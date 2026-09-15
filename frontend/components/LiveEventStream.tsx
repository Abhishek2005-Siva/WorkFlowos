"use client";

import { useEffect, useRef } from "react";
import type { EventItem } from "@/lib/types";

const EVENT_ICONS: Record<string, string> = {
  email_received: "📧",
  agent_status: "🔄",
  agent_reasoning: "🤔",
  api_call: "🌐",
  approval_requested: "🙋",
  approval_granted: "✅",
  conflict_detected: "⚠️",
  negotiation_started: "🤝",
  negotiation_proposal: "💬",
  negotiation_resolved: "✅",
  task_created: "📝",
  event_created: "📅",
  kb_logged: "📊",
  slack_notification: "💬",
  workflow_complete: "🎉",
  error: "❌",
};

const CATEGORY_STYLES: Record<string, string> = {
  conflict: "border-l-4 border-red-500 bg-red-950/20",
  negotiation: "border-l-4 border-amber-500 bg-amber-950/20",
  error: "border-l-4 border-red-500 bg-red-950/20",
  warning: "border-l-4 border-amber-500 bg-amber-950/10",
  success: "border-l-4 border-emerald-500 bg-emerald-950/20",
  status: "border-l-4 border-slate-600 bg-slate-800/40",
  reasoning: "border-l-4 border-slate-700 bg-slate-800/30",
  default: "border-l-4 border-cyan-600 bg-slate-800/40",
};

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

export default function LiveEventStream({ events }: { events: EventItem[] }) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events.length]);

  return (
    <div className="flex h-[28rem] flex-col rounded-xl border border-slate-700 bg-slate-800/60 p-4">
      <h2 className="mb-3 shrink-0 text-lg font-bold text-white">🎬 Live Event Stream</h2>

      <div className="flex-1 space-y-2 overflow-y-auto pr-1">
        {events.length === 0 && (
          <p className="py-12 text-center text-sm text-slate-500">
            No events yet — click &quot;Run Demo&quot; to watch the agents work.
          </p>
        )}

        {events.map((event) => (
          <div
            key={event.id}
            className={`rounded-r px-3 py-2 text-xs ${CATEGORY_STYLES[event.category] ?? CATEGORY_STYLES.default}`}
          >
            <div className="flex items-start gap-2">
              <span className="shrink-0 text-base leading-none">{EVENT_ICONS[event.type] ?? "🤖"}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-semibold text-white">{event.agent_name}</span>
                  <span className="shrink-0 text-[10px] text-slate-500">{formatTime(event.timestamp)}</span>
                </div>
                <p className="mt-0.5 whitespace-pre-wrap text-slate-300">{event.message}</p>
              </div>
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
