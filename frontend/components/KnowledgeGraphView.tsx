"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api-client";
import type { EventItem, GraphSnapshot } from "@/lib/types";

const TYPE_COLOR: Record<string, string> = {
  person: "#22d3ee",
  meeting: "#34d399",
  task: "#fbbf24",
  conflict: "#f87171",
};

const TYPE_ICON: Record<string, string> = {
  person: "👤",
  meeting: "📅",
  task: "✅",
  conflict: "⚠️",
};

const RING_RADIUS: Record<string, number> = {
  person: 80,
  meeting: 150,
  task: 210,
  conflict: 240,
};

// Distinct starting angles per ring so single-node rings (meeting,
// conflict) never land exactly on top of a multi-node ring's first item.
const RING_ANGLE_OFFSET: Record<string, number> = {
  person: 0,
  meeting: Math.PI / 5,
  task: Math.PI / 2.5,
  conflict: Math.PI,
};

const WIDTH = 720;
const HEIGHT = 500;
const CENTER = { x: WIDTH / 2, y: HEIGHT / 2 };

interface PositionedNode {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
}

function layout(graph: GraphSnapshot): PositionedNode[] {
  const byType = new Map<string, typeof graph.entities>();
  for (const node of graph.entities) {
    if (!byType.has(node.type)) byType.set(node.type, []);
    byType.get(node.type)!.push(node);
  }

  const positioned: PositionedNode[] = [];
  for (const [type, nodes] of byType.entries()) {
    if (type === "person" && nodes.some((n) => n.name === "You") && nodes.length === 1) {
      positioned.push({ ...nodes[0], x: CENTER.x, y: CENTER.y });
      continue;
    }
    const radius = RING_RADIUS[type] ?? 260;
    const you = nodes.find((n) => n.name === "You");
    const rest = nodes.filter((n) => n.name !== "You");
    if (you) positioned.push({ ...you, x: CENTER.x, y: CENTER.y });

    const offset = RING_ANGLE_OFFSET[type] ?? 0;
    rest.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(rest.length, 1) - Math.PI / 2 + offset;
      positioned.push({
        ...node,
        x: CENTER.x + radius * Math.cos(angle),
        y: CENTER.y + radius * Math.sin(angle),
      });
    });
  }
  return positioned;
}

function curvePath(x1: number, y1: number, x2: number, y2: number): string {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  // bow the curve perpendicular to the line so parallel edges don't overlap
  const dx = x2 - x1;
  const dy = y2 - y1;
  const dist = Math.hypot(dx, dy) || 1;
  const bow = Math.min(dist * 0.15, 40);
  const cx = mx - (dy / dist) * bow;
  const cy = my + (dx / dist) * bow;
  return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
}

export default function KnowledgeGraphView({ latestEvent }: { latestEvent: EventItem | null }) {
  const [graph, setGraph] = useState<GraphSnapshot>({ entities: [], relationships: [] });
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [pulse, setPulse] = useState(false);

  const refresh = () => api.graph().then(setGraph);

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (latestEvent?.type === "kb_logged") {
      refresh();
      setPulse(true);
      const t = setTimeout(() => setPulse(false), 1200);
      return () => clearTimeout(t);
    }
  }, [latestEvent]);

  const positioned = useMemo(() => layout(graph), [graph]);
  const positionMap = useMemo(() => new Map(positioned.map((n) => [n.id, n])), [positioned]);

  const active = hovered ?? selected;
  const connected = useMemo(() => {
    if (!active) return null;
    const set = new Set<string>([active]);
    for (const rel of graph.relationships) {
      if (rel.from_id === active) set.add(rel.to_id);
      if (rel.to_id === active) set.add(rel.from_id);
    }
    return set;
  }, [active, graph.relationships]);

  const activeNode = active ? positionMap.get(active) : null;

  return (
    <div className="glass-card animate-fade-in-up rounded-2xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-lg font-bold text-white">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500/20 to-purple-500/20 text-base">
            🕸️
          </span>
          Knowledge Graph
        </h2>
        {activeNode && (
          <span className="animate-fade-in-up rounded-full border border-slate-600 bg-slate-900/70 px-3 py-1 text-xs font-medium text-slate-200">
            {TYPE_ICON[activeNode.type] ?? "●"} {activeNode.name}
          </span>
        )}
      </div>

      {graph.entities.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 py-20 text-center">
          <span className="text-4xl opacity-40">🕸️</span>
          <p className="text-sm text-slate-500">No entities yet — the graph fills in as agents log decisions.</p>
        </div>
      ) : (
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full rounded-xl"
          style={{ height: HEIGHT, background: "radial-gradient(ellipse at center, #0f172a 0%, #020617 100%)" }}
          onClick={() => setSelected(null)}
        >
          <defs>
            {Object.entries(TYPE_COLOR).map(([type, color]) => (
              <radialGradient key={type} id={`grad-${type}`} cx="35%" cy="30%" r="70%">
                <stop offset="0%" stopColor={color} stopOpacity="1" />
                <stop offset="100%" stopColor={color} stopOpacity="0.55" />
              </radialGradient>
            ))}
            <radialGradient id="grad-you" cx="35%" cy="30%" r="70%">
              <stop offset="0%" stopColor="#a78bfa" stopOpacity="1" />
              <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.6" />
            </radialGradient>
            <pattern id="dot-grid" width="24" height="24" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill="#1e293b" />
            </pattern>
          </defs>

          <rect width={WIDTH} height={HEIGHT} fill="url(#dot-grid)" opacity={0.5} />

          {graph.relationships.map((rel, i) => {
            const from = positionMap.get(rel.from_id);
            const to = positionMap.get(rel.to_id);
            if (!from || !to) return null;
            const isHighlighted = active && (rel.from_id === active || rel.to_id === active);
            const isDimmed = active && !isHighlighted;
            return (
              <g key={i} opacity={isDimmed ? 0.12 : 1} className="transition-opacity duration-300">
                <path
                  d={curvePath(from.x, from.y, to.x, to.y)}
                  fill="none"
                  stroke={isHighlighted ? "#22d3ee" : "#334155"}
                  strokeWidth={isHighlighted ? 2.5 : 1.25}
                  strokeLinecap="round"
                  className="transition-all duration-300"
                />
                {isHighlighted && (
                  <text
                    x={(from.x + to.x) / 2}
                    y={(from.y + to.y) / 2 - 4}
                    textAnchor="middle"
                    fontSize={9}
                    fill="#67e8f9"
                    paintOrder="stroke"
                    stroke="#020617"
                    strokeWidth={3}
                    className="font-medium"
                  >
                    {rel.type.replace(/_/g, " ")}
                  </text>
                )}
              </g>
            );
          })}

          {positioned.map((node) => {
            const isYou = node.name === "You";
            const r = isYou ? 26 : 19;
            const isDimmed = active && connected && !connected.has(node.id);
            const isActive = active === node.id;
            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelected((prev) => (prev === node.id ? null : node.id));
                }}
                className="cursor-pointer transition-opacity duration-300"
                opacity={isDimmed ? 0.25 : 1}
              >
                {isActive && (
                  <circle r={r + 6} fill="none" stroke={TYPE_COLOR[node.type] ?? "#a78bfa"} strokeWidth={1.5} opacity={0.5}>
                    <animate attributeName="r" values={`${r + 4};${r + 10};${r + 4}`} dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.5;0.1;0.5" dur="2s" repeatCount="indefinite" />
                  </circle>
                )}
                <circle
                  r={r}
                  fill={isYou ? "url(#grad-you)" : `url(#grad-${node.type})`}
                  stroke={isActive ? "#f8fafc" : "#0f172a"}
                  strokeWidth={isActive ? 2.5 : 2}
                  style={{ filter: `drop-shadow(0 0 ${isActive ? 10 : 4}px ${isYou ? "#a78bfa" : (TYPE_COLOR[node.type] ?? "#64748b")}66)` }}
                />
                <text y={4} textAnchor="middle" fontSize={isYou ? 15 : 12}>
                  {isYou ? "🧑" : TYPE_ICON[node.type] ?? "●"}
                </text>
                <text
                  y={r + 15}
                  textAnchor="middle"
                  fontSize={10.5}
                  fill="#e2e8f0"
                  paintOrder="stroke"
                  stroke="#020617"
                  strokeWidth={3}
                  className="font-medium"
                >
                  {node.name.length > 20 ? `${node.name.slice(0, 18)}…` : node.name}
                </text>
              </g>
            );
          })}
        </svg>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2 text-[11px] text-slate-400">
          {Object.entries(TYPE_COLOR).map(([type, color]) => (
            <span
              key={type}
              className="flex items-center gap-1.5 rounded-full border border-slate-700/60 bg-slate-900/40 px-2.5 py-1"
            >
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }} />
              <span className="capitalize">{type}</span>
            </span>
          ))}
        </div>
        {graph.entities.length > 0 && (
          <span className={`text-[11px] text-slate-500 ${pulse ? "text-cyan-300" : ""}`}>
            {graph.entities.length} entities · {graph.relationships.length} relationships
          </span>
        )}
      </div>
    </div>
  );
}
