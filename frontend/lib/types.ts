export type AgentStatus =
  | "idle"
  | "thinking"
  | "acting"
  | "negotiating"
  | "waiting"
  | "escalated"
  | "error";

export interface ReasoningStep {
  timestamp: string;
  step: number;
  reasoning: string;
}

export interface Agent {
  id: string;
  name: string;
  type: string;
  status: AgentStatus;
  error_count: number;
  last_error: string | null;
  last_action_time: string | null;
  reasoning_trace: ReasoningStep[];
}

export interface EventItem {
  id: number;
  timestamp: string;
  type: string;
  category: string;
  agent_name: string;
  message: string;
  data: Record<string, unknown>;
  thread_id: string | null;
}

export interface Decision {
  decision_id: string;
  timestamp: string;
  agent: string;
  type: string;
  title: string;
  data: Record<string, unknown>;
}

export interface NegotiationStep {
  iteration: number;
  agent: string;
  proposal: string;
}

export interface Conflict {
  conflict_id: string;
  timestamp: string;
  agent1: string;
  agent2: string;
  description: string;
  negotiation_log: NegotiationStep[];
  status: "proposed" | "accepted" | "rejected" | "counter_proposed" | "resolved" | "escalated";
  resolution: string | null;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
}

export interface GraphLink {
  from_id: string;
  to_id: string;
  type: string;
}

export interface GraphSnapshot {
  entities: GraphNode[];
  relationships: GraphLink[];
}

export interface PendingApproval {
  decision_id: string;
  payload: { agent: string; title: string; description: string };
  resolved: boolean;
}
