"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { Conflict, EventItem } from "@/lib/types";

const STATUS_BADGE: Record<string, string> = {
  proposed: "bg-slate-600 text-slate-100",
  counter_proposed: "bg-amber-600 text-white",
  resolved: "bg-emerald-600 text-white",
  escalated: "bg-red-600 text-white",
  rejected: "bg-red-600 text-white",
  accepted: "bg-emerald-600 text-white",
};

export default function ConflictPanel({ latestEvent }: { latestEvent: EventItem | null }) {
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [selected, setSelected] = useState<Conflict | null>(null);

  const refresh = () => api.conflicts(10).then((r) => setConflicts(r.conflicts));

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (!latestEvent) return;
    if (["conflict_detected", "negotiation_started", "negotiation_proposal", "negotiation_resolved"].includes(latestEvent.type)) {
      refresh();
    }
  }, [latestEvent]);

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-4">
      <h2 className="mb-3 text-lg font-bold text-white">🤝 Conflicts &amp; Negotiations</h2>

      {conflicts.length === 0 && (
        <p className="py-6 text-center text-sm text-slate-500">No conflicts yet — negotiation kicks in when a meeting collides with a task deadline.</p>
      )}

      <div className="space-y-2">
        {conflicts.map((c) => (
          <button
            key={c.conflict_id}
            onClick={() => setSelected(c)}
            className="block w-full rounded-lg border border-slate-700 bg-slate-900/40 p-3 text-left text-xs transition hover:border-cyan-500/60"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-white">
                {c.agent1} ↔ {c.agent2}
              </span>
              <span className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${STATUS_BADGE[c.status] ?? "bg-slate-600"}`}>
                {c.status}
              </span>
            </div>
            <p className="mt-1 line-clamp-2 text-slate-400">{c.description}</p>
          </button>
        ))}
      </div>

      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-800 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4 text-xl font-bold text-white">Negotiation Detail</h3>

            <div className="mb-4 flex items-center justify-around">
              <div className="text-center">
                <div className="text-3xl">📅</div>
                <p className="mt-1 text-sm font-semibold text-white">{selected.agent1}</p>
              </div>
              <div className="text-2xl">🤝</div>
              <div className="text-center">
                <div className="text-3xl">✅</div>
                <p className="mt-1 text-sm font-semibold text-white">{selected.agent2}</p>
              </div>
            </div>

            <div className="mb-3 rounded bg-slate-900/60 p-3 text-sm text-slate-300">
              <span className="font-semibold text-red-300">Issue: </span>
              {selected.description}
            </div>

            <div className="mb-3 space-y-2 rounded bg-slate-900/60 p-3">
              <p className="text-xs font-semibold text-slate-400">Negotiation rounds:</p>
              {selected.negotiation_log.map((step, i) => (
                <div key={i} className="flex gap-2 text-xs text-slate-300">
                  <span>{step.agent === selected.agent1 ? "→" : "←"}</span>
                  <span>
                    <span className="font-semibold">{step.agent}:</span> {step.proposal}
                  </span>
                </div>
              ))}
            </div>

            {selected.resolution && (
              <div
                className={`rounded p-3 text-sm font-semibold ${
                  selected.status === "resolved"
                    ? "border border-emerald-500 bg-emerald-950/30 text-emerald-400"
                    : "border border-red-500 bg-red-950/30 text-red-400"
                }`}
              >
                {selected.status === "resolved" ? "✅ " : "🚨 "}
                {selected.resolution}
              </div>
            )}

            <button
              onClick={() => setSelected(null)}
              className="mt-4 w-full rounded-lg bg-slate-700 px-4 py-2 text-sm text-white hover:bg-slate-600"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
