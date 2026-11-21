import { useEffect, useRef } from "react";
import { formatTs } from "../lib/format";
import type { Segment } from "../lib/types";
import { EmptyState } from "./Badges";

export function TranscriptViewer({ segments, highlight, nonce }: { segments: Segment[]; highlight: number | null; nonce: number }) {
  const refs = useRef(new Map<number, HTMLDivElement>());
  useEffect(() => {
    if (highlight == null) return;
    const el = refs.current.get(highlight);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlight, nonce]);

  if (!segments.length) return <EmptyState title="No transcript" />;
  const anySpeaker = segments.some((s) => s.speaker);
  return (
    <div className="card max-h-[70vh] overflow-y-auto" role="log" aria-label="Transcript">
      {!anySpeaker && <p className="mb-3 text-xs text-slate-500">No speaker labels were found, so speakers are not attributed.</p>}
      {segments.map((s) => (
        <div
          key={`${s.idx}-${highlight === s.idx ? nonce : 0}`} ref={(el) => { if (el) refs.current.set(s.idx, el); }}
          className={`flex gap-3 rounded px-2 py-1.5 text-sm ${highlight === s.idx ? "seg-highlight" : ""}`} data-seg={s.idx}
        >
          <span className="w-12 shrink-0 pt-0.5 text-right font-mono text-xs text-slate-400">{formatTs(s.start) || s.idx + 1}</span>
          <p className="min-w-0">
            {s.speaker && <b className="mr-1.5">{s.speaker}:</b>}
            {s.text}
          </p>
        </div>
      ))}
    </div>
  );
}
