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

const AGENT_GRADIENT: Record<string, string> = {
  "Email Agent": "from-sky-500/25 to-sky-600/5",
  "Calendar Agent": "from-emerald-500/25 to-emerald-600/5",
  "Task Agent": "from-amber-500/25 to-amber-600/5",
  "Knowledge Graph Agent": "from-purple-500/25 to-purple-600/5",
  "Slack Coordination Hub": "from-pink-500/25 to-pink-600/5",
  "Alert Agent": "from-orange-500/25 to-orange-600/5",
  "GitHub Agent": "from-slate-400/25 to-slate-600/5",
};

const STATUS_STYLES: Record<string, { dot: string; glow: string; label: string; text: string }> = {
  idle: { dot: "bg-slate-500", glow: "", label: "Idle", text: "text-slate-400" },
  thinking: { dot: "bg-blue-400", glow: "shadow-[0_0_12px_2px_rgba(96,165,250,0.5)]", label: "Thinking", text: "text-blue-300" },
  acting: { dot: "bg-emerald-400", glow: "shadow-[0_0_12px_2px_rgba(52,211,153,0.5)]", label: "Acting", text: "text-emerald-300" },
  negotiating: { dot: "bg-amber-400", glow: "shadow-[0_0_12px_2px_rgba(251,191,36,0.5)]", label: "Negotiating", text: "text-amber-300" },
  waiting: { dot: "bg-purple-400", glow: "shadow-[0_0_12px_2px_rgba(192,132,252,0.5)]", label: "Waiting", text: "text-purple-300" },
  escalated: { dot: "bg-red-500", glow: "shadow-[0_0_14px_3px_rgba(239,68,68,0.6)]", label: "Escalated", text: "text-red-300" },
  error: { dot: "bg-red-600", glow: "shadow-[0_0_14px_3px_rgba(220,38,38,0.6)]", label: "Error", text: "text-red-400" },
};

const ACTIVE_STATUSES = new Set(["thinking", "acting", "negotiating", "waiting"]);

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
  const gradient = AGENT_GRADIENT[agent.name] ?? "from-slate-500/25 to-slate-600/5";
  const lastReasoning = agent.reasoning_trace[agent.reasoning_trace.length - 1];
  const isActive = ACTIVE_STATUSES.has(agent.status);

  return (
    <div
      className={`glass-card group relative overflow-hidden rounded-2xl p-4 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl ${
        isActive ? "border-white/20" : ""
      }`}
    >
      {isActive && <div className="absolute inset-0 animate-shimmer" />}

      <div className="relative mb-3 flex items-center justify-between">
        <span
          className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br text-lg ${gradient} ring-1 ring-white/10 transition-transform group-hover:scale-105`}
        >
          {emoji}
        </span>
        <span className={`h-2.5 w-2.5 rounded-full ${style.dot} ${style.glow} transition-all`} title={style.label} />
      </div>

      <h3 className="relative truncate text-sm font-semibold text-white">{agent.name}</h3>
      <p className={`relative mt-0.5 text-xs font-medium ${style.text}`}>{style.label}</p>

      <div className="relative mt-3 space-y-1 text-[11px] text-slate-500">
        <div className="flex justify-between">
          <span>Last action</span>
          <span>{timeAgo(agent.last_action_time)}</span>
        </div>
        {agent.error_count > 0 && (
          <div className="font-medium text-red-400">⚠ {agent.error_count} error(s)</div>
        )}
      </div>

      {lastReasoning && (
        <p
          className="relative mt-3 line-clamp-2 rounded-lg border border-white/5 bg-black/20 p-2 text-[11px] leading-relaxed text-slate-300"
          title={lastReasoning.reasoning}
        >
          {lastReasoning.reasoning}
        </p>
      )}
    </div>
  );
}
