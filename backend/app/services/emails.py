"""Follow-up email drafts (recap + one per owner). Drafts only; nothing is ever sent."""
from __future__ import annotations

import html
import logging
import re
from datetime import date
from typing import Optional

from ..schemas import MeetingOut, TaskOut
from .llm import LLMProvider

log = logging.getLogger(__name__)

TONES = {
    "professional": {
        "recap_open": "Please find below a summary of our meeting, including decisions and next steps.",
        "owner_open": "Following our meeting, here are the action items assigned to you.",
        "close": "Please let me know if any of the above is incorrect or if you need support.",
        "sign": "Best regards,",
        "hi": "Hello {name},",
    },
    "friendly": {
        "recap_open": "Thanks for a great meeting! Here's a quick recap so we're all on the same page.",
        "owner_open": "Thanks for today! Here's what's on your plate coming out of the meeting.",
        "close": "Shout if anything looks off or you need a hand. Thanks, everyone!",
        "sign": "Cheers,",
        "hi": "Hi {name},",
    },
    "concise": {
        "recap_open": "Meeting recap:",
        "owner_open": "Your action items:",
        "close": "Reply with corrections.",
        "sign": "Thanks,",
        "hi": "{name},",
    },
}


def parse_attendees(value: str | list[str] | None) -> list[str]:
    if not value:
        return []
    items = re.split(r"[,;\n]+", value) if isinstance(value, str) else list(value)
    return [i.strip() for i in items if i and i.strip()][:50]


def attendee_name(entry: str) -> str:
    return entry.split("<")[0].strip().strip('"') or entry


def attendee_email(owner: Optional[str], attendees: list[str]) -> Optional[str]:
    if not owner:
        return None
    for a in attendees:
        m = re.search(r"<([^>]+@[^>]+)>", a) or re.fullmatch(r"\s*(\S+@\S+)\s*", a)
        name = attendee_name(a)
        if m and (owner.lower() == name.lower() or owner.lower() == name.split()[0].lower()):
            return m.group(1)
    return None


def _due(t: TaskOut) -> str:
    if t.deadline_resolved:
        return t.deadline_resolved.strftime("%a %b %d, %Y").replace(" 0", " ")
    return f"{t.deadline_raw} (date TBC)" if t.deadline_raw else "No deadline set"


def _fmt_date(d: date) -> str:
    return d.strftime("%A, %B %d, %Y").replace(" 0", " ")


def _task_lines(tasks: list[TaskOut], with_owner: bool) -> list[str]:
    out = []
    for t in tasks:
        owner = f" | Owner: {t.owner or 'TBD'}" if with_owner else ""
        out.append(f"- {t.title}{owner} | Due: {_due(t)} | Priority: {t.priority}")
    return out


def _task_table(tasks: list[TaskOut], with_owner: bool) -> str:
    head = "<tr><th align='left'>Task</th>" + ("<th align='left'>Owner</th>" if with_owner else "") + "<th align='left'>Due</th><th align='left'>Priority</th></tr>"
    rows = "".join(
        f"<tr><td>{html.escape(t.title)}</td>" + (f"<td>{html.escape(t.owner or 'TBD')}</td>" if with_owner else "")
        + f"<td>{html.escape(_due(t))}</td><td>{html.escape(t.priority)}</td></tr>"
        for t in tasks
    )
    return (
        "<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse;border-color:#ddd;font-size:14px'>"
        f"{head}{rows}</table>"
    )


def _polish(provider: Optional[LLMProvider], text: str, context: str) -> str:
    """Optionally let a real LLM rewrite the one-line opener. Falls back to the template on any failure."""
    if not provider or provider.is_demo:
        return text
    try:
        out = provider.complete(
            "ACTIONLOOP_TASK: POLISH\nRewrite the sentence in the same tone, same language as the context, max 30 words. "
            "Return only the sentence, no quotes.",
            [{"role": "user", "content": f"Context: {context}\nSentence: {text}"}],
            json_mode=False, max_tokens=120,
        ).strip().strip('"')
        return out if 5 < len(out) < 300 else text
    except Exception as e:  # noqa: BLE001
        log.info("Email polish skipped: %s", e)
        return text


def build_recap(m: MeetingOut, tone: str, provider: Optional[LLMProvider] = None) -> dict:
    t = TONES[tone]
    opener = _polish(provider, t["recap_open"], m.title)
    text = [t["hi"].format(name="team"), "", opener, ""]
    if m.summary and m.summary.bullets:
        text += ["SUMMARY"] + [f"- {b}" for b in m.summary.bullets] + [""]
    if m.decisions:
        text += ["DECISIONS"] + [f"- {d.decision}" for d in m.decisions] + [""]
    tasks = [x for x in m.tasks if x.status != "done"] or m.tasks
    if tasks:
        text += ["ACTION ITEMS"] + _task_lines(tasks, True) + [""]
    if m.open_questions:
        text += ["OPEN QUESTIONS"] + [f"- {q.question}" for q in m.open_questions] + [""]
    text += [t["close"], "", t["sign"], ""]
    h = [f"<p>{html.escape(t['hi'].format(name='team'))}</p>", f"<p>{html.escape(opener)}</p>"]
    if m.summary and m.summary.bullets:
        h.append("<h3>Summary</h3><ul>" + "".join(f"<li>{html.escape(b)}</li>" for b in m.summary.bullets) + "</ul>")
    if m.decisions:
        h.append("<h3>Decisions</h3><ul>" + "".join(f"<li>{html.escape(d.decision)}</li>" for d in m.decisions) + "</ul>")
    if tasks:
        h.append("<h3>Action items</h3>" + _task_table(tasks, True))
    if m.open_questions:
        h.append("<h3>Open questions</h3><ul>" + "".join(f"<li>{html.escape(q.question)}</li>" for q in m.open_questions) + "</ul>")
    h.append(f"<p>{html.escape(t['close'])}</p><p>{html.escape(t['sign'])}</p>")
    return {
        "kind": "recap", "recipient": None, "to_addr": None, "tone": tone,
        "subject": f"Recap: {m.title} ({_fmt_date(m.date)})", "body_text": "\n".join(text), "body_html": "".join(h),
    }


def build_owner_email(m: MeetingOut, owner: str, tasks: list[TaskOut], tone: str, provider: Optional[LLMProvider] = None) -> dict:
    t = TONES[tone]
    first = owner.split()[0] if owner else "there"
    opener = _polish(provider, t["owner_open"], m.title)
    text = [t["hi"].format(name=first), "", opener, ""] + _task_lines(tasks, False)
    unclear = [x for x in tasks if not x.deadline_resolved]
    if unclear:
        text += ["", "Could you confirm a due date for: " + "; ".join(x.title for x in unclear) + "?"]
    text += ["", t["close"], "", t["sign"], ""]
    h = [f"<p>{html.escape(t['hi'].format(name=first))}</p>", f"<p>{html.escape(opener)}</p>", _task_table(tasks, False)]
    if unclear:
        h.append("<p>Could you confirm a due date for: " + html.escape("; ".join(x.title for x in unclear)) + "?</p>")
    h.append(f"<p>{html.escape(t['close'])}</p><p>{html.escape(t['sign'])}</p>")
    return {
        "kind": "owner", "recipient": owner, "to_addr": attendee_email(owner, m.attendees), "tone": tone,
        "subject": f"Your action items from {m.title}", "body_text": "\n".join(text), "body_html": "".join(h),
    }


def build_all(m: MeetingOut, tone: str, provider: Optional[LLMProvider] = None) -> list[dict]:
    drafts = [build_recap(m, tone, provider)]
    by_owner: dict[str, list[TaskOut]] = {}
    for t in m.tasks:
        if t.owner and t.status != "done":
            by_owner.setdefault(t.owner, []).append(t)
    for owner, tasks in sorted(by_owner.items()):
        drafts.append(build_owner_email(m, owner, tasks, tone, provider))
    return drafts
