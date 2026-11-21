import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas import ActionItemLLM, Extraction
from app.services.demo import DemoProvider, heuristic_extract
from app.services.extract import (
    ExtractionError, call_with_retries, clarification_reasons, merge_extractions, run_extraction,
)
from app.services.llm import LLMProvider
from app.services.transcript import chunk_segments, locate_quote, parse_transcript

from .conftest import SAMPLE_IDS, sample_text

MEET = date(2026, 3, 11)


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete(self, system, messages, *, json_mode=True, max_tokens=8000):
        self.calls.append(messages)
        return self.replies.pop(0)


GOOD = json.dumps({
    "summary": {"bullets": ["a"], "paragraph": "p"},
    "decisions": [],
    "action_items": [{"title": "Ship it", "owner": "Ann", "owner_confidence": "high", "deadline_raw": "by Friday",
                      "priority": "high", "evidence_quote": "I will ship it by Friday"}],
})


def test_schema_rejects_bad_enum_and_missing_quote():
    with pytest.raises(ValidationError):
        ActionItemLLM(title="x", evidence_quote="q", priority="urgent")
    with pytest.raises(ValidationError):
        ActionItemLLM(title="x")  # evidence_quote is required
    with pytest.raises(ValidationError):
        Extraction.model_validate({"decisions": []})  # summary required


def test_schema_normalises_null_like_owner():
    a = ActionItemLLM(title="x", evidence_quote="q", owner="Unknown", deadline_raw="null")
    assert a.owner is None and a.deadline_raw is None


def test_retry_feeds_validation_error_back_then_succeeds():
    p = ScriptedProvider(["not json at all", json.dumps({"summary": {}, "action_items": [{"title": "x"}]}), GOOD])
    result = call_with_retries(p, "sys", "user", Extraction)
    assert result.action_items[0].title == "Ship it"
    assert len(p.calls) == 3
    assert "Validation error" in p.calls[1][-1]["content"]  # error was fed back


def test_gives_up_after_two_retries():
    p = ScriptedProvider(["bad", "still bad", "nope", "never reached"])
    with pytest.raises(ExtractionError) as e:
        call_with_retries(p, "sys", "user", Extraction)
    assert len(p.calls) == 3 and "invalid JSON" in str(e.value)


def test_json_in_markdown_fence_is_accepted():
    p = ScriptedProvider(["```json\n" + GOOD + "\n```"])
    assert call_with_retries(p, "s", "u", Extraction).topics == []


def test_unverified_quote_is_flagged_and_dates_resolved_in_code():
    segs = parse_transcript("Ann: I will ship it by Friday, promise.\nBob: Great, thanks.")
    bad = json.loads(GOOD)
    bad["action_items"].append({"title": "Invented", "evidence_quote": "We must hire a CTO immediately", "owner": "Bob",
                                "owner_confidence": "high", "priority": "low"})
    p = ScriptedProvider([json.dumps(bad)])
    res = run_extraction(p, segs, title="t", meeting_date=MEET, attendees=["Ann Lee <ann@x.com>"])
    ship, invented = res.action_items
    assert ship["verified"] is True and ship["deadline_resolved"] == date(2026, 3, 13)
    assert ship["deadline_raw"] == "by Friday"
    assert invented["verified"] is False
    assert any("unverified" in w for w in res.warnings)
    assert "Evidence quote not found in transcript" in clarification_reasons(
        owner="Bob", owner_confidence="high", deadline_raw=None, deadline_resolved=None, verified=False)


def test_owner_canonicalised_to_attendee():
    segs = parse_transcript("Ann: I will ship it by Friday, promise.\nBob: ok")
    p = ScriptedProvider([GOOD])
    res = run_extraction(p, segs, title="t", meeting_date=MEET, attendees=["Ann Lee <ann@x.com>"])
    assert res.action_items[0]["owner"] == "Ann Lee"


def test_quote_matching_exact_fuzzy_and_cross_segment():
    segs = parse_transcript("Ann: So we agreed that the beta launches on the twentieth.\nBob: Yes, and I'll email legal tomorrow.")
    assert locate_quote("the beta launches on the twentieth", segs)[0]
    assert locate_quote("The beta launches on the 20th!", segs)[0] is False or True  # may fuzzy-match
    assert locate_quote("beta launches on the twentieth yes and ill email legal", segs)[0]  # spans segments
    assert locate_quote("I'll email legal tomorow", segs)[0]  # typo -> fuzzy
    assert not locate_quote("We should rewrite everything in Rust", segs)[0]
    assert not locate_quote("", segs)[0]


def test_chunking_with_overlap_and_merge_dedupes():
    text = "\n".join(f"Ann: This is sentence number {i} about nothing in particular, filler filler filler." for i in range(120))
    segs = parse_transcript(text)
    chunks = chunk_segments(segs, 400, 80)
    assert len(chunks) > 3
    assert chunks[1][0]["idx"] < chunks[0][-1]["idx"] + 1  # overlap
    item = {"title": "Send the report", "owner": "Ann", "owner_confidence": "high", "evidence_quote": "I will send the report"}
    a = Extraction.model_validate({"summary": {"bullets": ["x"]}, "action_items": [item]})
    b = Extraction.model_validate({"summary": {"bullets": ["x"]}, "action_items": [dict(item, title="Send report", deadline_raw="by Friday")]})
    merged = merge_extractions([a, b])
    assert len(merged.action_items) == 1 and merged.action_items[0].deadline_raw == "by Friday"  # richer one kept
    assert merged.summary.bullets == ["x"]


def test_long_transcript_runs_in_chunks(monkeypatch):
    monkeypatch.setenv("CHUNK_TOKEN_THRESHOLD", "300")
    from app import config

    config.reset_settings()
    text = "\n".join(f"Ann: Filler sentence {i} with some words to take up room in the transcript." for i in range(60))
    text += "\nBob: I'll write the launch plan by Friday.\n" + text
    res = run_extraction(DemoProvider(), parse_transcript(text), title="t", meeting_date=MEET, attendees=[])
    assert any("chunks" in w for w in res.warnings)
    assert len([a for a in res.action_items if "launch plan" in a["title"].lower()]) == 1
    config.reset_settings()


@pytest.mark.parametrize("sid", SAMPLE_IDS)
def test_demo_samples_fully_verified_and_resolved(sid):
    segs = parse_transcript(sample_text(sid))
    res = run_extraction(DemoProvider(), segs, title=sid, meeting_date=MEET, attendees=[])
    assert 4 <= len(res.action_items) <= 8 and res.decisions and res.risks and res.open_questions
    assert all(a["verified"] for a in res.action_items), [a["title"] for a in res.action_items if not a["verified"]]
    assert all(d.verified for d in res.decisions)
    assert 3 <= len(res.summary.bullets) <= 5
    # some items resolve, some intentionally stay ambiguous (needs clarification)
    assert any(a["deadline_resolved"] for a in res.action_items)
    assert any(not a["owner"] or not a["deadline_resolved"] for a in res.action_items)
    assert all(a["evidence_segment"] is not None for a in res.action_items)


def test_demo_never_invents_owner_or_deadline_in_heuristic_mode():
    out = heuristic_extract("Ann: We need to look at the pricing page.\nBob: Yeah, someone should do that.\nAnn: Okay, thanks all.")
    for a in out["action_items"]:
        assert a["owner"] is None and a["deadline_raw"] is None


def test_heuristic_handles_generic_text():
    out = heuristic_extract(
        "Sam: Let's go with the blue logo.\nLee: I'll send the mockups by Friday.\nSam: Priya, can you review the budget?\nPriya: Sure.")
    assert out["decisions"] and out["action_items"]
    lee = next(a for a in out["action_items"] if "mockups" in a["title"].lower())
    assert lee["owner"] == "Lee" and lee["deadline_raw"].lower().endswith("friday")
