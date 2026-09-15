"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export default function ControlPanel({ connected }: { connected: boolean }) {
  const [mockMode, setMockMode] = useState<boolean | null>(null);
  const [busy, setBusy] = useState<"demo" | "inbox" | "live" | null>(null);
  const [isLive, setIsLive] = useState<boolean | null>(null);
  const [watchConfigured, setWatchConfigured] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [blockedReason, setBlockedReason] = useState<string | null>(null);

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
    setBlockedReason(null);
    try {
      const result = await api.triggerDemo();
      if (result.status === "blocked") setBlockedReason(result.reason ?? "Blocked.");
    } finally {
      setTimeout(() => setBusy(null), 1000);
    }
  };

  const processInbox = async () => {
    setBusy("inbox");
    setBlockedReason(null);
    try {
      const result = await api.triggerCycle(3);
      if (result.status === "blocked") setBlockedReason(result.reason ?? "Blocked.");
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
    <div className="glass-card animate-fade-in-up flex flex-col gap-3 rounded-2xl p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            {connected && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
            <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${connected ? "bg-emerald-500" : "bg-red-500"}`} />
          </span>
          <span className="text-sm text-slate-300">{connected ? "Connected" : "Disconnected"}</span>
          {mockMode !== null && (
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
                mockMode ? "bg-amber-500/10 text-amber-300 ring-amber-500/30" : "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
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
            className="rounded-xl bg-gradient-to-r from-cyan-500 to-cyan-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-cyan-900/30 transition hover:from-cyan-400 hover:to-cyan-500 disabled:opacity-50"
          >
            {busy === "demo" ? "Running…" : "🤝 Run Negotiation Demo"}
          </button>
          <button
            onClick={processInbox}
            disabled={busy !== null}
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10 disabled:opacity-50"
          >
            {busy === "inbox" ? "Processing…" : "📥 Process Inbox"}
          </button>
        </div>
      </div>

      {blockedReason && (
        <p className="animate-fade-in-up rounded-xl border border-amber-500/30 bg-amber-950/20 px-3 py-2 text-xs text-amber-300">
          ⚠️ {blockedReason}
        </p>
      )}

      {isLive !== null && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/5 bg-black/20 p-3.5">
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
            className={`shrink-0 rounded-xl px-5 py-2 text-sm font-bold text-white shadow-lg transition disabled:opacity-50 ${
              isLive ? "bg-gradient-to-r from-red-500 to-red-600 shadow-red-900/30 hover:from-red-400 hover:to-red-500" : "bg-gradient-to-r from-emerald-500 to-emerald-600 shadow-emerald-900/30 hover:from-emerald-400 hover:to-emerald-500"
            }`}
          >
            {busy === "live" ? "…" : isLive ? "⏹ Stop" : "▶ Go Live"}
          </button>
        </div>
      )}
    </div>
  );
}
