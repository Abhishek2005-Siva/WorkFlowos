"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { Decision, EventItem } from "@/lib/types";

interface ReasoningEntry {
  step: number;
  reasoning: string;
  timestamp: string;
}

const TYPE_ICON: Record<string, string> = {
  meeting_scheduled: "📅",
  task_created: "✅",
  urgency_flag: "🚨",
  inform: "ℹ️",
};

export default function DecisionTimeline({ latestEvent }: { latestEvent: EventItem | null }) {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reasoningTrace, setReasoningTrace] = useState<ReasoningEntry[]>([]);

  const refresh = () => api.decisions(8).then((r) => setDecisions(r.decisions));

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (latestEvent?.type === "kb_logged") refresh();
  }, [latestEvent]);

  const toggle = async (decision: Decision) => {
    if (expandedId === decision.decision_id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(decision.decision_id);
    const full = await api.decision(decision.decision_id);
    setReasoningTrace((full.reasoning_trace as ReasoningEntry[]) ?? []);
  };

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-4">
      <h2 className="mb-3 text-lg font-bold text-white">📊 Decision Timeline</h2>

      {decisions.length === 0 && (
        <p className="py-6 text-center text-sm text-slate-500">No decisions logged yet.</p>
      )}

      <div className="space-y-3">
        {decisions.map((d) => (
          <div key={d.decision_id} className="flex gap-3">
            <div className="mt-0.5 text-xl">{TYPE_ICON[d.type] ?? "📌"}</div>
            <button
              onClick={() => toggle(d)}
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900/40 p-3 text-left text-xs transition hover:border-cyan-500/60"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-white">{d.title}</span>
                <span className="shrink-0 text-[10px] text-slate-500">
                  {new Date(d.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p className="mt-0.5 text-slate-400">
                {d.agent} · {d.type}
              </p>

              {expandedId === d.decision_id && (
                <div className="mt-3 space-y-1 border-t border-slate-700 pt-2">
                  {reasoningTrace.length === 0 && <p className="text-slate-500">No reasoning trace recorded.</p>}
                  {reasoningTrace.map((r, i) => (
                    <div key={i} className="flex gap-2 text-slate-300">
                      <span className="text-slate-600">{r.step}.</span>
                      <span>{r.reasoning}</span>
                    </div>
                  ))}
                </div>
              )}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
