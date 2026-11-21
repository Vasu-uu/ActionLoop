import { describe, expect, it } from "vitest";
import { avatarColor, deadlineState, filterTasks, findSegmentIndex, formatTs, groupByStatus, initials, mailto, moveTask, workloadByOwner } from "../lib/format";
import type { Segment, Task } from "../lib/types";

const today = new Date(2026, 2, 11);
const mk = (o: Partial<Task>): Task => ({
  id: "1", meeting_id: "m", title: "T", description: "", owner: null, owner_confidence: "low", deadline_raw: null,
  deadline_resolved: null, priority: "medium", status: "todo", evidence_quote: "", evidence_timestamp: null,
  evidence_segment: null, verified: true, manual: false, position: 0, needs_clarification: false, clarification_reasons: [], ...o,
});

describe("deadlineState", () => {
  it("flags overdue red, within 2 days amber, later ok, none", () => {
    expect(deadlineState("2026-03-10", today)).toBe("overdue");
    expect(deadlineState("2026-03-11", today)).toBe("soon");
    expect(deadlineState("2026-03-13", today)).toBe("soon");
    expect(deadlineState("2026-03-14", today)).toBe("ok");
    expect(deadlineState(null, today)).toBe("none");
  });
});

describe("avatars and timestamps", () => {
  it("builds initials", () => {
    expect(initials("Ada Lovelace")).toBe("AL");
    expect(initials("marcus")).toBe("MA");
    expect(initials("Jo <jo@x.io>")).toBe("JO");
    expect(initials(null)).toBe("?");
  });
  it("is stable per name", () => expect(avatarColor("Dana")).toBe(avatarColor("dana")));
  it("formats timestamps", () => {
    expect(formatTs(65)).toBe("01:05");
    expect(formatTs(3725)).toBe("1:02:05");
    expect(formatTs(null)).toBe("");
  });
});

describe("board helpers", () => {
  const tasks = [
    mk({ id: "a", title: "Fix bug", owner: "Ann", status: "todo", position: 1 }),
    mk({ id: "b", title: "Write docs", owner: "Bob", status: "todo", position: 0 }),
    mk({ id: "c", title: "Ship", owner: null, status: "done" }),
  ];
  it("groups by status ordered by position", () => {
    const g = groupByStatus(tasks);
    expect(g.todo.map((t) => t.id)).toEqual(["b", "a"]);
    expect(g.done).toHaveLength(1);
  });
  it("filters by owner and search", () => {
    expect(filterTasks(tasks, "Ann", "").map((t) => t.id)).toEqual(["a"]);
    expect(filterTasks(tasks, "__unassigned", "").map((t) => t.id)).toEqual(["c"]);
    expect(filterTasks(tasks, "", "DOCS").map((t) => t.id)).toEqual(["b"]);
  });
  it("computes open workload per owner", () => {
    expect(workloadByOwner(tasks)).toEqual([{ owner: "Ann", count: 1 }, { owner: "Bob", count: 1 }]);
  });
});

describe("moveTask (kanban optimistic update)", () => {
  const ts = [
    mk({ id: "a", status: "todo", position: 0 }), mk({ id: "b", status: "todo", position: 1 }),
    mk({ id: "c", status: "todo", position: 2 }), mk({ id: "d", status: "done", position: 0 }),
  ];
  const ids = (l: Task[], s: string) => l.filter((t) => t.status === s).sort((x, y) => x.position - y.position).map((t) => t.id);
  it("reorders within a column", () => {
    expect(ids(moveTask(ts, "a", "todo", 2), "todo")).toEqual(["b", "c", "a"]);
    expect(ids(moveTask(ts, "c", "todo", 0), "todo")).toEqual(["c", "a", "b"]);
  });
  it("moves across columns and renumbers both", () => {
    const r = moveTask(ts, "a", "done", 0);
    expect(ids(r, "done")).toEqual(["a", "d"]);
    expect(r.filter((t) => t.status === "todo").map((t) => t.position).sort()).toEqual([0, 1]);
  });
  it("ignores unknown ids and clamps index", () => {
    expect(moveTask(ts, "zzz", "done", 0)).toBe(ts);
    expect(ids(moveTask(ts, "a", "in_progress", 99), "in_progress")).toEqual(["a"]);
  });
});

describe("evidence → transcript segment", () => {
  const segs: Segment[] = [
    { idx: 0, start: null, end: null, speaker: "Ann", text: "I'll look at the Safari focus bug by tomorrow." },
    { idx: 1, start: null, end: null, speaker: "Bob", text: "Great." },
  ];
  it("prefers the server hint", () => expect(findSegmentIndex("x", segs, 1)).toBe(1));
  it("falls back to normalised text matching", () => {
    expect(findSegmentIndex("ill look at the safari focus bug", segs)).toBe(0);
    expect(findSegmentIndex("nothing like it", segs)).toBeNull();
  });
});

describe("mailto", () => {
  it("encodes and truncates", () => {
    const m = mailto("a@b.co", "Hi & bye", "x".repeat(3000));
    expect(m.startsWith("mailto:a%40b.co?subject=Hi%20%26%20bye&body=")).toBe(true);
    expect(m.length).toBeLessThan(2200);
  });
});
