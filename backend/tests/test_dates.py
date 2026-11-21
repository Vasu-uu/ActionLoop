from datetime import date

import pytest

from app.services.dates import resolve_deadline

# Meeting on Wednesday 2026-03-11
MEET = date(2026, 3, 11)
assert MEET.weekday() == 2


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("by Friday", date(2026, 3, 13)),
        ("Friday", date(2026, 3, 13)),
        ("by Wednesday", date(2026, 3, 18)),  # same weekday => next week
        ("by next Wednesday", date(2026, 3, 18)),  # "next X" = X in the following Mon-Sun week
        ("next Monday", date(2026, 3, 16)),
        ("next Friday", date(2026, 3, 20)),
        ("tomorrow", date(2026, 3, 12)),
        ("by tomorrow", date(2026, 3, 12)),
        ("today", MEET),
        ("EOD", MEET),
        ("end of the week", date(2026, 3, 13)),
        ("by end of the month", date(2026, 3, 31)),
        ("end of month", date(2026, 3, 31)),
        ("next week", date(2026, 3, 16)),
        ("the week after next", date(2026, 3, 23)),
        ("in 3 days", date(2026, 3, 14)),
        ("in two weeks", date(2026, 3, 25)),
        ("in 5 business days", date(2026, 3, 18)),
        ("end of the quarter", date(2026, 3, 31)),
        ("by March 20th", date(2026, 3, 20)),
        ("April 2", date(2026, 4, 2)),
        ("2026-04-15", date(2026, 4, 15)),
    ],
)
def test_resolves(raw, expected):
    assert resolve_deadline(raw, MEET) == expected


@pytest.mark.parametrize("raw", [None, "", "  ", "soon", "ASAP", "whenever you can", "at some point", "sometime", "TBD", "gibberish words here"])
def test_vague_or_unknown_is_none(raw):
    assert resolve_deadline(raw, MEET) is None


def test_year_rollover():
    assert resolve_deadline("end of next month", date(2026, 12, 10)) == date(2027, 1, 31)
    assert resolve_deadline("January 5", date(2026, 12, 10)) == date(2027, 1, 5)
    assert resolve_deadline("in 2 months", date(2026, 12, 31)) == date(2027, 2, 28)


def test_relative_to_meeting_date_not_today():
    assert resolve_deadline("tomorrow", date(2020, 1, 31)) == date(2020, 2, 1)
