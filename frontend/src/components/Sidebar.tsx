import { useState } from "react";
import { api } from "../lib/api";
import { go } from "../hooks/useRoute";
import { useToast } from "../hooks/useToasts";
import type { Dashboard, Health, MeetingSummary } from "../lib/types";
import { Skeleton } from "./Badges";

export function Sidebar({ meetings, dashboard, health, currentId, loading, onChanged, dark, toggleTheme }: {
  meetings: MeetingSummary[] | null; dashboard: Dashboard | null; health: Health | null; currentId?: string; loading: boolean;
  onChanged: () => void; dark: boolean; toggleTheme: () => void;
}) {
  const { toast } = useToast();
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");

  const rename = async (id: string) => {
    const t = name.trim();
    setEditing(null);
    if (!t) return;
    try { await api.renameMeeting(id, t); onChanged(); } catch (e) { toast((e as Error).message, "error"); }
  };
  const remove = async (m: MeetingSummary) => {
    if (!confirm(`Delete “${m.title}” and its tasks? This cannot be undone.`)) return;
    try { await api.deleteMeeting(m.id); toast("Meeting deleted", "success"); if (m.id === currentId) go("#/"); onChanged(); }
    catch (e) { toast((e as Error).message, "error"); }
  };

  return (
    <aside className="flex h-full w-full flex-col gap-4 overflow-y-auto border-r border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900" aria-label="Meetings">
      <div className="flex items-center justify-between">
        <a href="#/" className="flex items-center gap-2 text-lg font-bold">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">✓</span>ActionLoop
        </a>
        <button onClick={toggleTheme} className="btn-ghost px-2" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} title="Toggle theme">{dark ? "☀️" : "🌙"}</button>
      </div>
      <a href="#/" className="btn-primary">+ New meeting</a>

      <div className="grid grid-cols-2 gap-2 text-center" aria-label="Dashboard">
        {dashboard ? (
          <>
            <div className="rounded-lg bg-slate-100 p-2 dark:bg-slate-800"><div className="text-xl font-bold">{dashboard.open_tasks}</div><div className="text-xs text-slate-500">open actions</div></div>
            <div className={`rounded-lg p-2 ${dashboard.overdue_tasks ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200" : "bg-slate-100 dark:bg-slate-800"}`}><div className="text-xl font-bold">{dashboard.overdue_tasks}</div><div className="text-xs opacity-80">overdue</div></div>
          </>
        ) : <><Skeleton className="h-14" /><Skeleton className="h-14" /></>}
      </div>

      <nav className="min-h-0 flex-1">
        <h2 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">History</h2>
        {loading && <div className="space-y-2"><Skeleton className="h-9" /><Skeleton className="h-9" /><Skeleton className="h-9" /></div>}
        {!loading && !meetings?.length && <p className="text-sm text-slate-500">No meetings yet. Try a sample!</p>}
        <ul className="space-y-1">
          {meetings?.map((m) => (
            <li key={m.id} className={`group rounded-lg ${m.id === currentId ? "bg-brand-50 dark:bg-brand-700/20" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`}>
              {editing === m.id ? (
                <input autoFocus className="input" value={name} aria-label="Meeting title" onChange={(e) => setName(e.target.value)} onBlur={() => rename(m.id)}
                  onKeyDown={(e) => { if (e.key === "Enter") rename(m.id); if (e.key === "Escape") setEditing(null); }} />
              ) : (
                <div className="flex items-center gap-1 pr-1">
                  <a href={`#/meeting/${m.id}`} className="min-w-0 flex-1 px-2 py-1.5">
                    <div className="truncate text-sm font-medium">{m.title}</div>
                    <div className="text-xs text-slate-500">{m.date} · {m.status === "done" ? `${m.open_tasks} open` : m.status}{m.overdue_tasks ? <span className="text-red-600"> · {m.overdue_tasks} overdue</span> : null}</div>
                  </a>
                  <button className="rounded p-1 text-xs text-slate-400 opacity-0 hover:bg-slate-200 focus:opacity-100 group-hover:opacity-100 dark:hover:bg-slate-700" aria-label={`Rename ${m.title}`} onClick={() => { setEditing(m.id); setName(m.title); }}>✎</button>
                  <button className="rounded p-1 text-xs text-slate-400 opacity-0 hover:bg-red-100 hover:text-red-600 focus:opacity-100 group-hover:opacity-100" aria-label={`Delete ${m.title}`} onClick={() => remove(m)}>🗑</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </nav>

      <div className="rounded-lg border border-slate-200 p-2 text-xs dark:border-slate-700" aria-label="AI provider">
        {health ? (
          <>
            <div className="flex items-center gap-1.5 font-medium"><span className={`h-2 w-2 rounded-full ${health.llm.demo ? "bg-amber-500" : "bg-emerald-500"}`} />AI: {health.llm.provider}{health.llm.demo && " (demo mode)"}</div>
            <div className="mt-1 text-slate-500">🔒 {health.privacy}</div>
          </>
        ) : <span className="text-slate-500">Connecting to server…</span>}
      </div>
    </aside>
  );
}
