"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { CalendarEvent, EventItem } from "@/lib/types";

function formatRange(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  const dateStr = start.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  const startTime = start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const endTime = end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${dateStr} · ${startTime} – ${endTime}`;
}

function groupByDay(events: CalendarEvent[]): Map<string, CalendarEvent[]> {
  const groups = new Map<string, CalendarEvent[]>();
  for (const e of events) {
    const key = new Date(e.start).toDateString();
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(e);
  }
  return groups;
}

export default function CalendarPanel({ latestEvent }: { latestEvent: EventItem | null }) {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isMock, setIsMock] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = () =>
    api
      .calendarEvents(14, 1)
      .then((r) => {
        setEvents(r.events);
        setIsMock(r.mock);
      })
      .finally(() => setLoading(false));

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (latestEvent?.type === "event_created") refresh();
  }, [latestEvent]);

  const grouped = groupByDay(events);

  return (
    <div className="glass-card animate-fade-in-up rounded-2xl p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-bold text-white">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 text-base">
            📅
          </span>
          Calendar
          <span className="text-xs font-normal text-slate-500">next 14 days</span>
        </h2>
        {isMock !== null && (
          <span
            className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
              isMock ? "bg-amber-500/20 text-amber-300" : "bg-emerald-500/20 text-emerald-300"
            }`}
          >
            {isMock ? "MOCK" : "REAL"}
          </span>
        )}
      </div>

      {loading && <p className="py-6 text-center text-sm text-slate-500">Loading…</p>}

      {!loading && events.length === 0 && (
        <p className="py-6 text-center text-sm text-slate-500">Nothing on the calendar in this window.</p>
      )}

      <div className="max-h-96 space-y-4 overflow-y-auto">
        {Array.from(grouped.entries()).map(([day, dayEvents]) => (
          <div key={day}>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {new Date(day).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
            </p>
            <div className="space-y-1.5">
              {dayEvents.map((e, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-white/5 bg-black/20 p-2.5 text-xs transition-colors hover:bg-black/30"
                >
                  <p className="font-semibold text-white">{e.summary}</p>
                  <p className="mt-0.5 text-slate-400">{formatRange(e.start, e.end)}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
