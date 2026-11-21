"""Transcript parsing and evidence-quote verification (the anti-hallucination check)."""
from __future__ import annotations

import re
from typing import Optional

from rapidfuzz import fuzz

# Optional "[mm:ss]" / "[hh:mm:ss]" then "Name:" at the start of a line.
_TS = r"\[?\(?(\d{1,2}:\d{2}(?::\d{2})?)\)?\]?"
_LINE_RE = re.compile(rf"^\s*(?:{_TS}\s*)?([A-Z][\w.'\- ]{{0,28}}?)\s*:\s+(\S.*)$")
_TS_ONLY_RE = re.compile(rf"^\s*{_TS}\s+(\S.*)$")
_NOT_SPEAKERS = {"note", "notes", "agenda", "action", "actions", "todo", "summary", "re", "subject", "date", "time", "ps"}
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")
MAX_SEGMENT_CHARS = 420


def _ts_to_seconds(ts: str) -> float:
    parts = [int(p) for p in ts.split(":")]
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return float(sec)


def format_ts(seconds: Optional[float]) -> str:
    if seconds is None:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_SEGMENT_CHARS:
        return [text]
    out, cur = [], ""
    for sent in _SENT_SPLIT.split(text):
        if cur and len(cur) + len(sent) + 1 > MAX_SEGMENT_CHARS:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def parse_transcript(text: str) -> list[dict]:
    """Split pasted text into segments. 'Name:' prefixes become speakers; otherwise speaker stays None."""
    lines = [ln for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]
    matches = [_LINE_RE.match(ln) for ln in lines]
    speaker_lines = [m for m in matches if m and m.group(2).strip().lower() not in _NOT_SPEAKERS]
    use_speakers = len(speaker_lines) >= 2 and len(speaker_lines) >= 0.3 * len(lines)

    segments: list[dict] = []
    for ln, m in zip(lines, matches):
        speaker, ts, body = None, None, ln.strip()
        if use_speakers and m and m.group(2).strip().lower() not in _NOT_SPEAKERS:
            ts = m.group(1)
            speaker = " ".join(m.group(2).split())
            body = m.group(3).strip()
        else:
            tm = _TS_ONLY_RE.match(ln)
            if tm:
                ts, body = tm.group(1), tm.group(2).strip()
        start = _ts_to_seconds(ts) if ts else None
        for piece in _split_long(body):
            segments.append({"idx": len(segments), "start": start, "end": None, "speaker": speaker, "text": piece})
    return segments


def segments_from_whisper(raw: list[dict]) -> list[dict]:
    return [
        {"idx": i, "start": s.get("start"), "end": s.get("end"), "speaker": None, "text": s["text"].strip()}
        for i, s in enumerate(raw)
        if s.get("text", "").strip()
    ]


def render_for_llm(segments: list[dict]) -> str:
    out = []
    for s in segments:
        prefix = f"[{format_ts(s['start'])}] " if s.get("start") is not None else ""
        who = f"{s['speaker']}: " if s.get("speaker") else ""
        out.append(f"{prefix}{who}{s['text']}")
    return "\n".join(out)


def plain_text(segments: list[dict]) -> str:
    return "\n".join((f"{s['speaker']}: " if s.get("speaker") else "") + s["text"] for s in segments)


_NORM_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("'", "")
    return " ".join(_NORM_RE.sub(" ", text).split())


FUZZY_THRESHOLD = 88


def locate_quote(quote: str, segments: list[dict]) -> tuple[bool, Optional[int], Optional[float]]:
    """Return (verified, segment_idx, timestamp). Exact (normalised) match first, then fuzzy."""
    q = normalize(quote)
    if len(q) < 8 or not segments:
        return False, None, None
    norm = [normalize(s["text"]) for s in segments]

    # 1) exact normalised substring in a single segment
    for i, n in enumerate(norm):
        if q in n:
            return True, segments[i]["idx"], segments[i].get("start")

    # 2) quote spans neighbouring segments (join 2-3)
    for width in (2, 3):
        for i in range(len(norm) - width + 1):
            joined = " ".join(norm[i : i + width])
            if q in joined:
                return True, segments[i]["idx"], segments[i].get("start")

    # 3) fuzzy: best partial match in a single segment or a 2-segment window
    best, best_i = 0.0, None
    for i, n in enumerate(norm):
        score = fuzz.partial_ratio(q, n) if len(n) >= len(q) else fuzz.ratio(q, n)
        if score > best:
            best, best_i = score, i
    for i in range(len(norm) - 1):
        score = fuzz.partial_ratio(q, norm[i] + " " + norm[i + 1])
        if score > best:
            best, best_i = score, i
    if best >= FUZZY_THRESHOLD and best_i is not None:
        return True, segments[best_i]["idx"], segments[best_i].get("start")
    return False, None, None


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_segments(segments: list[dict], max_tokens: int, overlap_tokens: int) -> list[list[dict]]:
    """Group segments into chunks of ~max_tokens, carrying ~overlap_tokens of trailing context forward."""
    chunks: list[list[dict]] = []
    cur: list[dict] = []
    cur_tok = 0
    for seg in segments:
        t = estimate_tokens(seg["text"]) + 4
        if cur and cur_tok + t > max_tokens:
            chunks.append(cur)
            carry, tok = [], 0
            for prev in reversed(cur):
                pt = estimate_tokens(prev["text"]) + 4
                if tok + pt > overlap_tokens:
                    break
                carry.insert(0, prev)
                tok += pt
            cur, cur_tok = carry, tok
        cur.append(seg)
        cur_tok += t
    if cur:
        chunks.append(cur)
    return chunks
