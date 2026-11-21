# Architecture

```mermaid
flowchart TD
  subgraph Browser
    UI[React SPA<br/>Input · Overview · Board · Emails · Transcript · Export]
  end
  subgraph FastAPI
    R1[routers/meetings.py]
    R2[routers/tasks.py]
    R3[routers/exports.py + /m/id]
    P[services/pipeline.py<br/>background task]
    T[services/transcribe.py<br/>ffmpeg → faster-whisper]
    X[services/extract.py]
    TR[services/transcript.py<br/>parse · chunk · locate_quote]
    DT[services/dates.py]
    L[services/llm.py<br/>LLMProvider]
    DM[services/demo.py]
    EM[services/emails.py]
    EXP[services/exports.py]
  end
  DB[(SQLite<br/>Meeting · Task · EmailDraft)]
  UI -- "POST /api/meetings(/audio)" --> R1
  UI -- "SSE /progress" --> R1
  UI -- "PATCH /api/tasks" --> R2
  UI -- "GET /export/*" --> R3
  R1 --> P
  P --> T
  P --> X
  X --> TR
  X --> L
  L --> AN[Anthropic]
  L --> OA[OpenAI / Ollama]
  L --> DM
  X --> DT
  P --> EM
  R1 & R2 & R3 --> DB
  R3 --> EXP
```

## Request flow

1. `POST /api/meetings` stores the meeting (`queued`) and returns `202`; a background task runs `pipeline.process_meeting`.
2. Status moves `transcribing` (audio only) → `analyzing` → `drafting` → `done` (or `error` with a user-facing message). `GET /progress` streams each change as SSE; the UI falls back to polling if SSE drops.
3. `extract.run_extraction` chunks long input, calls the provider with validation + retries, merges, verifies quotes, and resolves dates in code.
4. Action items become `Task` rows (the Kanban cards); summary, decisions, questions, risks and warnings are stored as JSON on the meeting.
5. `emails.build_all` renders a recap and one draft per owner for the chosen tone.

## Design decisions

- **Provider abstraction**: `LLMProvider.complete(system, messages)` returns text; validation, retries and parsing live once in `extract.py`, so all providers (and the demo provider) share the same safety path.
- **Demo provider**: serves pre-baked JSON for the bundled samples (filtered to the quotes present in the given text, which also works per chunk) and a conservative rule-based extractor otherwise.
- **Dates in code**: determinism, testability, and the model cannot hallucinate a calendar.
- **Evidence quotes**: the anti-hallucination feature and the source for transcript jump links.
- **SQLite + background threads**: zero-setup for judges; the pipeline updates a status column that SSE polls, so no broker is required.
- **Emails are templates** (tone-aware, deterministic). With a real provider, the opening line is optionally polished by the LLM and falls back to the template on any failure.
- **One origin in production**: FastAPI serves the built SPA, `/api`, and `/m/{id}`; Vite proxies in development.
