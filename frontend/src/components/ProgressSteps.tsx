import type { MeetingStatus } from "../lib/types";

const STEPS: { id: MeetingStatus; label: string }[] = [
  { id: "transcribing", label: "Transcribing" },
  { id: "analyzing", label: "Analyzing" },
  { id: "drafting", label: "Drafting emails" },
  { id: "done", label: "Done" },
];

export function ProgressSteps({ status, source }: { status: MeetingStatus; source: string }) {
  const steps = source === "audio" ? STEPS : STEPS.filter((s) => s.id !== "transcribing");
  const current = Math.max(0, steps.findIndex((s) => s.id === status));
  return (
    <div className="card mx-auto max-w-xl" role="status" aria-live="polite">
      <h2 className="mb-4 text-lg font-semibold">Working on it…</h2>
      <ol className="space-y-3">
        {steps.map((s, i) => {
          const done = i < current || status === "done";
          const active = i === current && status !== "done";
          return (
            <li key={s.id} className="flex items-center gap-3 text-sm">
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs text-white ${done ? "bg-emerald-500" : active ? "animate-pulse bg-brand-600" : "bg-slate-300 dark:bg-slate-700"}`}>{done ? "✓" : i + 1}</span>
              <span className={active ? "font-semibold" : done ? "" : "text-slate-400"}>{s.label}{active && "…"}</span>
            </li>
          );
        })}
      </ol>
      {source === "audio" && <p className="mt-4 text-xs text-slate-500">Local Whisper transcription can take a while on CPU, and the first run downloads the model.</p>}
    </div>
  );
}
