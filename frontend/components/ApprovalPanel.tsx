"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { EventItem, PendingApproval } from "@/lib/types";

/**
 * Approve/reject decisions directly from the dashboard — the fallback to
 * Slack's buttons. Slack's interactivity webhook needs a public HTTPS
 * URL, which a local dev server doesn't have, so this is often the only
 * way to actually unblock a workflow once MOCK_MODE is off.
 */
export default function ApprovalPanel({ latestEvent }: { latestEvent: EventItem | null }) {
  const [pending, setPending] = useState<PendingApproval[]>([]);
  const [resolving, setResolving] = useState<string | null>(null);

  const refresh = () =>
    api.pendingApprovals().then((r) => setPending(r.pending.filter((p) => !p.resolved)));

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (latestEvent?.type === "approval_requested" || latestEvent?.type === "approval_granted") {
      refresh();
    }
  }, [latestEvent]);

  const respond = async (decisionId: string, approved: boolean) => {
    setResolving(decisionId);
    try {
      await api.resolveApproval(decisionId, approved);
      setPending((prev) => prev.filter((p) => p.decision_id !== decisionId));
    } finally {
      setResolving(null);
    }
  };

  if (pending.length === 0) return null;

  return (
    <div className="animate-fade-in-up rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-amber-900/5 p-5 backdrop-blur-md">
      <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-white">
        <span className="flex h-8 w-8 animate-glow-pulse items-center justify-center rounded-lg bg-amber-500/20 text-base">
          🙋
        </span>
        Needs Your Approval
      </h2>
      <div className="space-y-2">
        {pending.map((p) => (
          <div key={p.decision_id} className="rounded-xl border border-white/5 bg-black/25 p-3 text-xs">
            <p className="font-semibold text-white">{p.payload.title}</p>
            <p className="mt-1 text-slate-400">{p.payload.description}</p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => respond(p.decision_id, true)}
                disabled={resolving === p.decision_id}
                className="rounded-lg bg-emerald-500 px-3 py-1.5 font-semibold text-black transition hover:bg-emerald-400 disabled:opacity-50"
              >
                ✅ Approve
              </button>
              <button
                onClick={() => respond(p.decision_id, false)}
                disabled={resolving === p.decision_id}
                className="rounded-lg bg-red-500 px-3 py-1.5 font-semibold text-white transition hover:bg-red-400 disabled:opacity-50"
              >
                ❌ Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
