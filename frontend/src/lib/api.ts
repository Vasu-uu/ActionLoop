import type { Dashboard, Email, Health, Meeting, MeetingSummary, Sample, Task, Tone } from "./types";

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("network", "Cannot reach the ActionLoop server. Is the backend running on port 8000?", 0);
  }
  if (!res.ok) {
    let code = "error", message = `Request failed (${res.status})`;
    try { const j = await res.json(); code = j.error?.code ?? code; message = j.error?.message ?? message; } catch { /* non-JSON */ }
    throw new ApiError(code, message, res.status);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const json = (method: string, body: unknown): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export interface NewMeeting { title: string; date: string; attendees: string; timezone: string; transcript: string; tone: Tone; sample_id?: string }

export const api = {
  health: () => req<Health>("/api/health"),
  samples: () => req<Sample[]>("/api/samples"),
  sample: (id: string) => req<Sample>(`/api/samples/${id}`),
  dashboard: () => req<Dashboard>("/api/dashboard"),
  meetings: () => req<MeetingSummary[]>("/api/meetings"),
  meeting: (id: string) => req<Meeting>(`/api/meetings/${id}`),
  createMeeting: (b: NewMeeting) => req<Meeting>("/api/meetings", json("POST", b)),
  createFromAudio: (file: File, meta: Omit<NewMeeting, "transcript" | "sample_id">) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", meta.title); fd.append("date", meta.date); fd.append("attendees", meta.attendees);
    fd.append("timezone", meta.timezone); fd.append("tone", meta.tone);
    return req<Meeting>("/api/meetings/audio", { method: "POST", body: fd });
  },
  renameMeeting: (id: string, title: string) => req<Meeting>(`/api/meetings/${id}`, json("PATCH", { title })),
  deleteMeeting: (id: string) => req<void>(`/api/meetings/${id}`, { method: "DELETE" }),
  patchTask: (id: string, patch: Record<string, unknown>) => req<Task>(`/api/tasks/${id}`, json("PATCH", patch)),
  createTask: (b: { meeting_id: string; title: string; owner?: string | null; deadline_resolved?: string | null; priority?: string; description?: string }) =>
    req<Task>("/api/tasks", json("POST", b)),
  deleteTask: (id: string) => req<void>(`/api/tasks/${id}`, { method: "DELETE" }),
  regenerateEmails: (id: string, tone: Tone) => req<Email[]>(`/api/meetings/${id}/emails?tone=${tone}`, { method: "POST" }),
  regenerateEmail: (id: string, tone: Tone) => req<Email>(`/api/emails/${id}/regenerate?tone=${tone}`, { method: "POST" }),
  patchEmail: (id: string, patch: Partial<Pick<Email, "subject" | "body_text" | "to_addr">>) => req<Email>(`/api/emails/${id}`, json("PATCH", patch)),
  exportUrl: (id: string, fmt: string) => `/api/meetings/${id}/export/${fmt}`,
  exportText: async (id: string, fmt: string) => {
    const res = await fetch(`/api/meetings/${id}/export/${fmt}`);
    if (!res.ok) throw new ApiError("export", "Export failed.", res.status);
    return res.text();
  },
  reportUrl: (id: string) => `/m/${id}`,
  /** Subscribe to processing progress via Server-Sent Events; returns an unsubscribe function. */
  progress: (id: string, onEvent: (e: { status: string; error: string | null }) => void, onFail: () => void) => {
    const es = new EventSource(`/api/meetings/${id}/progress`);
    es.onmessage = (m) => {
      const data = JSON.parse(m.data);
      onEvent(data);
      if (data.status === "done" || data.status === "error") es.close();
    };
    es.onerror = () => { es.close(); onFail(); };
    return () => es.close();
  },
};
