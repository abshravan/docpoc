import { ExtractPanel } from "@/components/ExtractPanel";
import { VerifyFactsPanel } from "@/components/VerifyFactsPanel";
import { ConclusionsPanel } from "@/components/ConclusionsPanel";
import { Disclaimer } from "@/components/Disclaimer";
import { useStore } from "@/store";

export function AssessmentPage() {
  const s = useStore();
  return (
    <div className="space-y-5">
      <Disclaimer rulesetStatus={s.config?.ruleset_status} />

      {s.error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {s.error}
        </p>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <ExtractPanel
          note={s.note}
          setNote={s.setNote}
          extractionEnabled={s.config?.extraction_enabled ?? false}
          model={s.config?.extractor_model ?? "—"}
          onFacts={s.setExtractedFacts}
        />
        <VerifyFactsPanel
          facts={s.facts}
          setFact={s.setFact}
          onRun={s.runAnalysis}
          running={s.running}
        />
        <ConclusionsPanel
          engine={s.engine}
          baseline={s.baseline}
          baselineEnabled={s.config?.extraction_enabled ?? false}
        />
      </div>
    </div>
  );
}
