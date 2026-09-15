"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api-client";
import type { EventItem, GraphSnapshot } from "@/lib/types";

const TYPE_COLOR: Record<string, string> = {
  person: "#06b6d4",
  meeting: "#10b981",
  task: "#f59e0b",
  conflict: "#ef4444",
};

const RING_RADIUS: Record<string, number> = {
  person: 70,
  meeting: 130,
  task: 185,
  conflict: 210,
};

// Distinct starting angles per ring so single-node rings (meeting,
// conflict) never land exactly on top of a multi-node ring's first item.
const RING_ANGLE_OFFSET: Record<string, number> = {
  person: 0,
  meeting: Math.PI / 5,
  task: Math.PI / 2.5,
  conflict: Math.PI,
};

const WIDTH = 680;
const HEIGHT = 460;
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
    const radius = RING_RADIUS[type] ?? 220;
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

export default function KnowledgeGraphView({ latestEvent }: { latestEvent: EventItem | null }) {
  const [graph, setGraph] = useState<GraphSnapshot>({ entities: [], relationships: [] });
  const [hovered, setHovered] = useState<string | null>(null);

  const refresh = () => api.graph().then(setGraph);

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    if (latestEvent?.type === "kb_logged") refresh();
  }, [latestEvent]);

  const positioned = useMemo(() => layout(graph), [graph]);
  const positionMap = useMemo(() => new Map(positioned.map((n) => [n.id, n])), [positioned]);

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-4">
      <h2 className="mb-3 text-lg font-bold text-white">🕸️ Knowledge Graph</h2>

      {graph.entities.length === 0 ? (
        <p className="py-16 text-center text-sm text-slate-500">
          No entities yet — the graph fills in as agents log decisions to Notion.
        </p>
      ) : (
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full rounded-lg bg-slate-900/50" style={{ height: HEIGHT }}>
          {graph.relationships.map((rel, i) => {
            const from = positionMap.get(rel.from_id);
            const to = positionMap.get(rel.to_id);
            if (!from || !to) return null;
            const isHighlighted = hovered === from.id || hovered === to.id;
            return (
              <line
                key={i}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={isHighlighted ? "#22d3ee" : "#475569"}
                strokeWidth={isHighlighted ? 2 : 1}
                opacity={isHighlighted ? 1 : 0.5}
              />
            );
          })}

          {positioned.map((node) => (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              onMouseEnter={() => setHovered(node.id)}
              onMouseLeave={() => setHovered(null)}
              className="cursor-pointer"
            >
              <circle r={node.name === "You" ? 22 : 16} fill={TYPE_COLOR[node.type] ?? "#64748b"} stroke="#0f172a" strokeWidth={2} />
              <text y={node.name === "You" ? 36 : 30} textAnchor="middle" fontSize={10} fill="#e2e8f0">
                {node.name.length > 18 ? `${node.name.slice(0, 16)}…` : node.name}
              </text>
              <title>{`${node.name} (${node.type})`}</title>
            </g>
          ))}
        </svg>
      )}

      <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-slate-400">
        {Object.entries(TYPE_COLOR).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}
