# 2-minute demo script

**Setup before recording:** run `make run` (or `.\scripts\dev.ps1 run`), open http://localhost:8000 in dark mode at 1280×720, browser zoom 110%, no meetings in history (delete `data/` for a clean start).

| Time | Screen | Say |
|---|---|---|
| 0:00–0:12 | Landing page | "Every meeting ends the same way: good intentions, no follow-through. Someone has to rewrite the notes, work out who owns what, turn 'by Friday' into a date, and write the emails. ActionLoop does that loop for you." |
| 0:12–0:25 | **Try a sample** tab → click **Load & analyze** on *Startup weekly standup* | "I'll use a messy standup: interruptions, vague deadlines, ambiguous owners. No API key and nothing leaves this machine, as the privacy note says." |
| 0:25–0:35 | Progress steps | "It transcribes if it's audio, extracts, then drafts emails. Progress streams live." |
| 0:35–0:55 | **Overview**: summary, decisions | "A TL;DR, decisions, risks. Notice the quote under each decision." Click a quote → transcript highlights. "Every claim is backed by a verbatim quote that ActionLoop checks against the transcript. If it can't find it, the item gets an *unverified* badge. That's our anti-hallucination guard." |
| 0:55–1:10 | Back to Overview: **Needs clarification** panel | "ActionLoop never guesses. The README has no owner and 'at some point' isn't a deadline, so they're flagged instead of invented. 'By tomorrow' and 'by Friday' were resolved against the meeting date in code, not by the model." |
| 1:10–1:30 | **Board** tab: drag a card to *In progress*, open a card, set an owner, save | "Tasks land on a Kanban board with owner avatars and amber/red deadline chips. Drag, edit, filter. It's all saved." |
| 1:30–1:48 | **Emails** tab: show recap, switch tone to Concise, open a personal email, click **Open in mail app** | "A recap for everyone plus one personalised email per owner, in three tones. Editable, and drafts only: we never send anything." |
| 1:48–2:00 | **Export** tab: click **Download all as ZIP**, show the shareable report | "Markdown, CSV, calendar events, Slack text, JSON, all in one ZIP, plus a shareable report page. Paste a transcript or upload audio and ActionLoop turns your meeting into finished follow-through." |

**Tips:** keep the cursor slow; pre-load the sample once to confirm timing; if you want the audio path, upload `samples/sample-audio.wav` beforehand and mention local Whisper.
