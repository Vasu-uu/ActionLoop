import { useState } from "react";
import { api } from "../lib/api";
import { useToast } from "../hooks/useToasts";

const FILES = [
  { fmt: "md", label: "Markdown notes", desc: "Full meeting report" },
  { fmt: "csv", label: "CSV", desc: "Action items for spreadsheets" },
  { fmt: "ics", label: "Calendar (.ics)", desc: "All-day event per dated task" },
  { fmt: "json", label: "JSON", desc: "Complete structured result" },
  { fmt: "html", label: "HTML report", desc: "Standalone read-only page" },
];

export function ExportsPanel({ meetingId }: { meetingId: string }) {
  const { toast } = useToast();
  const [slack, setSlack] = useState<string | null>(null);
  const loadSlack = async () => {
    try { setSlack(await api.exportText(meetingId, "slack")); } catch (e) { toast((e as Error).message, "error"); }
  };
  const copySlack = async () => {
    try { await navigator.clipboard.writeText(slack ?? ""); toast("Slack text copied", "success"); } catch { toast("Copy failed", "error"); }
  };
  const share = async () => {
    const url = new URL(api.reportUrl(meetingId), window.location.origin).href;
    try { await navigator.clipboard.writeText(url); toast("Report link copied", "success"); } catch { toast(url, "info"); }
  };
  return (
    <div className="space-y-4">
      <div className="card">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold">Download</h2>
          <a className="btn-primary" href={api.exportUrl(meetingId, "zip")}>⬇ Download all as ZIP</a>
        </div>
        <ul className="grid gap-2 sm:grid-cols-2">
          {FILES.map((f) => (
            <li key={f.fmt}>
              <a href={api.exportUrl(meetingId, f.fmt)} className="flex items-center justify-between rounded-lg border border-slate-200 p-3 text-sm hover:border-brand-500 dark:border-slate-700">
                <span><b>{f.label}</b><br /><span className="text-xs text-slate-500">{f.desc}</span></span><span aria-hidden>⬇</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
      <div className="card">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold">Slack / Teams text</h2>
          <div className="flex gap-2">
            {slack === null ? <button className="btn-ghost" onClick={loadSlack}>Show</button> : <button className="btn-primary" onClick={copySlack}>Copy</button>}
          </div>
        </div>
        {slack !== null && <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs dark:bg-slate-950">{slack}</pre>}
      </div>
      <div className="card flex flex-wrap items-center justify-between gap-2">
        <div><h2 className="text-base font-semibold">Shareable report</h2><p className="text-xs text-slate-500">Read-only page. Anyone who can reach this server can open the link.</p></div>
        <div className="flex gap-2"><a className="btn-ghost" href={api.reportUrl(meetingId)} target="_blank" rel="noreferrer">Open</a><button className="btn-ghost" onClick={share}>Copy link</button></div>
      </div>
    </div>
  );
}
