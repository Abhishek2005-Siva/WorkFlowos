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
    <div className="min-h-screen bg-gradient-to-br from-slate-950 to-slate-900 px-4 py-8 sm:px-8">
      <header className="mb-6">
        <h1 className="text-3xl font-black text-white sm:text-4xl">🤖 WorkflowOS</h1>
        <p className="mt-1 text-sm text-slate-400">Multi-agent orchestration platform — live agent status</p>
      </header>

      <div className="mb-6 space-y-4">
        <ControlPanel connected={connected} />
        <ApprovalPanel latestEvent={latestEvent} />
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7">
        {agents.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
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
    </div>
  );
}
