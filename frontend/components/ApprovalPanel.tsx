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
    <div className="rounded-xl border border-amber-500/40 bg-amber-950/10 p-4">
      <h2 className="mb-3 text-lg font-bold text-white">🙋 Needs Your Approval</h2>
      <div className="space-y-2">
        {pending.map((p) => (
          <div key={p.decision_id} className="rounded-lg border border-slate-700 bg-slate-900/50 p-3 text-xs">
            <p className="font-semibold text-white">{p.payload.title}</p>
            <p className="mt-1 text-slate-400">{p.payload.description}</p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => respond(p.decision_id, true)}
                disabled={resolving === p.decision_id}
                className="rounded bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                ✅ Approve
              </button>
              <button
                onClick={() => respond(p.decision_id, false)}
                disabled={resolving === p.decision_id}
                className="rounded bg-red-600 px-3 py-1.5 font-semibold text-white hover:bg-red-500 disabled:opacity-50"
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
