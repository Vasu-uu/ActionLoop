import { workloadByOwner } from "../lib/format";
import type { Meeting, Task } from "../lib/types";
import { Avatar, PriorityChip, UnverifiedBadge } from "./Badges";

function Quote({ text, onJump, verified }: { text: string; onJump: () => void; verified: boolean }) {
  return (
    <button onClick={onJump} className="mt-1 block max-w-full text-left text-xs italic text-slate-500 hover:text-brand-600 dark:text-slate-400" title="Jump to this moment in the transcript">
      “{text}” <span className="not-italic text-brand-600 dark:text-brand-500">→ transcript</span> {!verified && <UnverifiedBadge />}
    </button>
  );
}

export function WorkloadChart({ tasks }: { tasks: Task[] }) {
  const data = workloadByOwner(tasks);
  const max = Math.max(1, ...data.map((d) => d.count));
  if (!data.length) return <p className="text-sm text-slate-500">All tasks are done 🎉</p>;
  return (
    <ul className="space-y-2" aria-label="Open tasks per owner">
      {data.map((d) => (
        <li key={d.owner} className="flex items-center gap-2 text-sm">
          <Avatar name={d.owner === "Unassigned" ? null : d.owner} size={22} />
          <span className="w-24 shrink-0 truncate">{d.owner}</span>
          <div className="h-3 flex-1 rounded bg-slate-100 dark:bg-slate-800"><div className="h-3 rounded bg-brand-500" style={{ width: `${(d.count / max) * 100}%` }} /></div>
          <span className="w-5 text-right tabular-nums">{d.count}</span>
        </li>
      ))}
    </ul>
  );
}

export function ClarificationPanel({ tasks, onOpen }: { tasks: Task[]; onOpen: (t: Task) => void }) {
  const flagged = tasks.filter((t) => t.needs_clarification && t.status !== "done");
  if (!flagged.length) return null;
  return (
    <section className="card border-violet-300 bg-violet-50/60 dark:border-violet-900 dark:bg-violet-950/30" aria-labelledby="clarify-h">
      <h2 id="clarify-h" className="mb-1 text-base font-semibold">❓ Needs clarification ({flagged.length})</h2>
      <p className="mb-3 text-xs text-slate-600 dark:text-slate-400">ActionLoop never guesses owners or deadlines. Click an item to fill the gaps.</p>
      <ul className="divide-y divide-violet-200 dark:divide-violet-900">
        {flagged.map((t) => (
          <li key={t.id}>
            <button className="flex w-full items-start justify-between gap-3 py-2 text-left hover:bg-violet-100/60 dark:hover:bg-violet-900/30" onClick={() => onOpen(t)}>
              <span className="text-sm font-medium">{t.title}</span>
              <span className="shrink-0 text-right text-xs text-violet-800 dark:text-violet-200">{t.clarification_reasons.join(" · ")}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Overview({ m, tasks, onJump, onOpenTask }: { m: Meeting; tasks: Task[]; onJump: (seg: number | null, quote: string) => void; onOpenTask: (t: Task) => void }) {
  return (
    <div className="space-y-4">
      {m.warnings.map((w) => <div key={w} className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">⚠ {w}</div>)}
      <section className="card">
        <h2 className="mb-2 text-base font-semibold">Summary</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">{m.summary?.bullets.map((b) => <li key={b}>{b}</li>)}</ul>
        {m.summary?.paragraph && <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{m.summary.paragraph}</p>}
        {!!m.topics.length && <div className="mt-3 flex flex-wrap gap-1.5">{m.topics.map((t) => <span key={t} className="chip bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">#{t}</span>)}</div>}
      </section>
      <ClarificationPanel tasks={tasks} onOpen={onOpenTask} />
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-2 text-base font-semibold">✅ Decisions ({m.decisions.length})</h2>
          {m.decisions.length ? (
            <ul className="space-y-3">
              {m.decisions.map((d) => (
                <li key={d.id} className="text-sm">
                  <p className="font-medium">{d.decision}</p>
                  {d.rationale && <p className="text-slate-600 dark:text-slate-400">{d.rationale}</p>}
                  <Quote text={d.evidence_quote} verified={d.verified} onJump={() => onJump(d.evidence_segment, d.evidence_quote)} />
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate-500">No explicit decisions were found.</p>}
        </section>
        <section className="card">
          <h2 className="mb-2 text-base font-semibold">📋 Action items ({tasks.length})</h2>
          <ul className="space-y-3">
            {tasks.map((t) => (
              <li key={t.id} className="text-sm">
                <div className="flex items-center justify-between gap-2">
                  <button className="text-left font-medium hover:text-brand-600" onClick={() => onOpenTask(t)}>{t.title}</button>
                  <PriorityChip level={t.priority} />
                </div>
                <p className="text-xs text-slate-500">{t.owner ?? "Unassigned"} · {t.deadline_resolved ?? t.deadline_raw ?? "no deadline"}</p>
                {t.evidence_quote && <Quote text={t.evidence_quote} verified={t.verified} onJump={() => onJump(t.evidence_segment, t.evidence_quote)} />}
              </li>
            ))}
          </ul>
        </section>
        <section className="card">
          <h2 className="mb-2 text-base font-semibold">❓ Open questions ({m.open_questions.length})</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {m.open_questions.map((q) => <li key={q.id}>{q.question}{q.suggested_owner && <span className="text-slate-500"> — suggested: {q.suggested_owner}</span>}</li>)}
            {!m.open_questions.length && <li className="list-none text-slate-500">None.</li>}
          </ul>
        </section>
        <section className="card">
          <h2 className="mb-2 text-base font-semibold">⚠ Risks ({m.risks.length})</h2>
          <ul className="space-y-1.5 text-sm">
            {m.risks.map((r) => <li key={r.id} className="flex items-start gap-2"><PriorityChip level={r.severity} /><span>{r.risk}</span></li>)}
            {!m.risks.length && <li className="text-slate-500">None.</li>}
          </ul>
        </section>
        <section className="card lg:col-span-2">
          <h2 className="mb-3 text-base font-semibold">Workload (open tasks per person)</h2>
          <WorkloadChart tasks={tasks} />
        </section>
      </div>
    </div>
  );
}
