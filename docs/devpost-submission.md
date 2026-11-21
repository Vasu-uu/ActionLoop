# Devpost submission text (ready to paste)

## Project name
ActionLoop

## Tagline
Turn messy meetings into finished follow-through: verified decisions, owned tasks and ready-to-send emails.

## Image gallery (upload in this order)
Screenshots are in `docs/screenshots/`. Devpost accepts JPG/PNG/GIF, ideally 3:2, so use these 800-px captures as-is or crop to 3:2.

1. `02-overview.png`: summary, decisions and the Needs clarification panel (use as the **thumbnail**)
2. `03-board.png`: Kanban board with deadline chips and clarification badges
3. `05-transcript-evidence.png`: evidence quote jumping to the highlighted transcript line
4. `04-emails.png`: team recap and per-owner email drafts
5. `06-export.png`: Markdown, CSV, ICS, JSON, Slack text and ZIP exports
6. `07-board-dark.png`: dark mode
7. `01-landing.png`: input options and one-click samples

Suggested captions: "Every claim is backed by a verified quote", "ActionLoop never guesses owners or deadlines", "Drafts only: nothing is ever sent".

## Inspiration
Every club, startup and study group has the same problem: the meeting goes well, and then nothing happens. Notes are incomplete, nobody remembers who said "I'll do it", "by Friday" means different days to different people, and the follow-up email never gets written. We wanted an agent that finishes the loop, and one that **doesn't make things up**, because a wrong owner or deadline is worse than a missing one.

## What it does
Paste a transcript or upload audio/video. ActionLoop transcribes it locally with Whisper, then extracts a summary, decisions, action items (owner, deadline, priority), open questions and risks. Every decision and task carries a verbatim evidence quote that the app verifies against the transcript, and unverifiable items get a warning badge. Relative deadlines such as "by Friday" are resolved in code against the meeting date. Items with a missing owner or vague deadline land in a *Needs clarification* panel instead of being guessed. You get a drag-and-drop Kanban board, a team recap plus one personalised email per owner (three tones, drafts only), and exports to Markdown, CSV, ICS calendar events, Slack text, JSON and ZIP, plus a shareable report. It runs with **no API key and no internet** in demo mode, or with Claude, OpenAI-compatible models or local Ollama.

## How we built it
FastAPI + Pydantic v2 + SQLModel/SQLite on the backend; faster-whisper and ffmpeg for transcription; a provider abstraction (`LLMProvider`) with Anthropic, OpenAI-compatible/Ollama and an offline demo provider. Extraction is strict JSON validated by Pydantic with retries that feed the validation error back to the model, chunking with overlap and a merge/dedupe pass for long meetings, fuzzy quote verification (RapidFuzz) and deterministic date resolution. The frontend is React + Vite + TypeScript + Tailwind with @dnd-kit for the board, live progress over Server-Sent Events, and dark mode. Packaged with Docker and a Makefile, with 72 pytest and 13 Vitest tests. Claude Code assisted development; see the AI disclosure in the README.

## Challenges we ran into
- **Trust**: making the output verifiable. Evidence quotes plus fuzzy matching that tolerates small transcription differences, but not invention.
- **Dates**: "next Wednesday", "end of the month", "week after next" are ambiguous. We defined clear rules, tested them, and left vague phrases unresolved on purpose.
- **Working with no API key**: a demo provider that returns realistic results for samples and falls back to a conservative rule-based extractor, going through the same validation and verification path as real models.
- **Drag-and-drop**: reliable cross-column drops, including into empty columns, with optimistic updates and server-side reordering.
- **Hardware variety**: Whisper on machines whose GPU is present but unusable; we auto-fall back to CPU.

## Accomplishments that we're proud of
An agent that says "I don't know" correctly, and shows its evidence. A complete flow from audio to calendar events that a judge can run in one command without any keys.

## What we learned
Structure and verification matter more than prompt cleverness: strict schemas, retries with error feedback, and programmatic checks make LLM output dependable. Keeping dates and verification in code makes the system testable.

## What's next for ActionLoop
Follow-up check mode (compare the next meeting with open tasks and mark done, still open or dropped), speaker-name mapping for audio, cross-meeting workload views, Slack/Calendar/Jira integrations, and optional authentication for shared reports.

## Built with
Python, FastAPI, Pydantic, SQLModel, SQLite, faster-whisper, FFmpeg, dateparser, RapidFuzz, Anthropic Claude API, OpenAI-compatible APIs, Ollama, React, TypeScript, Vite, Tailwind CSS, dnd-kit, Docker, pytest, Vitest
