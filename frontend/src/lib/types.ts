export type Level = "high" | "medium" | "low";
export type TaskStatus = "todo" | "in_progress" | "done";
export type Tone = "professional" | "friendly" | "concise";
export type MeetingStatus = "queued" | "transcribing" | "analyzing" | "drafting" | "done" | "error";

export interface Segment { idx: number; start: number | null; end: number | null; speaker: string | null; text: string }
export interface Task {
  id: string; meeting_id: string; title: string; description: string; owner: string | null; owner_confidence: Level;
  deadline_raw: string | null; deadline_resolved: string | null; priority: Level; status: TaskStatus;
  evidence_quote: string; evidence_timestamp: number | null; evidence_segment: number | null; verified: boolean;
  manual: boolean; position: number; needs_clarification: boolean; clarification_reasons: string[];
}
export interface Decision { id: string; decision: string; rationale: string | null; evidence_quote: string; evidence_timestamp: number | null; evidence_segment: number | null; verified: boolean }
export interface OpenQuestion { id: string; question: string; suggested_owner: string | null }
export interface Risk { id: string; risk: string; severity: Level }
export interface Email { id: string; meeting_id: string; kind: "recap" | "owner"; recipient: string | null; to_addr: string | null; tone: Tone; subject: string; body_text: string; body_html: string; edited: boolean }
export interface Meeting {
  id: string; title: string; date: string; timezone: string; attendees: string[]; status: MeetingStatus; error: string | null;
  source: string; provider: string; language: string | null; tone: Tone; transcript: string; segments: Segment[];
  summary: { bullets: string[]; paragraph: string } | null; decisions: Decision[]; open_questions: OpenQuestion[];
  risks: Risk[]; topics: string[]; warnings: string[]; tasks: Task[]; emails: Email[];
}
export interface MeetingSummary { id: string; title: string; date: string; status: MeetingStatus; source: string; open_tasks: number; total_tasks: number; overdue_tasks: number; created_at: string }
export interface Dashboard { meetings: number; open_tasks: number; overdue_tasks: number; workload: Record<string, number> }
export interface Health {
  status: string; version: string; llm: { provider: string; model: string; local: boolean; demo: boolean };
  whisper: { model: string; ffmpeg: boolean }; privacy: string; max_upload_mb: number;
}
export interface Sample { id: string; title: string; description: string; attendees: string[]; transcript?: string; date?: string }
