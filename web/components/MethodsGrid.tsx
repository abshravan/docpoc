"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Layers, Lightbulb, BookMarked } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  getRulesets,
  listProposals,
  type RulesetInfo,
  type RuleDetail,
  type ProposedMethod,
} from "@/lib/api";

const TIER_STYLE: Record<string, string> = {
  diagnostic: "bg-diagnostic/10 text-diagnostic border-diagnostic/30",
  suspicious: "bg-suspicious/10 text-suspicious border-suspicious/30",
};

function fmtParams(params: Record<string, number>): string {
  const entries = Object.entries(params);
  if (!entries.length) return "—";
  return entries.map(([k, v]) => `${k} = ${v}`).join(", ");
}

function RuleCard({ rule, i }: { rule: RuleDetail; i: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: i * 0.02 }}
      className="rounded-lg border bg-card p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs font-semibold">{rule.id}</span>
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize",
            TIER_STYLE[rule.tier] ?? "bg-muted text-muted-foreground"
          )}
        >
          {rule.tier}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{rule.description}</p>
      <div className="mt-2 rounded bg-muted px-2 py-1 font-mono text-[11px]">
        {fmtParams(rule.params)}
      </div>
      <div className="mt-1 text-[10px] text-muted-foreground">{rule.citation}</div>
    </motion.div>
  );
}

export function MethodsGrid() {
  const [rulesets, setRulesets] = useState<RulesetInfo[]>([]);
  const [proposals, setProposals] = useState<ProposedMethod[]>([]);

  useEffect(() => {
    getRulesets().then((r) => setRulesets(r.rulesets)).catch(() => undefined);
    listProposals().then((r) => setProposals(r.proposals)).catch(() => undefined);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Layers className="h-5 w-5 text-primary" /> Detection methods
        </h2>
        <p className="text-sm text-muted-foreground">
          Every rule the engine checks, grouped by guideline. New approved rulesets and
          proposed methods appear here automatically.
        </p>
      </div>

      {rulesets.map((rs) => (
        <section key={rs.version} className="space-y-2">
          <div className="flex items-center gap-2">
            <BookMarked className="h-4 w-4 text-muted-foreground" />
            <h3 className="font-medium">{rs.label}</h3>
            <Badge variant="secondary" className="text-[11px]">
              {rs.rule_count} rules · {rs.version}
            </Badge>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(rs.rules ?? []).map((rule, i) => (
              <RuleCard key={rule.id} rule={rule} i={i} />
            ))}
          </div>
        </section>
      ))}

      <section className="space-y-2">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-suspicious" />
          <h3 className="font-medium">Proposed methods</h3>
          <Badge variant="outline" className="text-[11px]">
            pending implementation
          </Badge>
        </div>
        {proposals.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            None yet. Novel criteria proposed in Authoring appear here — non-executable until a
            developer implements and a clinician signs off.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {proposals.map((p, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border border-dashed border-suspicious/40 bg-suspicious/5 p-3"
              >
                <div className="text-sm font-medium">{p.name}</div>
                <p className="mt-1 text-xs text-muted-foreground">{p.description}</p>
                <div className="mt-1 text-[10px] text-muted-foreground">{p.citation}</div>
              </motion.div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
