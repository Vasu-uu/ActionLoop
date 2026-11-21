import { useEffect, useRef, useState } from "react";
import type { Level, Task, TaskStatus } from "../lib/types";
import { formatTs } from "../lib/format";
import { ClarifyBadge, UnverifiedBadge } from "./Badges";

export interface TaskDraft {
  title: string; description: string; owner: string; deadline: string; priority: Level; status: TaskStatus;
}

export function TaskModal({ task, owners, defaultStatus, onClose, onSave, onDelete, onJump }: {
  task: Task | null; owners: string[]; defaultStatus?: TaskStatus; onClose: () => void;
  onSave: (d: TaskDraft, existing: Task | null) => Promise<void>; onDelete: (t: Task) => Promise<void>; onJump: (t: Task) => void;
}) {
  const [d, setD] = useState<TaskDraft>({
    title: task?.title ?? "", description: task?.description ?? "", owner: task?.owner ?? "",
    deadline: task?.deadline_resolved ?? "", priority: task?.priority ?? "medium", status: task?.status ?? defaultStatus ?? "todo",
  });
  const [busy, setBusy] = useState(false);
  const first = useRef<HTMLInputElement>(null);
  useEffect(() => {
    first.current?.focus();
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  const set = <K extends keyof TaskDraft>(k: K, v: TaskDraft[K]) => setD((s) => ({ ...s, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!d.title.trim()) return;
    setBusy(true);
    try { await onSave(d, task); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form onSubmit={submit} role="dialog" aria-modal="true" aria-label={task ? "Edit task" : "New task"}
        className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-white p-5 shadow-2xl dark:bg-slate-900 sm:rounded-2xl">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{task ? "Edit task" : "New task"}</h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Close">✕</button>
        </div>
        {task && (task.needs_clarification || !task.verified) && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {task.needs_clarification && <ClarifyBadge reasons={task.clarification_reasons} />}
            {!task.verified && <UnverifiedBadge />}
            <p className="w-full text-xs text-slate-500">{task.clarification_reasons.join(" · ")}</p>
          </div>
        )}
        <label className="label" htmlFor="t-title">Title</label>
        <input id="t-title" ref={first} className="input mb-3" value={d.title} onChange={(e) => set("title", e.target.value)} maxLength={300} required />
        <label className="label" htmlFor="t-desc">Description</label>
        <textarea id="t-desc" className="input mb-3" rows={3} value={d.description} onChange={(e) => set("description", e.target.value)} />
        <div className="mb-3 grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="t-owner">Owner</label>
            <input id="t-owner" className="input" list="owner-list" value={d.owner} placeholder="Unassigned" onChange={(e) => set("owner", e.target.value)} />
            <datalist id="owner-list">{owners.map((o) => <option key={o} value={o} />)}</datalist>
          </div>
          <div>
            <label className="label" htmlFor="t-date">Deadline</label>
            <input id="t-date" type="date" className="input" value={d.deadline} onChange={(e) => set("deadline", e.target.value)} />
            {task?.deadline_raw && <p className="mt-1 text-xs text-slate-500">Said: “{task.deadline_raw}”</p>}
          </div>
          <div>
            <label className="label" htmlFor="t-prio">Priority</label>
            <select id="t-prio" className="input" value={d.priority} onChange={(e) => set("priority", e.target.value as Level)}>
              <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="t-status">Status</label>
            <select id="t-status" className="input" value={d.status} onChange={(e) => set("status", e.target.value as TaskStatus)}>
              <option value="todo">To do</option><option value="in_progress">In progress</option><option value="done">Done</option>
            </select>
          </div>
        </div>
        {task?.evidence_quote && (
          <blockquote className="mb-3 rounded-lg border-l-4 border-brand-500 bg-slate-50 p-3 text-sm italic dark:bg-slate-800">
            “{task.evidence_quote}”
            <div className="mt-1 flex items-center gap-3 text-xs not-italic text-slate-500">
              {task.evidence_timestamp != null && <span>@ {formatTs(task.evidence_timestamp)}</span>}
              <button type="button" className="font-medium text-brand-600 hover:underline dark:text-brand-500" onClick={() => onJump(task)}>Jump to transcript →</button>
            </div>
          </blockquote>
        )}
        <div className="flex items-center justify-between gap-2">
          {task ? (
            <button type="button" className="btn text-red-600 hover:bg-red-50 dark:hover:bg-red-950" disabled={busy}
              onClick={async () => { if (confirm("Delete this task?")) { setBusy(true); try { await onDelete(task); } finally { setBusy(false); } } }}>Delete</button>
          ) : <span />}
          <div className="flex gap-2">
            <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={busy || !d.title.trim()}>{busy ? "Saving…" : "Save"}</button>
          </div>
        </div>
      </form>
    </div>
  );
}
