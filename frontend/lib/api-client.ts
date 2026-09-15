const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  agentsStatus: () => request<{ agents: import("./types").Agent[] }>("/agents/status"),
  recentEvents: (limit = 50) =>
    request<{ events: import("./types").EventItem[] }>(`/events/recent?limit=${limit}`),
  decisions: (limit = 20) => request<{ decisions: import("./types").Decision[] }>(`/decisions?limit=${limit}`),
  decision: (id: string) => request<import("./types").Decision & { reasoning_trace: unknown[] }>(`/decisions/${id}`),
  conflicts: (limit = 20) => request<{ conflicts: import("./types").Conflict[] }>(`/conflicts?limit=${limit}`),
  graph: () => request<import("./types").GraphSnapshot>("/knowledge/graph"),
  triggerCycle: (maxEmails = 3) =>
    request<{ status: string }>(`/workflow/trigger?max_emails=${maxEmails}`, { method: "POST" }),
  triggerDemo: () => request<{ status: string }>("/workflow/demo", { method: "POST" }),
  pendingApprovals: () =>
    request<{ pending: import("./types").PendingApproval[] }>("/workflow/approvals/pending"),
  resolveApproval: (decisionId: string, approved: boolean) =>
    request<{ resolved: boolean }>(`/workflow/approvals/${decisionId}?approved=${approved}`, { method: "POST" }),
  health: () => request<{ status: string; mock_mode: boolean }>("/health"),
  liveStatus: () => request<{ live: boolean; gmail_watch_configured: boolean }>("/workflow/live-status"),
  setLiveStatus: (live: boolean) =>
    request<{ live: boolean; error?: string }>(`/workflow/live-status?live=${live}`, { method: "POST" }),
};

export { BACKEND_URL };
