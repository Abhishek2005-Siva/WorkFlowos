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
  conflict: "border-red-500/60 bg-gradient-to-r from-red-500/10 to-transparent",
  negotiation: "border-amber-500/60 bg-gradient-to-r from-amber-500/10 to-transparent",
  error: "border-red-500/60 bg-gradient-to-r from-red-500/10 to-transparent",
  warning: "border-amber-500/50 bg-gradient-to-r from-amber-500/5 to-transparent",
  success: "border-emerald-500/60 bg-gradient-to-r from-emerald-500/10 to-transparent",
  status: "border-slate-600/60 bg-white/[0.02]",
  reasoning: "border-slate-700/60 bg-transparent",
  default: "border-cyan-500/50 bg-gradient-to-r from-cyan-500/5 to-transparent",
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
    <div className="glass-card animate-fade-in-up flex h-[28rem] flex-col rounded-2xl p-5">
      <h2 className="mb-3 flex shrink-0 items-center gap-2 text-lg font-bold text-white">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/20 to-purple-500/20 text-base">
          🎬
        </span>
        Live Event Stream
      </h2>

      <div className="flex-1 space-y-1.5 overflow-y-auto pr-1">
        {events.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <span className="text-3xl opacity-40">📡</span>
            <p className="text-sm text-slate-500">
              No events yet — click &quot;Run Negotiation Demo&quot; to watch the agents work.
            </p>
          </div>
        )}

        {events.map((event, i) => (
          <div
            key={event.id}
            className={`animate-fade-in-up rounded-lg border-l-2 px-3 py-2 text-xs transition-colors hover:bg-white/[0.03] ${
              CATEGORY_STYLES[event.category] ?? CATEGORY_STYLES.default
            }`}
            style={{ animationDelay: i >= events.length - 3 ? "0ms" : undefined }}
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
