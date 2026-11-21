import type { Segment, Task, TaskStatus } from "./types";

export type DeadlineState = "overdue" | "soon" | "ok" | "none";

function parseISO(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** overdue = before today; soon = today..2 days ahead (amber); ok = later; none = no date. */
export function deadlineState(iso: string | null, today: Date = new Date()): DeadlineState {
  if (!iso) return "none";
  const t0 = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const days = Math.round((parseISO(iso).getTime() - t0) / 86_400_000);
  if (days < 0) return "overdue";
  if (days <= 2) return "soon";
  return "ok";
}

export function formatDeadline(iso: string | null): string {
  if (!iso) return "No date";
  return parseISO(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function initials(name: string | null): string {
  if (!name) return "?";
  const parts = name.replace(/<.*>/, "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return (parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const PALETTE = ["bg-rose-500", "bg-orange-500", "bg-amber-600", "bg-emerald-600", "bg-teal-600", "bg-sky-600", "bg-indigo-600", "bg-fuchsia-600"];
export function avatarColor(name: string | null): string {
  if (!name) return "bg-slate-400";
  let h = 0;
  for (const ch of name.toLowerCase()) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export function formatTs(sec: number | null | undefined): string {
  if (sec == null) return "";
  const s = Math.floor(sec), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(r)}` : `${pad(m)}:${pad(r)}`;
}

export function filterTasks(tasks: Task[], owner: string, query: string): Task[] {
  const q = query.trim().toLowerCase();
  return tasks.filter((t) => {
    if (owner === "__unassigned" ? t.owner : owner && t.owner !== owner) return false;
    if (!q) return true;
    return [t.title, t.description, t.owner ?? "", t.evidence_quote].some((s) => s.toLowerCase().includes(q));
  });
}

export function groupByStatus(tasks: Task[]): Record<TaskStatus, Task[]> {
  const out: Record<TaskStatus, Task[]> = { todo: [], in_progress: [], done: [] };
  for (const t of tasks) out[t.status].push(t);
  for (const k of Object.keys(out) as TaskStatus[]) out[k].sort((a, b) => a.position - b.position);
  return out;
}

/** Pure optimistic version of the server's drag-and-drop reordering. */
export function moveTask(tasks: Task[], id: string, status: TaskStatus, index: number): Task[] {
  const moved = tasks.find((t) => t.id === id);
  if (!moved) return tasks;
  const col = (s: TaskStatus) => tasks.filter((t) => t.status === s && t.id !== id).sort((a, b) => a.position - b.position);
  const target = col(status);
  target.splice(Math.max(0, Math.min(index, target.length)), 0, { ...moved, status });
  const out = new Map<string, Task>();
  target.forEach((t, i) => out.set(t.id, { ...t, position: i }));
  if (moved.status !== status) col(moved.status).forEach((t, i) => out.set(t.id, { ...t, position: i }));
  return tasks.map((t) => out.get(t.id) ?? t);
}

export function ownersOf(tasks: Task[]): string[] {
  return [...new Set(tasks.map((t) => t.owner).filter((o): o is string => !!o))].sort();
}

export function normalizeText(s: string): string {
  return s.toLowerCase().replace(/[’‘']/g, "").replace(/[^\p{L}\p{N}\s]/gu, " ").replace(/\s+/g, " ").trim();
}

/** Find which transcript segment an evidence quote belongs to (uses server index when present). */
export function findSegmentIndex(quote: string, segments: Segment[], hint?: number | null): number | null {
  if (hint != null && segments.some((s) => s.idx === hint)) return hint;
  const q = normalizeText(quote);
  if (q.length < 6) return null;
  const hit = segments.find((s) => normalizeText(s.text).includes(q));
  return hit ? hit.idx : null;
}

export function mailto(to: string | null, subject: string, body: string): string {
  const max = 1800; // keep within common mailto length limits
  const b = body.length > max ? body.slice(0, max) + "\n…(truncated, use Copy for the full text)" : body;
  return `mailto:${encodeURIComponent(to ?? "")}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(b)}`;
}

export function workloadByOwner(tasks: Task[]): { owner: string; count: number }[] {
  const m = new Map<string, number>();
  for (const t of tasks) if (t.status !== "done") m.set(t.owner ?? "Unassigned", (m.get(t.owner ?? "Unassigned") ?? 0) + 1);
  return [...m].map(([owner, count]) => ({ owner, count })).sort((a, b) => b.count - a.count);
}

export const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
