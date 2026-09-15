"use client";

import { useWorkflowState } from "@/hooks/useWorkflowState";
import AgentCard from "@/components/AgentCard";
import ApprovalPanel from "@/components/ApprovalPanel";
import CalendarPanel from "@/components/CalendarPanel";
import ControlPanel from "@/components/ControlPanel";
import LiveEventStream from "@/components/LiveEventStream";
import ConflictPanel from "@/components/ConflictPanel";
import DecisionTimeline from "@/components/DecisionTimeline";
import KnowledgeGraphView from "@/components/KnowledgeGraphView";
import PerformanceMetrics from "@/components/PerformanceMetrics";

export default function Dashboard() {
  const { agents, events, connected, latestEvent } = useWorkflowState();

  return (
    <div className="min-h-screen px-4 py-8 sm:px-8">
      <header className="mb-6 flex items-center gap-4">
        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500/30 to-purple-500/20 text-3xl ring-1 ring-white/10">
          🤖
        </span>
        <div>
          <h1 className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-3xl font-black text-transparent sm:text-4xl">
            WorkflowOS
          </h1>
          <p className="mt-0.5 text-sm text-slate-400">Multi-agent orchestration platform — live agent status</p>
        </div>
      </header>

      <div className="mb-6 space-y-4">
        <ControlPanel connected={connected} />
        <ApprovalPanel latestEvent={latestEvent} />
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7">
        {agents.map((agent, i) => (
          <div key={agent.id} className="animate-fade-in-up" style={{ animationDelay: `${i * 40}ms` }}>
            <AgentCard agent={agent} />
          </div>
        ))}
      </div>

      <div className="mb-6">
        <PerformanceMetrics agents={agents} events={events} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <LiveEventStream events={events} />
        </div>
        <div className="space-y-6">
          <ConflictPanel latestEvent={latestEvent} />
          <DecisionTimeline latestEvent={latestEvent} />
          <CalendarPanel latestEvent={latestEvent} />
        </div>
      </div>

      <div className="mt-6">
        <KnowledgeGraphView latestEvent={latestEvent} />
      </div>

      <footer className="mt-10 pb-4 text-center text-[11px] text-slate-600">
        WorkflowOS — agents that negotiate, not just automate.
      </footer>
    </div>
  );
}
