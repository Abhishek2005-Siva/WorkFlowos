"use client";

import { useMemo } from "react";
import type { Agent, EventItem } from "@/lib/types";

export default function PerformanceMetrics({ agents, events }: { agents: Agent[]; events: EventItem[] }) {
  const stats = useMemo(() => {
    const errors = events.filter((e) => e.category === "error").length;
    const conflicts = events.filter((e) => e.type === "conflict_detected").length;
    const resolved = events.filter((e) => e.type === "negotiation_resolved").length;
    const apiCalls = events.filter((e) => ["event_created", "task_created", "kb_logged", "slack_notification", "api_call"].includes(e.type)).length;
    const active = agents.filter((a) => a.status !== "idle").length;

    return { errors, conflicts, resolved, apiCalls, active };
  }, [agents, events]);

  const items: Array<{ label: string; value: number | string; accent: string; icon: string }> = [
    { label: "Active agents", value: `${stats.active}/${agents.length}`, accent: "from-cyan-500/20 to-transparent text-cyan-300", icon: "⚡" },
    { label: "API-ish calls", value: stats.apiCalls, accent: "from-emerald-500/20 to-transparent text-emerald-300", icon: "🌐" },
    { label: "Conflicts detected", value: stats.conflicts, accent: "from-amber-500/20 to-transparent text-amber-300", icon: "⚠️" },
    { label: "Negotiations resolved", value: stats.resolved, accent: "from-emerald-500/20 to-transparent text-emerald-300", icon: "🤝" },
    {
      label: "Errors",
      value: stats.errors,
      accent: stats.errors > 0 ? "from-red-500/20 to-transparent text-red-300" : "from-slate-500/10 to-transparent text-slate-400",
      icon: stats.errors > 0 ? "🚨" : "✅",
    },
  ];

  return (
    <div className="glass-card animate-fade-in-up rounded-2xl p-5">
      <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-white">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/20 to-purple-500/20 text-base">
          📈
        </span>
        Performance
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {items.map((item) => (
          <div
            key={item.label}
            className={`relative overflow-hidden rounded-xl border border-white/5 bg-gradient-to-br p-3 text-center ${item.accent}`}
          >
            <div className="mb-0.5 text-sm opacity-70">{item.icon}</div>
            <div className="text-2xl font-bold">{item.value}</div>
            <div className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
