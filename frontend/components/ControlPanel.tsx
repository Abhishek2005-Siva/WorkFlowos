"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export default function ControlPanel({ connected }: { connected: boolean }) {
  const [mockMode, setMockMode] = useState<boolean | null>(null);
  const [busy, setBusy] = useState<"demo" | "inbox" | null>(null);

  useEffect(() => {
    api
      .health()
      .then((r) => setMockMode(r.mock_mode))
      .catch(() => setMockMode(null));
  }, []);

  const runDemo = async () => {
    setBusy("demo");
    try {
      await api.triggerDemo();
    } finally {
      setTimeout(() => setBusy(null), 1000);
    }
  };

  const processInbox = async () => {
    setBusy("inbox");
    try {
      await api.triggerCycle(3);
    } finally {
      setTimeout(() => setBusy(null), 1000);
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-700 bg-slate-800/60 p-4">
      <div className="flex items-center gap-3">
        <span className={`h-2.5 w-2.5 rounded-full ${connected ? "bg-emerald-500" : "bg-red-500"}`} />
        <span className="text-sm text-slate-300">{connected ? "Live" : "Disconnected"}</span>
        {mockMode !== null && (
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              mockMode ? "bg-amber-500/20 text-amber-300" : "bg-emerald-500/20 text-emerald-300"
            }`}
          >
            {mockMode ? "MOCK MODE — no real APIs called" : "LIVE — real APIs connected"}
          </span>
        )}
      </div>

      <div className="flex gap-2">
        <button
          onClick={runDemo}
          disabled={busy !== null}
          className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:opacity-50"
        >
          {busy === "demo" ? "Running…" : "🤝 Run Negotiation Demo"}
        </button>
        <button
          onClick={processInbox}
          disabled={busy !== null}
          className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-600 disabled:opacity-50"
        >
          {busy === "inbox" ? "Processing…" : "📥 Process Inbox"}
        </button>
      </div>
    </div>
  );
}
