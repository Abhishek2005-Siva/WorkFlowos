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

  const items: Array<{ label: string; value: number | string; accent: string }> = [
    { label: "Active agents", value: `${stats.active}/${agents.length}`, accent: "text-cyan-400" },
    { label: "API-ish calls", value: stats.apiCalls, accent: "text-emerald-400" },
    { label: "Conflicts detected", value: stats.conflicts, accent: "text-amber-400" },
    { label: "Negotiations resolved", value: stats.resolved, accent: "text-emerald-400" },
    { label: "Errors", value: stats.errors, accent: stats.errors > 0 ? "text-red-400" : "text-slate-400" },
  ];

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-4">
      <h2 className="mb-3 text-lg font-bold text-white">📈 Performance</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {items.map((item) => (
          <div key={item.label} className="rounded-lg bg-slate-900/50 p-3 text-center">
            <div className={`text-2xl font-bold ${item.accent}`}>{item.value}</div>
            <div className="mt-1 text-[10px] uppercase tracking-wide text-slate-500">{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
