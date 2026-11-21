# Samples

Three fictional meetings (about 300 to 400 words each) with natural messy speech, interruptions, vague deadlines and ambiguous owners:

| File | Scenario |
|---|---|
| `startup-standup.txt` | Early-stage startup standup |
| `club-planning.txt` | College club hackathon planning |
| `project-retro.txt` | Engineering sprint retrospective |

`index.json` lists them for the app (`GET /api/samples`). In demo mode these return pre-baked extractions (`backend/app/demo_data/`).

## Sample audio

`sample-audio.wav` is a short synthetic recording (about 16 s) for testing the Whisper path. Script:

> Okay team. Marcus, can you fix the Safari bug by Friday? Marcus: Yes, I will fix the Safari bug by Friday. We decided to use Postgres for launch.

Regenerate or record your own:

```powershell
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile("$PWD\sample-audio.wav")
$s.Speak("Okay team. Marcus, can you fix the Safari bug by Friday? Yes, I will fix the Safari bug by Friday. We decided to use Postgres for launch.")
$s.Dispose()
```

Or on macOS: `say -o sample.aiff "..." && ffmpeg -i sample.aiff sample-audio.wav`. Upload it on the **Upload audio/video** tab. Note that the `tiny` model may mishear words (it heard "Postgres" as "Poskers"); use `WHISPER_MODEL=base` or `small` for better accuracy.
