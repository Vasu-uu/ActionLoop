import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EmptyState, Skeleton } from "../components/Badges";
import { EmailsPanel } from "../components/EmailsPanel";
import { ExportsPanel } from "../components/ExportsPanel";
import { KanbanBoard } from "../components/KanbanBoard";
import { Overview } from "../components/Overview";
import { ProgressSteps } from "../components/ProgressSteps";
import { TaskModal, type TaskDraft } from "../components/TaskModal";
import { TranscriptViewer } from "../components/TranscriptViewer";
import { go } from "../hooks/useRoute";
import { useToast } from "../hooks/useToasts";
import { api } from "../lib/api";
import { filterTasks, findSegmentIndex, moveTask, ownersOf } from "../lib/format";
import type { Meeting, Task, TaskStatus, Tone } from "../lib/types";

type Tab = "overview" | "board" | "emails" | "transcript" | "export";
const TABS: [Tab, string][] = [["overview", "Overview"], ["board", "Board"], ["emails", "Emails"], ["transcript", "Transcript"], ["export", "Export"]];

export function MeetingPage({ id, onChanged }: { id: string; onChanged: () => void }) {
  const { toast } = useToast();
  const [m, setM] = useState<Meeting | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [owner, setOwner] = useState("");
  const [query, setQuery] = useState("");
  const [modal, setModal] = useState<{ task: Task | null; status?: TaskStatus } | null>(null);
  const [hl, setHl] = useState<{ seg: number | null; nonce: number }>({ seg: null, nonce: 0 });
  const searchRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const x = await api.meeting(id);
      setM(x); setTasks(x.tasks); setError(null);
      return x;
    } catch (e) { setError((e as Error).message); return null; }
  }, [id]);

  useEffect(() => {
    setM(null); setError(null); setTab("overview"); setOwner(""); setQuery("");
    let stop = () => {}, timer: number | undefined, cancelled = false;
    const poll = async () => {
      const x = await load();
      if (cancelled || !x) return;
      if (x.status !== "done" && x.status !== "error") timer = window.setTimeout(poll, 1500);
      else onChanged();
    };
    load().then((x) => {
      if (cancelled || !x || x.status === "done" || x.status === "error") return;
      stop = api.progress(id, (ev) => {
        setM((cur) => (cur ? { ...cur, status: ev.status as Meeting["status"], error: ev.error } : cur));
        if (ev.status === "done" || ev.status === "error") { void load().then(onChanged); }
      }, () => { timer = window.setTimeout(poll, 1500); });
    });
    return () => { cancelled = true; stop(); window.clearTimeout(timer); };
  }, [id, load, onChanged]);

  // keyboard shortcuts: "/" search, "n" new task, 1-5 switch tabs
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest("input,textarea,select,[contenteditable]") || e.metaKey || e.ctrlKey || m?.status !== "done" || modal) return;
      if (e.key === "/") { e.preventDefault(); setTab("board"); setTimeout(() => searchRef.current?.focus(), 0); }
      else if (e.key === "n") { e.preventDefault(); setTab("board"); setModal({ task: null }); }
      else if (/^[1-5]$/.test(e.key)) setTab(TABS[Number(e.key) - 1][0]);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [m?.status, modal]);

  const owners = useMemo(() => [...new Set([...ownersOf(tasks), ...(m?.attendees ?? []).map((a) => a.split("<")[0].trim())])].filter(Boolean), [tasks, m?.attendees]);
  const visible = useMemo(() => filterTasks(tasks, owner, query), [tasks, owner, query]);

  const jump = useCallback((seg: number | null, quote: string) => {
    if (!m) return;
    const idx = findSegmentIndex(quote, m.segments, seg);
    if (idx == null) toast("Could not locate that quote in the transcript.", "error");
    setHl((h) => ({ seg: idx, nonce: h.nonce + 1 }));
    setTab("transcript"); setModal(null);
  }, [m, toast]);

  const onMove = async (taskId: string, status: TaskStatus, index: number) => {
    const before = tasks;
    setTasks(moveTask(tasks, taskId, status, index));
    try { await api.patchTask(taskId, { status, position: index }); onChanged(); }
    catch (e) { setTasks(before); toast(`Could not move card: ${(e as Error).message}`, "error"); }
  };

  const save = async (d: TaskDraft, existing: Task | null) => {
    try {
      if (existing) {
        const patch: Record<string, unknown> = { title: d.title, description: d.description, priority: d.priority, status: d.status };
        if (d.owner.trim()) patch.owner = d.owner.trim(); else if (existing.owner) patch.clear_owner = true;
        if (d.deadline) patch.deadline_resolved = d.deadline; else if (existing.deadline_resolved) patch.clear_deadline = true;
        const t = await api.patchTask(existing.id, patch);
        setTasks((l) => l.map((x) => (x.id === t.id ? t : x)));
      } else {
        const t = await api.createTask({ meeting_id: id, title: d.title, description: d.description, owner: d.owner.trim() || null, deadline_resolved: d.deadline || null, priority: d.priority, ...({ status: d.status } as object) });
        setTasks((l) => [...l, t]);
      }
      setModal(null); onChanged(); toast("Task saved", "success");
    } catch (e) { toast((e as Error).message, "error"); }
  };
  const remove = async (t: Task) => {
    try { await api.deleteTask(t.id); setTasks((l) => l.filter((x) => x.id !== t.id)); setModal(null); onChanged(); toast("Task deleted", "success"); }
    catch (e) { toast((e as Error).message, "error"); }
  };

  if (error && !m) return <EmptyState title="Could not load this meeting"><p>{error}</p><button className="btn-primary mt-3" onClick={() => go("#/")}>Back to start</button></EmptyState>;
  if (!m) return <div className="space-y-3"><Skeleton className="h-8 w-1/2" /><Skeleton className="h-40" /><Skeleton className="h-40" /></div>;
  if (m.status === "error") {
    return (
      <div className="mx-auto max-w-xl"><div className="card border-red-300 dark:border-red-900" role="alert">
        <h2 className="text-lg font-semibold text-red-700 dark:text-red-300">We couldn’t finish analysing this meeting</h2>
        <p className="mt-2 text-sm">{m.error ?? "Unknown error."}</p>
        <div className="mt-4 flex gap-2"><button className="btn-primary" onClick={() => go("#/")}>Start over</button></div>
      </div></div>
    );
  }
  if (m.status !== "done") return <ProgressSteps status={m.status} source={m.source} />;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold">{m.title}</h1>
          <p className="text-sm text-slate-500">{m.date} · {m.attendees.length ? m.attendees.map((a) => a.split("<")[0].trim()).join(", ") : "attendees not provided"} · {tasks.length} tasks · AI: {m.provider}{m.language ? ` · ${m.language}` : ""}</p>
        </div>
        <div className="flex gap-2"><a className="btn-ghost" href={api.reportUrl(m.id)} target="_blank" rel="noreferrer">Shareable report</a><a className="btn-primary" href={api.exportUrl(m.id, "zip")}>⬇ ZIP</a></div>
      </header>

      <div role="tablist" aria-label="Sections" className="flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-800">
        {TABS.map(([t, label], i) => (
          <button key={t} role="tab" aria-selected={tab === t} title={`Shortcut: ${i + 1}`} onClick={() => setTab(t)}
            className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${tab === t ? "border-brand-600 text-brand-700 dark:text-brand-500" : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"}`}>{label}</button>
        ))}
      </div>

      {tab === "overview" && <Overview m={m} tasks={tasks} onJump={jump} onOpenTask={(t) => setModal({ task: t })} />}
      {tab === "board" && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <input ref={searchRef} className="input max-w-xs" type="search" placeholder="Search tasks  ( / )" aria-label="Search tasks" value={query} onChange={(e) => setQuery(e.target.value)} />
            <select className="input w-auto" aria-label="Filter by owner" value={owner} onChange={(e) => setOwner(e.target.value)}>
              <option value="">All owners</option><option value="__unassigned">Unassigned</option>
              {ownersOf(tasks).map((o) => <option key={o}>{o}</option>)}
            </select>
            <button className="btn-primary ml-auto" onClick={() => setModal({ task: null })}>+ Add task <kbd className="ml-1 rounded bg-white/20 px-1 text-[10px]">n</kbd></button>
          </div>
          <KanbanBoard tasks={visible} onMove={onMove} onOpen={(t) => setModal({ task: t })} onAdd={(s) => setModal({ task: null, status: s })} />
        </div>
      )}
      {tab === "emails" && <EmailsPanel meetingId={m.id} emails={m.emails} tone={m.tone} setTone={(t: Tone) => setM((c) => (c ? { ...c, tone: t } : c))} setEmails={(emails) => setM((c) => (c ? { ...c, emails } : c))} />}
      {tab === "transcript" && <TranscriptViewer segments={m.segments} highlight={hl.seg} nonce={hl.nonce} />}
      {tab === "export" && <ExportsPanel meetingId={m.id} />}

      {modal && (
        <TaskModal key={modal.task?.id ?? `new-${modal.status}`} task={modal.task} owners={owners} defaultStatus={modal.status}
          onClose={() => setModal(null)} onSave={save} onDelete={remove} onJump={(t) => jump(t.evidence_segment, t.evidence_quote)} />
      )}
    </div>
  );
}
