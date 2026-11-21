"""Offline demo provider.

* For the bundled sample meetings it returns pre-baked, realistic extractions (app/demo_data/*.json).
* For any other text it falls back to a transparent rule-based extractor (English only), so the whole
  app works with no API key and no internet. It is deliberately conservative: it never invents owners
  or deadlines.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .llm import LLMProvider
from .transcript import locate_quote, normalize, parse_transcript

DATA_DIR = Path(__file__).resolve().parents[1] / "demo_data"

_LINE_PREFIX = re.compile(r"^\s*(?:\[[\d:]+\]\s*)?(?:([A-Z][\w.'\- ]{0,28}?):\s+)?(.*)$")
_SENT = re.compile(r"(?<=[.!?])\s+")

DEADLINE_RE = re.compile(
    r"\b((?:by|before|until|on|due)\s+(?:the\s+)?(?:end of (?:the )?(?:day|week|month|quarter|year)|eod|eow|"
    r"(?:next |this )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|tomorrow|today|tonight|"
    r"next week|next month|the \d{1,2}(?:st|nd|rd|th)|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?)"
    r"|next week|next month|tomorrow|tonight|end of (?:the )?(?:day|week|month)|in (?:\d+|a|two|three|four|five) (?:days?|weeks?)"
    r"|(?:this|next) (?:monday|tuesday|wednesday|thursday|friday)|week after next|asap|soonish|soon)\b",
    re.I,
)
COMMIT_RE = re.compile(
    r"\b(i'll|i will|i can (?:take|do|handle|look)|i'm going to|i am going to|i'd be happy to|let me|i'll take|i can)\b", re.I
)
ASSIGN_RE = re.compile(r"\b([A-Z][a-z]{1,15}),?\s+(?:can|could|will|would)\s+you\b")
NAME_WILL_RE = re.compile(r"\b([A-Z][a-z]{1,15})\s+(?:will|is going to|to take|should)\s+(?!be\b)")
UNOWNED_RE = re.compile(r"\b(we need to|we should|someone should|somebody should|someone needs to|somebody needs to|let's|we have to)\b", re.I)
DECISION_RE = re.compile(r"\b(we decided|decided to|decision(?: made)?:|we're going with|we are going with|let's go with|agreed to|the plan is|we'll go with|we're going to go with)\b", re.I)
RISK_RE = re.compile(r"\b(risk|worried|worry|concern|blocker|blocked|might slip|behind schedule|delay|dependency|throttle|sunset|no backup|out of sync|fail)\w*\b", re.I)
QUESTION_RE = re.compile(r"(open question|not sure|don't know|do not know|still need to figure|\?$)", re.I)
HIGH_RE = re.compile(r"\b(urgent|asap|critical|blocking|blocker|today|tomorrow|immediately|before launch)\b", re.I)
LOW_RE = re.compile(r"\b(nice to have|eventually|no rush|not a priority|if we have time|at some point)\b", re.I)
STOP = set("""the a an and or but to of in on for with at by from is are was were be been it this that these those we you i they he she
our your their my so just like um uh yeah okay ok well really very about also then there here what when who how why which can could
should would will have has had do does did not no yes if as into than too more most some any all one two get got going gonna kinda
sort maybe actually basically think know need want let lets right good great cool thanks thank everyone""".split())


def _clean(s: str) -> str:
    s = re.sub(r"\b(um+|uh+|you know|like,)\b[,.]?\s*", "", s, flags=re.I)
    return " ".join(s.split())


def _title(sentence: str) -> str:
    t = _clean(sentence)
    t = re.sub(r"^(okay|ok|so|yeah|yes|sure|great|fine|right|and|also|well)[, ]+", "", t, flags=re.I)
    t = re.sub(r"^(i'll|i will|i can|let me|i'm going to)\s+", "", t, flags=re.I)
    t = t.rstrip(" .!?")
    return (t[:1].upper() + t[1:])[:100]


def heuristic_extract(transcript: str) -> dict:
    segments = parse_transcript(transcript)
    sentences: list[tuple[str | None, str]] = []
    for seg in segments:
        for s in _SENT.split(seg["text"]):
            s = s.strip()
            if len(s) > 8:
                sentences.append((seg["speaker"], s))

    actions, decisions, questions, risks = [], [], [], []
    seen: set[str] = set()
    for idx, (speaker, s) in enumerate(sentences):
        key = normalize(s)
        if key in seen:
            continue
        deadline = DEADLINE_RE.search(s)
        dl = deadline.group(1) if deadline else None
        if DECISION_RE.search(s):
            decisions.append({"decision": _title(s), "rationale": None, "evidence_quote": s})
            seen.add(key)
            continue
        owner, conf = None, "low"
        m = ASSIGN_RE.search(s)
        if COMMIT_RE.search(s) and speaker:
            owner, conf = speaker, "high"
        elif m:
            owner, conf = m.group(1), "medium"
        elif (n := NAME_WILL_RE.search(s)) and n.group(1) not in {"We", "They", "It", "That", "This", "There", "Then"}:
            owner, conf = n.group(1), "medium"
        is_action = bool(owner) or bool(UNOWNED_RE.search(s))
        if is_action and not s.endswith("?") or (m and s.endswith("?")):
            # when a "can you" request is answered with a commitment next, prefer the answerer's own sentence
            if m and idx + 1 < len(sentences) and sentences[idx + 1][0] == m.group(1) and COMMIT_RE.search(sentences[idx + 1][1]):
                continue
            prio = "high" if HIGH_RE.search(s) else "low" if LOW_RE.search(s) else "medium"
            actions.append({"title": _title(s), "description": "", "owner": owner, "owner_confidence": conf,
                            "deadline_raw": dl, "priority": prio, "evidence_quote": s})
            seen.add(key)
            continue
        if RISK_RE.search(s) and len(risks) < 5:
            sev = "high" if re.search(r"critical|major|serious|big deal|real risk", s, re.I) else "medium"
            risks.append({"risk": _title(s), "severity": sev})
        if QUESTION_RE.search(s) and len(s.split()) >= 6 and re.search(r"\b(who|when|should we|do we|which|how|are we|is it)\b", s, re.I) and len(questions) < 5:
            questions.append({"question": _title(s).rstrip("?") + "?", "suggested_owner": None})

    words = [w for w in re.findall(r"[a-zA-Z]{4,}", transcript.lower()) if w not in STOP]
    topics = [w for w, _ in Counter(words).most_common(5)]
    bullets = [f"{len(actions)} action item(s), {len(decisions)} decision(s) and {len(questions)} open question(s) identified."]
    bullets += [d["decision"] for d in decisions[:2]] + [a["title"] for a in actions[:2]]
    return {
        "summary": {
            "bullets": bullets[:5],
            "paragraph": "Rule-based demo summary (no AI model configured): "
            f"the meeting contained {len(sentences)} sentences across {len({s for s, _ in sentences if s}) or 'an unknown number of'} speaker(s). "
            "Configure an LLM provider for a richer, abstractive summary.",
        },
        "decisions": decisions[:8], "action_items": actions[:15], "open_questions": questions, "risks": risks, "topics": topics,
    }


def _load_fixtures() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DATA_DIR.glob("*.json"))]


def _fixture_for(text: str) -> dict | None:
    """Return a fixture filtered to what appears in `text` (works for chunks), or None if it is not a sample."""
    segs = parse_transcript(text)
    for fx in _load_fixtures():
        quotes = [x["evidence_quote"] for x in fx["decisions"] + fx["action_items"]]
        hits = [locate_quote(q, segs)[0] for q in quotes]
        if hits and sum(hits) >= max(2, len(hits) // 3):
            out = json.loads(json.dumps(fx))
            for key in ("decisions", "action_items"):
                out[key] = [x for x, ok in zip(fx[key], [locate_quote(x["evidence_quote"], segs)[0] for x in fx[key]]) if ok]
            return out
    return None


class DemoProvider(LLMProvider):
    name = "demo"
    model = "built-in samples + rule-based"
    local = True
    is_demo = True

    def complete(self, system: str, messages: list[dict], *, json_mode: bool = True, max_tokens: int = 8000) -> str:
        first = messages[0]["content"]
        if "ACTIONLOOP_TASK: MERGE_SUMMARY" in system:
            return first
        m = re.search(r"<transcript>\n(.*?)\n</transcript>", first, re.S)
        transcript = m.group(1) if m else first
        # strip leading "[mm:ss] " added by render_for_llm; parse_transcript handles them as timestamps
        result = _fixture_for(transcript) or heuristic_extract(transcript)
        return json.dumps(result)
