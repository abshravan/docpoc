import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Activity, FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { TIER_LABEL } from "@/lib/facts";
import { useStore } from "@/store";
import type { EngineResult, Ruleset } from "@/lib/api";

const INDIGO = "hsl(243 75% 58%)";
const MUTED = "hsl(220 16% 80%)";

const DIAG_CHAIN = [
  { node: "d1", rule: "crl_no_cardiac", yes: "e_d1_diag", no: "e_d1_d2" },
  { node: "d2", rule: "msd_no_embryo", yes: "e_d2_diag", no: "e_d2_d3" },
  { node: "d3", rule: "interval_no_yolk", yes: "e_d3_diag", no: "e_d3_d4" },
  { node: "d4", rule: "interval_with_yolk", yes: "e_d4_diag", no: "e_d4_s" },
];

const SUSPICIOUS_IDS = [
  "crl_small_no_cardiac",
  "msd_intermediate_no_embryo",
  "interval_no_yolk_suspicious",
  "interval_with_yolk_suspicious",
  "enlarged_yolk_sac",
  "empty_amnion",
  "small_sac_relative_to_embryo",
  "no_embryo_by_lmp",
];

// ---------------------------------------------------------------- node views
interface DecisionData {
  label: string;
  active: boolean;
  [key: string]: unknown;
}

function StartNode(props: NodeProps) {
  const data = props.data as DecisionData;
  return (
    <div className="w-[230px] rounded-xl border-2 border-primary/40 bg-card px-4 py-3 text-center shadow-sm">
      <div className="flex items-center justify-center gap-2 text-sm font-semibold">
        <Activity className="h-4 w-4 text-primary" /> {data.label}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-primary" />
    </div>
  );
}

function DecisionNode(props: NodeProps) {
  const data = props.data as DecisionData;
  return (
    <div
      className={cn(
        "w-[250px] rounded-lg border bg-card px-4 py-3 text-sm shadow-sm transition-colors",
        data.active ? "border-primary ring-2 ring-primary/40 bg-accent" : "border-border"
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      {data.label}
      <Handle id="no" type="source" position={Position.Bottom} className="!bg-muted-foreground" />
      <Handle id="yes" type="source" position={Position.Right} className="!bg-diagnostic" />
    </div>
  );
}

interface GroupData extends DecisionData {
  items: { id: string; text: string; fired: boolean }[];
}

function GroupNode(props: NodeProps) {
  const data = props.data as GroupData;
  return (
    <div
      className={cn(
        "w-[270px] rounded-lg border bg-card px-4 py-3 text-sm shadow-sm",
        data.active ? "border-suspicious ring-2 ring-suspicious/40" : "border-border"
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      <div className="font-medium">{data.label}</div>
      <ul className="mt-1 space-y-0.5">
        {data.items.map((it) => (
          <li
            key={it.id}
            className={cn(
              "text-[11px] leading-snug",
              it.fired ? "font-semibold text-suspicious" : "text-muted-foreground"
            )}
          >
            • {it.text}
          </li>
        ))}
      </ul>
      <Handle id="no" type="source" position={Position.Bottom} className="!bg-muted-foreground" />
      <Handle id="yes" type="source" position={Position.Right} className="!bg-suspicious" />
    </div>
  );
}

interface OutcomeData extends DecisionData {
  tone: "diagnostic" | "suspicious" | "ok";
  target: "left" | "top";
}

const TONE_BG: Record<string, string> = {
  diagnostic: "bg-diagnostic",
  suspicious: "bg-suspicious",
  ok: "bg-ok",
};

function OutcomeNode(props: NodeProps) {
  const data = props.data as OutcomeData;
  return (
    <div
      className={cn(
        "w-[210px] rounded-xl px-4 py-3 text-center text-sm font-bold text-white shadow-md transition-all",
        TONE_BG[data.tone],
        data.active ? "ring-4 ring-offset-2 ring-primary/50 scale-[1.03]" : "opacity-50"
      )}
    >
      <Handle
        type="target"
        position={data.target === "left" ? Position.Left : Position.Top}
        className="!bg-white"
      />
      {data.label}
    </div>
  );
}

const nodeTypes = {
  start: StartNode,
  decision: DecisionNode,
  group: GroupNode,
  outcome: OutcomeNode,
};

// ---------------------------------------------------------------- path logic
function activeSets(engine: EngineResult | null) {
  const nodes = new Set<string>();
  const edges = new Set<string>();
  if (!engine) return { nodes, edges };
  const fired = new Set(engine.fired_rules.map((r) => r.id));
  nodes.add("start");
  edges.add("e_start_d1");

  if (engine.determination === "diagnostic_of_loss") {
    for (const step of DIAG_CHAIN) {
      nodes.add(step.node);
      if (fired.has(step.rule)) {
        edges.add(step.yes);
        nodes.add("diag");
        break;
      }
      edges.add(step.no);
    }
  } else {
    for (const step of DIAG_CHAIN) {
      nodes.add(step.node);
      edges.add(step.no);
    }
    nodes.add("s");
    if (engine.determination === "suspicious_for_loss") {
      edges.add("e_s_susp");
      nodes.add("susp");
    } else {
      edges.add("e_s_none");
      nodes.add("none");
    }
  }
  return { nodes, edges };
}

// ---------------------------------------------------------------- label data
function param(ruleset: Ruleset | null, id: string, key: string, fallback: number) {
  const r = ruleset?.rules.find((x) => x.id === id);
  return r?.params?.[key] ?? fallback;
}

function buildGraph(ruleset: Ruleset | null, engine: EngineResult | null) {
  const active = activeSets(engine);
  const firedSuspicious = new Set(
    (engine?.fired_rules ?? [])
      .map((r) => r.id)
      .filter((id) => SUSPICIOUS_IDS.includes(id))
  );

  const labels: Record<string, string> = {
    d1: `CRL ≥ ${param(ruleset, "crl_no_cardiac", "crl_mm", 7)} mm and no cardiac activity?`,
    d2: `MSD ≥ ${param(ruleset, "msd_no_embryo", "msd_mm", 25)} mm and no embryo?`,
    d3: `No embryo + heartbeat ≥ ${param(ruleset, "interval_no_yolk", "days", 14)} days after a sac WITHOUT a yolk sac?`,
    d4: `No embryo + heartbeat ≥ ${param(ruleset, "interval_with_yolk", "days", 11)} days after a sac WITH a yolk sac?`,
  };

  const suspItems = SUSPICIOUS_IDS.map((id) => {
    const r = ruleset?.rules.find((x) => x.id === id);
    return { id, text: r ? shorten(r.description) : id, fired: firedSuspicious.has(id) };
  });

  const node = (
    id: string,
    type: string,
    x: number,
    y: number,
    data: Record<string, unknown>
  ): Node => ({ id, type, position: { x, y }, data: { ...data, active: active.nodes.has(id) } });

  const nodes: Node[] = [
    node("start", "start", 200, 0, { label: "Early-pregnancy ultrasound findings" }),
    node("d1", "decision", 190, 110, { label: labels.d1 }),
    node("d2", "decision", 190, 240, { label: labels.d2 }),
    node("d3", "decision", 190, 370, { label: labels.d3 }),
    node("d4", "decision", 190, 510, { label: labels.d4 }),
    node("s", "group", 175, 660, { label: "Any suspicious criterion met?", items: suspItems }),
    node("diag", "outcome", 580, 290, {
      label: TIER_LABEL.diagnostic_of_loss,
      tone: "diagnostic",
      target: "left",
    }),
    node("susp", "outcome", 600, 720, {
      label: `${TIER_LABEL.suspicious_for_loss} — follow-up`,
      tone: "suspicious",
      target: "left",
    }),
    node("none", "outcome", 205, 980, {
      label: TIER_LABEL.no_criteria_met,
      tone: "ok",
      target: "top",
    }),
  ];

  const mk = (
    id: string,
    source: string,
    target: string,
    opts: Partial<Edge> & { label?: string } = {}
  ): Edge => {
    const on = active.edges.has(id);
    const color = on ? INDIGO : MUTED;
    return {
      id,
      source,
      target,
      label: opts.label,
      sourceHandle: opts.sourceHandle,
      targetHandle: opts.targetHandle,
      type: "smoothstep",
      animated: on,
      labelStyle: { fontSize: 11, fill: on ? INDIGO : "hsl(220 12% 45%)" },
      labelBgStyle: { fill: "white" },
      style: { stroke: color, strokeWidth: on ? 2.5 : 1.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color },
    };
  };

  const edges: Edge[] = [
    mk("e_start_d1", "start", "d1"),
    mk("e_d1_d2", "d1", "d2", { label: "No", sourceHandle: "no" }),
    mk("e_d2_d3", "d2", "d3", { label: "No", sourceHandle: "no" }),
    mk("e_d3_d4", "d3", "d4", { label: "No", sourceHandle: "no" }),
    mk("e_d4_s", "d4", "s", { label: "No", sourceHandle: "no" }),
    mk("e_d1_diag", "d1", "diag", { label: "Yes", sourceHandle: "yes" }),
    mk("e_d2_diag", "d2", "diag", { label: "Yes", sourceHandle: "yes" }),
    mk("e_d3_diag", "d3", "diag", { label: "Yes", sourceHandle: "yes" }),
    mk("e_d4_diag", "d4", "diag", { label: "Yes", sourceHandle: "yes" }),
    mk("e_s_susp", "s", "susp", { label: "Yes", sourceHandle: "yes" }),
    mk("e_s_none", "s", "none", { label: "No", sourceHandle: "no" }),
  ];

  return { nodes, edges };
}

function shorten(text: string): string {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > 64 ? t.slice(0, 61) + "…" : t;
}

// ---------------------------------------------------------------- page
export function FlowPage() {
  const { ruleset, engine } = useStore();
  const { nodes, edges } = useMemo(() => buildGraph(ruleset, engine), [ruleset, engine]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <FlaskConical className="h-5 w-5 text-primary" /> How loss is detected
          </h2>
          <p className="text-sm text-muted-foreground">
            The SRU 2013 decision logic the engine applies. Thresholds are read live from
            ruleset {ruleset?.version ?? "—"}.
          </p>
        </div>
        {engine ? (
          <Badge variant="outline" className="text-xs">
            Highlighting current case: {TIER_LABEL[engine.determination] ?? engine.determination}
          </Badge>
        ) : (
          <Button asChild variant="outline" size="sm">
            <Link to="/">Run an assessment to highlight the path →</Link>
          </Button>
        )}
      </div>

      <div className="h-[72vh] overflow-hidden rounded-xl border bg-card/60">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
        >
          <Background color="hsl(243 40% 80%)" gap={20} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <Legend color="bg-diagnostic" label="Diagnostic of loss" />
        <Legend color="bg-suspicious" label="Suspicious — follow-up only" />
        <Legend color="bg-ok" label="No criteria met" />
        <span className="ml-auto">
          A “suspicious” path never escalates to treatment — it recommends follow-up imaging.
        </span>
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("h-3 w-3 rounded-full", color)} /> {label}
    </span>
  );
}
