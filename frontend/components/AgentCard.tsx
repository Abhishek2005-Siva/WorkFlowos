"use client";

import type { Agent } from "@/lib/types";

const AGENT_EMOJI: Record<string, string> = {
  "Email Agent": "📧",
  "Calendar Agent": "📅",
  "Task Agent": "✅",
  "Knowledge Graph Agent": "📊",
  "Slack Coordination Hub": "🤖",
  "Alert Agent": "🔔",
  "GitHub Agent": "🐙",
  "Data Agent": "🗂️",
  "Logging Agent": "📈",
  "Social Agent": "💬",
};

const STATUS_STYLES: Record<string, { dot: string; ring: string; label: string }> = {
  idle: { dot: "bg-slate-500", ring: "", label: "Idle" },
  thinking: { dot: "bg-blue-500 animate-pulse", ring: "ring-blue-500/40", label: "Thinking" },
  acting: { dot: "bg-emerald-500 animate-pulse", ring: "ring-emerald-500/40", label: "Acting" },
  negotiating: { dot: "bg-amber-500 animate-pulse", ring: "ring-amber-500/50", label: "Negotiating" },
  waiting: { dot: "bg-purple-500 animate-pulse", ring: "ring-purple-500/40", label: "Waiting" },
  escalated: { dot: "bg-red-500 animate-ping", ring: "ring-red-500/50", label: "Escalated" },
  error: { dot: "bg-red-600", ring: "ring-red-600/50", label: "Error" },
};

function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

export default function AgentCard({ agent }: { agent: Agent }) {
  const style = STATUS_STYLES[agent.status] ?? STATUS_STYLES.idle;
  const emoji = AGENT_EMOJI[agent.name] ?? "🤖";
  const lastReasoning = agent.reasoning_trace[agent.reasoning_trace.length - 1];

  return (
    <div
      className={`rounded-xl border border-slate-700 bg-slate-800/80 p-4 transition-all hover:border-cyan-500/60 ring-1 ring-transparent ${style.ring}`}
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="text-2xl">{emoji}</span>
        <span className={`h-3 w-3 rounded-full ${style.dot}`} title={style.label} />
      </div>

      <h3 className="truncate text-sm font-semibold text-white">{agent.name}</h3>
      <p className="mt-0.5 text-xs capitalize text-slate-400">{style.label}</p>

      <div className="mt-3 space-y-1 text-[11px] text-slate-500">
        <div className="flex justify-between">
          <span>Last action</span>
          <span>{timeAgo(agent.last_action_time)}</span>
        </div>
        {agent.error_count > 0 && (
          <div className="font-medium text-red-400">⚠ {agent.error_count} error(s)</div>
        )}
      </div>

      {lastReasoning && (
        <p className="mt-3 line-clamp-2 rounded bg-slate-900/60 p-2 text-[11px] text-slate-300" title={lastReasoning.reasoning}>
          {lastReasoning.reasoning}
        </p>
      )}
    </div>
  );
}
