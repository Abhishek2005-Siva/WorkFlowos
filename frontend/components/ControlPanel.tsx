"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export default function ControlPanel({ connected }: { connected: boolean }) {
  const [mockMode, setMockMode] = useState<boolean | null>(null);
  const [busy, setBusy] = useState<"demo" | "inbox" | "live" | null>(null);
  const [isLive, setIsLive] = useState<boolean | null>(null);
  const [watchConfigured, setWatchConfigured] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then((r) => setMockMode(r.mock_mode))
      .catch(() => setMockMode(null));

    api
      .liveStatus()
      .then((r) => {
        setIsLive(r.live);
        setWatchConfigured(r.gmail_watch_configured);
      })
      .catch(() => setIsLive(null));
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

  const toggleLive = async () => {
    setBusy("live");
    setLiveError(null);
    try {
      const result = await api.setLiveStatus(!isLive);
      setIsLive(result.live);
      if (result.error) setLiveError(result.error);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-slate-700 bg-slate-800/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className={`h-2.5 w-2.5 rounded-full ${connected ? "bg-emerald-500" : "bg-red-500"}`} />
          <span className="text-sm text-slate-300">{connected ? "Connected" : "Disconnected"}</span>
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

        <div className="flex flex-wrap gap-2">
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

      {isLive !== null && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-900/50 p-3">
          <div>
            <p className="text-sm font-semibold text-white">
              {isLive ? "🟢 Live — reading real Gmail automatically" : "⏸️ Stopped — automation paused"}
            </p>
            <p className="mt-0.5 text-xs text-slate-400">
              {watchConfigured
                ? isLive
                  ? "New emails trigger the pipeline in real time. Turning this off unsubscribes from Gmail push."
                  : "Gmail push is configured but paused — nothing runs automatically until you go live."
                : "Gmail push isn't configured yet (see scripts/gmail_watch_setup.py) — this switch has no effect until it is."}
            </p>
            {liveError && <p className="mt-1 text-xs text-red-400">Error: {liveError}</p>}
          </div>
          <button
            onClick={toggleLive}
            disabled={busy !== null || !watchConfigured}
            className={`shrink-0 rounded-lg px-5 py-2 text-sm font-bold text-white transition disabled:opacity-50 ${
              isLive ? "bg-red-600 hover:bg-red-500" : "bg-emerald-600 hover:bg-emerald-500"
            }`}
          >
            {busy === "live" ? "…" : isLive ? "⏹ Stop" : "▶ Go Live"}
          </button>
        </div>
      )}
    </div>
  );
}
