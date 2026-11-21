import {
  DndContext, DragOverlay, KeyboardSensor, PointerSensor, closestCorners, pointerWithin, useDroppable, useSensor, useSensors,
  type CollisionDetection, type DragEndEvent, type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { groupByStatus } from "../lib/format";
import type { Task, TaskStatus } from "../lib/types";
import { Avatar, ClarifyBadge, DeadlineChip, EmptyState, PriorityChip, UnverifiedBadge } from "./Badges";

const COLUMNS: { id: TaskStatus; label: string; accent: string }[] = [
  { id: "todo", label: "To do", accent: "bg-slate-400" },
  { id: "in_progress", label: "In progress", accent: "bg-brand-500" },
  { id: "done", label: "Done", accent: "bg-emerald-500" },
];

/** Prefer what the pointer is over (a card, else a column); fall back to nearest corners for keyboard drags. */
const collide: CollisionDetection = (args) => {
  const within = pointerWithin(args);
  if (within.length) {
    const card = within.find((c) => !COLUMNS.some((col) => col.id === c.id));
    return card ? [card] : within;
  }
  return closestCorners(args);
};

function CardBody({ task }: { task: Task }) {
  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className={`text-sm font-medium leading-snug ${task.status === "done" ? "text-slate-500 line-through" : ""}`}>{task.title}</p>
        <Avatar name={task.owner} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <DeadlineChip iso={task.deadline_resolved} raw={task.deadline_raw} />
        <PriorityChip level={task.priority} />
        {task.needs_clarification && <ClarifyBadge reasons={task.clarification_reasons} />}
        {!task.verified && <UnverifiedBadge />}
      </div>
    </>
  );
}

function Card({ task, onOpen }: { task: Task; onOpen: (t: Task) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id });
  return (
    <div
      ref={setNodeRef} {...attributes} {...listeners}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 }}
      onClick={() => onOpen(task)}
      onKeyDown={(e) => { if (e.key === "Enter") onOpen(task); listeners?.onKeyDown?.(e); }}
      aria-label={`Task: ${task.title}. Press Enter to edit, Space to drag.`}
      className="cursor-grab rounded-lg border border-slate-200 bg-white p-3 shadow-sm hover:border-brand-500 active:cursor-grabbing dark:border-slate-700 dark:bg-slate-900"
    >
      <CardBody task={task} />
    </div>
  );
}

function Column({ id, label, accent, tasks, onOpen, onAdd }: { id: TaskStatus; label: string; accent: string; tasks: Task[]; onOpen: (t: Task) => void; onAdd: (s: TaskStatus) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <section ref={setNodeRef} className={`flex min-h-[240px] flex-col rounded-xl bg-slate-100 p-2 dark:bg-slate-900/60 ${isOver ? "ring-2 ring-brand-500" : ""}`} aria-label={label}>
      <header className="mb-2 flex items-center justify-between px-1">
        <h3 className="flex items-center gap-2 text-sm font-semibold"><span className={`h-2 w-2 rounded-full ${accent}`} />{label}<span className="text-xs font-normal text-slate-500">{tasks.length}</span></h3>
        <button className="rounded px-1.5 text-lg leading-none text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-800" onClick={() => onAdd(id)} aria-label={`Add task to ${label}`}>+</button>
      </header>
      <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        <div className="flex flex-1 flex-col gap-2">
          {tasks.map((t) => <Card key={t.id} task={t} onOpen={onOpen} />)}
          {!tasks.length && <p className="m-auto py-6 text-xs text-slate-400">Drop cards here</p>}
        </div>
      </SortableContext>
    </section>
  );
}

export function KanbanBoard({ tasks, onMove, onOpen, onAdd }: {
  tasks: Task[]; onMove: (id: string, status: TaskStatus, index: number) => void; onOpen: (t: Task) => void; onAdd: (s: TaskStatus) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const [active, setActive] = useState<Task | null>(null);
  const grouped = groupByStatus(tasks);

  const end = (e: DragEndEvent) => {
    setActive(null);
    const { active: a, over } = e;
    if (!over) return;
    const overId = String(over.id);
    const col = COLUMNS.find((c) => c.id === overId);
    if (col) return onMove(String(a.id), col.id, grouped[col.id].filter((t) => t.id !== a.id).length);
    const overTask = tasks.find((t) => t.id === overId);
    if (!overTask || overTask.id === a.id) return;
    onMove(String(a.id), overTask.status, grouped[overTask.status].findIndex((t) => t.id === overId));
  };

  if (!tasks.length) return <EmptyState title="No tasks match">Adjust the filters or add a card with “+”.</EmptyState>;
  return (
    <DndContext sensors={sensors} collisionDetection={collide}
      onDragStart={(e: DragStartEvent) => setActive(tasks.find((t) => t.id === e.active.id) ?? null)} onDragEnd={end} onDragCancel={() => setActive(null)}>
      <div className="grid gap-3 md:grid-cols-3">
        {COLUMNS.map((c) => <Column key={c.id} {...c} tasks={grouped[c.id]} onOpen={onOpen} onAdd={onAdd} />)}
      </div>
      <DragOverlay>{active && <div className="rounded-lg border border-brand-500 bg-white p-3 shadow-xl dark:bg-slate-900"><CardBody task={active} /></div>}</DragOverlay>
    </DndContext>
  );
}
