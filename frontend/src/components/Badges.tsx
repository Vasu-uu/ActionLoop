import type { ReactNode } from "react";
import { avatarColor, deadlineState, formatDeadline, initials } from "../lib/format";
import type { Level } from "../lib/types";

export function Avatar({ name, size = 28 }: { name: string | null; size?: number }) {
  return (
    <span
      title={name ?? "Unassigned"} aria-label={name ?? "Unassigned"}
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ${avatarColor(name)}`}
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >{initials(name)}</span>
  );
}

const PRIORITY: Record<Level, string> = {
  high: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  medium: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  low: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
};
export const PriorityChip = ({ level }: { level: Level }) => <span className={`chip ${PRIORITY[level]}`}>{level}</span>;

export function DeadlineChip({ iso, raw }: { iso: string | null; raw?: string | null }) {
  const s = deadlineState(iso);
  const cls = {
    overdue: "bg-red-600 text-white", soon: "bg-amber-400 text-amber-950",
    ok: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200", none: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400",
  }[s];
  const label = iso ? formatDeadline(iso) : raw ? `“${raw}”` : "No date";
  return (
    <span className={`chip ${cls}`} title={s === "overdue" ? "Overdue" : s === "soon" ? "Due within 2 days" : raw ?? ""}>
      {s === "overdue" && "⏰ "}{label}
    </span>
  );
}

export const UnverifiedBadge = () => (
  <span className="chip bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200" title="The evidence quote was not found in the transcript. Double-check this item.">
    ⚠ unverified
  </span>
);
export const ClarifyBadge = ({ reasons }: { reasons?: string[] }) => (
  <span className="chip bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200" title={reasons?.join("; ")}>? needs clarification</span>
);

export const Skeleton = ({ className = "h-4 w-full" }: { className?: string }) => (
  <div className={`animate-pulse rounded bg-slate-200 dark:bg-slate-800 ${className}`} aria-hidden="true" />
);

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
      <p className="font-medium text-slate-700 dark:text-slate-200">{title}</p>
      {children && <div className="mt-1">{children}</div>}
    </div>
  );
}
