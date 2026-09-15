"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import type { Agent, EventItem } from "@/lib/types";
import { useWebSocket } from "@/hooks/useWebSocket";

const MAX_EVENTS = 150;

/**
 * Single source of truth for live dashboard state: one WebSocket
 * connection to /ws/events, fanned out into an agent-status map (kept in
 * sync from agent_status / agent_reasoning events) and a rolling event
 * feed. Everything else (conflicts, decisions, graph) is cheap to refetch
 * on relevant events rather than stream, so it stays out of this hook.
 */
export function useWorkflowState() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [connected, setConnectedState] = useState(false);
  const { data: event, connected: wsConnected } = useWebSocket<EventItem>("/ws/events");
  const seenIds = useRef<Set<number>>(new Set());

  useEffect(() => {
    setConnectedState(wsConnected);
  }, [wsConnected]);

  useEffect(() => {
    api.agentsStatus().then((r) => setAgents(r.agents));
    api.recentEvents(MAX_EVENTS).then((r) => {
      setEvents(r.events);
      seenIds.current = new Set(r.events.map((e) => e.id));
    });
  }, []);

  useEffect(() => {
    if (!event) return;

    if (!seenIds.current.has(event.id)) {
      seenIds.current.add(event.id);
      setEvents((prev) => [...prev, event].slice(-MAX_EVENTS));
    }

    if (event.type === "agent_status") {
      const payload = event.data as { agent_id?: string; status?: string };
      setAgents((prev) =>
        prev.map((a) =>
          a.id === payload.agent_id
            ? { ...a, status: (payload.status as Agent["status"]) ?? a.status, last_action_time: event.timestamp }
            : a
        )
      );
    }

    if (event.type === "agent_reasoning") {
      setAgents((prev) =>
        prev.map((a) =>
          a.name === event.agent_name
            ? {
                ...a,
                reasoning_trace: [
                  ...a.reasoning_trace,
                  { timestamp: event.timestamp, step: a.reasoning_trace.length + 1, reasoning: event.message },
                ].slice(-10),
              }
            : a
        )
      );
    }

    if (event.type === "error" && event.category === "error") {
      setAgents((prev) =>
        prev.map((a) => (a.name === event.agent_name ? { ...a, error_count: a.error_count + 1 } : a))
      );
    }
  }, [event]);

  return { agents, events, connected, latestEvent: event };
}
