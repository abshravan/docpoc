import { Cpu, Bot, Lock, CheckCircle2, AlertTriangle, Library } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { TIER_LABEL } from "@/lib/facts";
import type { BaselineResult, ComparisonResult, EngineResult } from "@/lib/api";

const TIER_BG: Record<string, string> = {
  diagnostic_of_loss: "bg-diagnostic",
  suspicious_for_loss: "bg-suspicious",
  no_criteria_met: "bg-ok",
};

function TierBadge({ tier }: { tier: string | null }) {
  if (!tier) return <Badge variant="outline">no parseable verdict</Badge>;
  return (
    <span
      className={cn(
        "inline-block rounded-md px-3 py-1 text-sm font-semibold text-white",
        TIER_BG[tier] ?? "bg-muted"
      )}
    >
      {TIER_LABEL[tier] ?? tier}
    </span>
  );
}

interface Props {
  engine: EngineResult | null;
  baseline: BaselineResult | null;
  comparison: ComparisonResult | null;
  baselineEnabled: boolean;
}

export function ConclusionsPanel({ engine, baseline, comparison, baselineEnabled }: Props) {
  const agreement =
    engine && baseline && baseline.determination
      ? engine.determination === baseline.determination
      : null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>3 · Conclusions</CardTitle>
          <Badge className="bg-[hsl(142,55%,30%)]">Deterministic + baseline</Badge>
        </div>
        <CardDescription>
          The engine is authoritative. The LLM opinion is a research baseline only.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!engine ? (
          <p className="py-6 text-sm text-muted-foreground">
            Run the analysis to see the determination.
          </p>
        ) : (
          <>
            {/* Authoritative deterministic result */}
            <section className="rounded-lg border bg-secondary/40 p-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                <Cpu className="h-4 w-4" /> Deterministic engine
                <Badge variant="outline" className="ml-auto">authoritative</Badge>
              </div>
              <TierBadge tier={engine.determination} />
              <p className="mt-2 text-sm text-muted-foreground">{engine.rationale}</p>
              {engine.fired_rules.length > 0 && (
                <ul className="mt-2 space-y-2">
                  {engine.fired_rules.map((r) => (
                    <li key={r.id} className="border-l-2 border-border pl-2 text-xs">
                      <div className="font-medium">
                        {r.id} <span className="opacity-60">({r.tier})</span>
                      </div>
                      <div>{r.description}</div>
                      <div className="text-muted-foreground">{r.citation}</div>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-2 text-[11px] text-muted-foreground">
                Ruleset {engine.ruleset_version}
              </div>
            </section>

            {/* Non-authoritative LLM baseline */}
            <section className="rounded-lg border border-dashed p-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                <Bot className="h-4 w-4" /> LLM baseline
                <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                  <Lock className="h-3 w-3" /> not used for the decision
                </span>
              </div>
              {!baselineEnabled ? (
                <p className="text-xs text-muted-foreground">
                  No model configured — baseline unavailable.
                </p>
              ) : !baseline ? (
                <p className="text-xs text-muted-foreground">Baseline pending…</p>
              ) : (
                <>
                  <TierBadge tier={baseline.determination} />
                  {baseline.rationale && (
                    <p className="mt-2 text-sm text-muted-foreground">{baseline.rationale}</p>
                  )}
                </>
              )}
            </section>

            {/* Disagreement flag */}
            {agreement !== null && (
              <div
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm",
                  agreement
                    ? "bg-ok/10 text-[hsl(142,60%,25%)]"
                    : "bg-destructive/10 text-destructive"
                )}
              >
                {agreement ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <AlertTriangle className="h-4 w-4" />
                )}
                {agreement
                  ? "LLM baseline agrees with the engine."
                  : "LLM baseline DISAGREES with the engine — the engine governs."}
              </div>
            )}

            {/* Cross-guideline comparison (deterministic, no voting) */}
            {comparison && comparison.entries.length > 1 && (
              <section className="rounded-lg border p-3">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                  <Library className="h-4 w-4" /> Across guidelines
                  <Badge
                    variant={comparison.concordant ? "secondary" : "destructive"}
                    className="ml-auto"
                  >
                    {comparison.concordant ? "concordant" : "divergent"}
                  </Badge>
                </div>
                <ul className="space-y-1.5">
                  {comparison.entries.map((e) => (
                    <li key={e.version} className="flex items-center justify-between gap-2 text-xs">
                      <span className="text-muted-foreground">{e.label}</span>
                      <span
                        className={cn(
                          "rounded px-2 py-0.5 font-semibold text-white",
                          TIER_BG[e.determination] ?? "bg-muted"
                        )}
                      >
                        {TIER_LABEL[e.determination] ?? e.determination}
                      </span>
                    </li>
                  ))}
                </ul>
                {!comparison.concordant && (
                  <p className="mt-2 text-[11px] text-muted-foreground">
                    Guidelines diverge on this case — clinician judgement decides which applies.
                  </p>
                )}
              </section>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
