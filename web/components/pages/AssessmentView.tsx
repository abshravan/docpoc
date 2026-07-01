"use client";

import { motion } from "framer-motion";
import { ExtractPanel } from "@/components/ExtractPanel";
import { VerifyFactsPanel } from "@/components/VerifyFactsPanel";
import { ConclusionsPanel } from "@/components/ConclusionsPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { Disclaimer } from "@/components/Disclaimer";
import { useStore } from "@/store";

const panel = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.06, duration: 0.28, ease: "easeOut" as const },
  }),
};

export function AssessmentPage() {
  const s = useStore();

  function selectRuleset(version: string) {
    s.setSelectedRuleset(version);
    if (s.engine) s.runAnalysis(version); // re-evaluate under the chosen guideline
  }

  return (
    <div className="space-y-5">
      <Disclaimer rulesetStatus={s.config?.ruleset_status} />

      {s.error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {s.error}
        </p>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {[
          <ExtractPanel
            key="extract"
            note={s.note}
            setNote={s.setNote}
            extractionEnabled={s.config?.extraction_enabled ?? false}
            ocrEnabled={s.config?.ocr_enabled ?? false}
            model={s.config?.extractor_model ?? "—"}
            onFacts={s.setExtractedFacts}
          />,
          <VerifyFactsPanel
            key="verify"
            facts={s.facts}
            setFact={s.setFact}
            onRun={() => s.runAnalysis()}
            running={s.running}
          />,
          <ConclusionsPanel
            key="conclude"
            engine={s.engine}
            baseline={s.baseline}
            comparison={s.comparison}
            baselineEnabled={s.config?.extraction_enabled ?? false}
            rulesets={s.rulesets}
            selectedRuleset={s.selectedRuleset}
            onSelectRuleset={selectRuleset}
          />,
        ].map((el, i) => (
          <motion.div key={i} custom={i} variants={panel} initial="hidden" animate="show">
            {el}
          </motion.div>
        ))}
      </div>

      <motion.div variants={panel} custom={3} initial="hidden" animate="show">
        <ChatPanel />
      </motion.div>
    </div>
  );
}
