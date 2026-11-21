"""Deterministic deadline resolution. The LLM never computes dates; we do, from the meeting date."""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from typing import Optional

import dateparser

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_WD_ABBR = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6}
_NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
VAGUE = re.compile(
    r"\b(soon|asap|sometime|at some point|eventually|when (we|i|you) can|later|whenever|in due course|tbd|tba)\b", re.I
)


def _weekday_index(token: str) -> Optional[int]:
    t = token.lower()
    if t in WEEKDAYS:
        return WEEKDAYS.index(t)
    return _WD_ABBR.get(t)


def _next_weekday(base: date, wd: int, *, strictly_after: bool = True) -> date:
    delta = (wd - base.weekday()) % 7
    if delta == 0 and strictly_after:
        delta = 7
    return base + timedelta(days=delta)


def is_vague(raw: Optional[str]) -> bool:
    return bool(raw and VAGUE.search(raw))


def resolve_deadline(raw: Optional[str], meeting_date: date) -> Optional[date]:
    """Resolve a spoken deadline ('by Friday', 'end of month') to an absolute date, or None if vague/unknown."""
    if not raw or not raw.strip():
        return None
    text = raw.strip().lower().strip(".,;!?")
    text = re.sub(r"^(by|before|until|due|on|no later than|for|at|within)\s+(the\s+)?", "", text).strip()
    if not text or VAGUE.search(text):
        return None

    if text in {"today", "tonight", "eod", "end of day", "end of the day", "cob", "this afternoon", "this evening"}:
        return meeting_date
    if text in {"tomorrow", "tomorrow morning", "tomorrow afternoon", "eod tomorrow", "end of day tomorrow"}:
        return meeting_date + timedelta(days=1)

    # end of week / month / quarter / year
    if re.fullmatch(r"(the )?(end of (the )?(this )?week|eow|this week|end of week)", text):
        return _next_weekday(meeting_date, 4, strictly_after=False)
    if re.fullmatch(r"(the )?(end of (the )?(this )?month|eom|this month|end of month)", text):
        return meeting_date.replace(day=calendar.monthrange(meeting_date.year, meeting_date.month)[1])
    if re.fullmatch(r"(the )?(end of (the )?next month)", text):
        y, m = (meeting_date.year + (meeting_date.month == 12), meeting_date.month % 12 + 1)
        return date(y, m, calendar.monthrange(y, m)[1])
    if re.fullmatch(r"(the )?(end of (the )?(this )?(year|eoy))", text):
        return date(meeting_date.year, 12, 31)
    if re.fullmatch(r"(the )?end of (the )?(this )?(quarter|eoq)", text):
        q_end_month = ((meeting_date.month - 1) // 3 + 1) * 3
        return date(meeting_date.year, q_end_month, calendar.monthrange(meeting_date.year, q_end_month)[1])

    # next week / next <weekday> / this <weekday> / <weekday>
    if text in {"next week", "early next week", "the following week"}:
        return _next_weekday(meeting_date, 0)  # Monday of next week
    if text in {"later this week", "end of this week"}:
        return _next_weekday(meeting_date, 4, strictly_after=False)
    if text in {"week after next", "the week after next", "the week after that"}:
        return _next_weekday(meeting_date, 0) + timedelta(days=7)
    if text in {"mid next week", "midweek next week"}:
        return _next_weekday(meeting_date, 0) + timedelta(days=2)
    m = re.fullmatch(
        r"(?:(next|this|coming|upcoming)\s+)?([a-z]+)(?:\s+(?:morning|afternoon|evening|night|eod|end of day|cob))?", text
    )
    if m:
        wd = _weekday_index(m.group(2))
        if wd is not None:
            if m.group(1) == "next":
                # 'next Friday' = Friday of the following week
                return _next_weekday(meeting_date, 0) + timedelta(days=wd)
            return _next_weekday(meeting_date, wd)

    # in N days/weeks/months
    m = re.fullmatch(
        r"(?:in\s+)?(\d+|a|an|one|two|three|four|five|six|seven|eight)\s+"
        r"(day|days|week|weeks|month|months|business day|business days)(?:\s+(?:from now|time))?",
        text,
    )
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else _NUM_WORDS[m.group(1)]
        unit = m.group(2)
        if unit.startswith("business"):
            d, left = meeting_date, n
            while left:
                d += timedelta(days=1)
                if d.weekday() < 5:
                    left -= 1
            return d
        if unit.startswith("day"):
            return meeting_date + timedelta(days=n)
        if unit.startswith("week"):
            return meeting_date + timedelta(weeks=n)
        mo = meeting_date.month - 1 + n
        y, mm = meeting_date.year + mo // 12, mo % 12 + 1
        return date(y, mm, min(meeting_date.day, calendar.monthrange(y, mm)[1]))

    # Fallback: dateparser, anchored to the meeting date, preferring the future.
    base = datetime(meeting_date.year, meeting_date.month, meeting_date.day, 12, 0)
    try:
        parsed = dateparser.parse(
            text,
            settings={"RELATIVE_BASE": base, "PREFER_DATES_FROM": "future", "PREFER_DAY_OF_MONTH": "last"},
            languages=["en"],
        )
    except Exception:  # noqa: BLE001
        parsed = None
    if parsed is None:
        return None
    d = parsed.date()
    # An explicit month/day earlier than the meeting ("March 3" in a December meeting) means the next occurrence.
    if d < meeting_date and not re.search(r"\b\d{4}\b", text):
        try:
            d = d.replace(year=d.year + 1)
        except ValueError:
            return None
    return d
