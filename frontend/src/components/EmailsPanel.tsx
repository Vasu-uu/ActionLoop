import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { mailto } from "../lib/format";
import type { Email, Tone } from "../lib/types";
import { useToast } from "../hooks/useToasts";
import { EmptyState } from "./Badges";

function EmailCard({ email, tone, onChange }: { email: Email; tone: Tone; onChange: (e: Email) => void }) {
  const { toast } = useToast();
  const [subject, setSubject] = useState(email.subject);
  const [body, setBody] = useState(email.body_text);
  const [to, setTo] = useState(email.to_addr ?? "");
  const [html, setHtml] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setSubject(email.subject); setBody(email.body_text); setTo(email.to_addr ?? ""); }, [email]);
  const dirty = subject !== email.subject || body !== email.body_text || to !== (email.to_addr ?? "");

  const save = async () => {
    setBusy(true);
    try { onChange(await api.patchEmail(email.id, { subject, body_text: body, to_addr: to || null as unknown as string })); toast("Draft saved", "success"); }
    catch (e) { toast((e as Error).message, "error"); } finally { setBusy(false); }
  };
  const regen = async () => {
    if (dirty && !confirm("Regenerating discards your edits to this draft. Continue?")) return;
    setBusy(true);
    try { onChange(await api.regenerateEmail(email.id, tone)); toast("Draft regenerated", "success"); }
    catch (e) { toast((e as Error).message, "error"); } finally { setBusy(false); }
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`); toast("Copied to clipboard", "success"); }
    catch { toast("Copy failed. Select the text and copy manually.", "error"); }
  };

  return (
    <article className="card space-y-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{email.kind === "recap" ? "📣 Team recap" : `✉️ For ${email.recipient}`}{email.edited && <span className="ml-2 chip bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">edited</span>}</h3>
        <div className="flex flex-wrap gap-1.5">
          <button className="btn-ghost" onClick={() => setHtml((v) => !v)}>{html ? "Plain text" : "HTML preview"}</button>
          <button className="btn-ghost" onClick={regen} disabled={busy}>↻ Regenerate</button>
          <button className="btn-ghost" onClick={copy}>Copy</button>
          <a className="btn-primary" href={mailto(to || null, subject, body)}>Open in mail app</a>
        </div>
      </header>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="sm:col-span-1"><label className="label" htmlFor={`to-${email.id}`}>To</label>
          <input id={`to-${email.id}`} className="input" value={to} onChange={(e) => setTo(e.target.value)} placeholder="(add an address)" type="email" /></div>
        <div className="sm:col-span-2"><label className="label" htmlFor={`s-${email.id}`}>Subject</label>
          <input id={`s-${email.id}`} className="input" value={subject} onChange={(e) => setSubject(e.target.value)} /></div>
      </div>
      {html ? (
        <iframe title="HTML preview" sandbox="" srcDoc={email.body_html} className="h-72 w-full rounded-lg border border-slate-300 bg-white dark:border-slate-700" />
      ) : (
        <><label className="label" htmlFor={`b-${email.id}`}>Body</label>
          <textarea id={`b-${email.id}`} className="input h-72 font-mono text-[13px]" value={body} onChange={(e) => setBody(e.target.value)} /></>
      )}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>Drafts only. ActionLoop never sends email.</span>
        <button className="btn-ghost" onClick={save} disabled={!dirty || busy}>Save edits</button>
      </div>
    </article>
  );
}

export function EmailsPanel({ meetingId, emails, tone, setTone, setEmails }: {
  meetingId: string; emails: Email[]; tone: Tone; setTone: (t: Tone) => void; setEmails: (e: Email[]) => void;
}) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const regenAll = async (t: Tone) => {
    setTone(t); setBusy(true);
    try { setEmails(await api.regenerateEmails(meetingId, t)); toast(`Emails rewritten in a ${t} tone`, "success"); }
    catch (e) { toast((e as Error).message, "error"); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium" htmlFor="tone">Tone</label>
        <select id="tone" className="input w-auto" value={tone} disabled={busy} onChange={(e) => regenAll(e.target.value as Tone)}>
          <option value="professional">Professional</option><option value="friendly">Friendly</option><option value="concise">Concise</option>
        </select>
        <span className="text-xs text-slate-500">Changing the tone regenerates all drafts.</span>
      </div>
      {emails.length ? emails.map((e) => <EmailCard key={e.id} email={e} tone={tone} onChange={(n) => setEmails(emails.map((x) => (x.id === n.id ? n : x)))} />)
        : <EmptyState title="No drafts yet" />}
    </div>
  );
}
