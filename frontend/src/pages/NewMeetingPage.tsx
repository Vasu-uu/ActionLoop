import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { todayISO } from "../lib/format";
import type { Health, Sample, Tone } from "../lib/types";
import { go } from "../hooks/useRoute";
import { useToast } from "../hooks/useToasts";

type Tab = "paste" | "upload" | "sample";
const EXTS = [".mp3", ".wav", ".m4a", ".mp4", ".webm"];
const tz = () => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { return "UTC"; } };

export function NewMeetingPage({ health, onCreated }: { health: Health | null; onCreated: () => void }) {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("sample");
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(todayISO());
  const [attendees, setAttendees] = useState("");
  const [timezone, setTimezone] = useState(tz());
  const [tone] = useState<Tone>("friendly");
  const [transcript, setTranscript] = useState("");
  const [sampleId, setSampleId] = useState<string | undefined>();
  const [file, setFile] = useState<File | null>(null);
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api.samples().then(setSamples).catch((e) => setErr(e.message)); }, []);
  const maxMb = health?.max_upload_mb ?? 100;

  const loadSample = async (id: string, analyze: boolean) => {
    setBusy(true); setErr(null);
    try {
      const s = await api.sample(id);
      const t = s.transcript ?? "";
      setTitle(s.title); setAttendees(s.attendees.join(", ")); setTranscript(t); setSampleId(id); setDate(todayISO());
      if (analyze) await submitMeeting({ title: s.title, attendees: s.attendees.join(", "), transcript: t, sample: id });
      else { setTab("paste"); toast("Sample loaded. Review it, then click Analyze.", "info"); }
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  const submitMeeting = async (o?: { title: string; attendees: string; transcript: string; sample?: string }) => {
    setErr(null);
    const useTranscript = o?.transcript ?? transcript;
    if (tab !== "upload" || o) {
      if (useTranscript.trim().split(/\s+/).filter(Boolean).length < 8) { setErr("Please paste a transcript of at least a few sentences."); return; }
    } else {
      if (!file) { setErr("Choose an audio or video file first."); return; }
      if (!EXTS.some((x) => file.name.toLowerCase().endsWith(x))) { setErr(`Unsupported file type. Use ${EXTS.join(", ")}.`); return; }
      if (file.size > maxMb * 1024 * 1024) { setErr(`File is larger than ${maxMb} MB.`); return; }
    }
    setBusy(true);
    try {
      const meta = { title: (o?.title ?? title) || "Untitled meeting", date, attendees: o?.attendees ?? attendees, timezone, tone };
      const m = tab === "upload" && !o
        ? await api.createFromAudio(file!, meta)
        : await api.createMeeting({ ...meta, transcript: useTranscript, sample_id: o?.sample ?? sampleId });
      onCreated();
      go(`#/meeting/${m.id}`);
    } catch (e) { setErr((e as Error).message); toast((e as Error).message, "error"); } finally { setBusy(false); }
  };

  const tabs: [Tab, string][] = [["paste", "Paste transcript"], ["upload", "Upload audio/video"], ["sample", "Try a sample"]];
  const words = transcript.trim() ? transcript.trim().split(/\s+/).length : 0;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <h1 className="text-2xl font-bold sm:text-3xl">Turn a messy meeting into finished follow-through</h1>
        <p className="mt-1 text-slate-600 dark:text-slate-400">Paste a transcript or upload a recording. Get decisions, an owner-assigned task board, and ready-to-send follow-ups.</p>
      </header>

      <div role="tablist" aria-label="Input method" className="flex gap-1 rounded-xl bg-slate-200 p-1 dark:bg-slate-800">
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
            className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition ${tab === id ? "bg-white shadow dark:bg-slate-950" : "text-slate-600 hover:text-slate-900 dark:text-slate-400"}`}>{label}</button>
        ))}
      </div>

      {tab === "sample" && (
        <div className="grid gap-3 sm:grid-cols-3" role="tabpanel">
          {samples === null ? Array.from({ length: 3 }, (_, i) => <div key={i} className="card h-40 animate-pulse" />) : samples.map((s) => (
            <div key={s.id} className="card flex flex-col">
              <h3 className="font-semibold">{s.title}</h3>
              <p className="mt-1 flex-1 text-sm text-slate-600 dark:text-slate-400">{s.description}</p>
              <p className="mt-2 text-xs text-slate-500">{s.attendees.join(", ")}</p>
              <div className="mt-3 flex gap-2">
                <button className="btn-primary flex-1" disabled={busy} onClick={() => loadSample(s.id, true)}>{busy ? "…" : "Load & analyze"}</button>
                <button className="btn-ghost" disabled={busy} onClick={() => loadSample(s.id, false)}>Load</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab !== "sample" && (
        <form className="card space-y-4" role="tabpanel" onSubmit={(e) => { e.preventDefault(); void submitMeeting(); }}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2"><label className="label" htmlFor="m-title">Meeting title</label>
              <input id="m-title" className="input" value={title} maxLength={200} placeholder="Weekly sync" onChange={(e) => setTitle(e.target.value)} /></div>
            <div><label className="label" htmlFor="m-date">Meeting date <span className="font-normal">(resolves “by Friday”)</span></label>
              <input id="m-date" type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} required /></div>
            <div><label className="label" htmlFor="m-tz">Timezone</label>
              <input id="m-tz" className="input" value={timezone} onChange={(e) => setTimezone(e.target.value)} /></div>
            <div className="sm:col-span-2"><label className="label" htmlFor="m-att">Attendees <span className="font-normal">(optional, comma-separated names or “Name &lt;email&gt;”)</span></label>
              <input id="m-att" className="input" value={attendees} placeholder="Priya, Marcus <marcus@example.com>, Dana" onChange={(e) => setAttendees(e.target.value)} /></div>
          </div>

          {tab === "paste" ? (
            <div>
              <label className="label" htmlFor="m-text">Transcript <span className="font-normal">· “Name: text” lines are parsed as speakers</span></label>
              <textarea id="m-text" className="input h-64 font-mono text-[13px]" value={transcript} onChange={(e) => { setTranscript(e.target.value); setSampleId(undefined); }} placeholder={"Priya: Okay, let's start. Marcus, can you fix the Safari bug by Friday?\nMarcus: Sure, I'll take it."} />
              <p className="mt-1 text-xs text-slate-500">{words} words{words > 0 && words < 8 ? " · too short to analyse" : ""}</p>
            </div>
          ) : (
            <div>
              <label className="label" htmlFor="m-file">Audio or video file ({EXTS.join(", ")} · up to {maxMb} MB)</label>
              <div className="rounded-xl border-2 border-dashed border-slate-300 p-6 text-center dark:border-slate-700"
                onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); setFile(e.dataTransfer.files?.[0] ?? null); }}>
                <input id="m-file" ref={fileRef} type="file" className="sr-only" accept={EXTS.join(",")} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                {file ? <p className="text-sm"><b>{file.name}</b> · {(file.size / 1048576).toFixed(1)} MB</p> : <p className="text-sm text-slate-500">Drop a file here or</p>}
                <button type="button" className="btn-ghost mt-2" onClick={() => fileRef.current?.click()}>Choose file</button>
              </div>
              <p className="mt-2 text-xs text-slate-500">Transcribed locally with Whisper ({health?.whisper.model ?? "base"}){health && !health.whisper.ffmpeg ? " · ⚠ ffmpeg not found on the server" : ""}. The first run downloads the model.</p>
            </div>
          )}

          {err && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{err}</p>}
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500">🔒 {health?.privacy ?? "Checking privacy mode…"}</p>
            <button className="btn-primary px-5 py-2" disabled={busy}>{busy ? "Starting…" : "Analyze meeting"}</button>
          </div>
        </form>
      )}
      {tab === "sample" && err && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{err}</p>}
      {tab === "sample" && <p className="text-xs text-slate-500">🔒 {health?.privacy}</p>}
    </div>
  );
}
