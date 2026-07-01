"use client";

import { motion } from "framer-motion";
import { ArrowRight, ScanLine, ShieldCheck, Cpu } from "lucide-react";
import { ExtractPanel } from "@/components/ExtractPanel";
import { VerifyFactsPanel } from "@/components/VerifyFactsPanel";
import { ConclusionsPanel } from "@/components/ConclusionsPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { Disclaimer } from "@/components/Disclaimer";
import { useStore } from "@/store";

const panel = {
  hidden: { opacity: 0, y: 14 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.07, duration: 0.3, ease: "easeOut" as const },
  }),
};

const STEPS = [
  { icon: ScanLine, label: "Extract", sub: "LLM + OCR", color: "hsl(258,60%,52%)" },
  { icon: ShieldCheck, label: "Verify", sub: "Clinician", color: "hsl(190,63%,34%)" },
  { icon: Cpu, label: "Decide", sub: "Engine", color: "hsl(142,55%,30%)" },
];

function FlowStepper() {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 rounded-xl border bg-card/70 px-4 py-2.5 shadow-sm">
      {STEPS.map((s, i) => (
        <div key={s.label} className="flex items-center gap-2">
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.12 }}
            className="flex items-center gap-2"
          >
            <span
              className="flex h-7 w-7 items-center justify-center rounded-lg text-white shadow-sm"
              style={{ backgroundColor: s.color }}
            >
              <s.icon className="h-4 w-4" />
            </span>
            <span className="leading-tight">
              <span className="block text-sm font-semibold">{s.label}</span>
              <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
                {s.sub}
              </span>
            </span>
          </motion.div>
          {i < STEPS.length - 1 && (
            <motion.span
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.12 + 0.06 }}
              className="mx-1 text-muted-foreground"
            >
              <ArrowRight className="h-4 w-4" />
            </motion.span>
          )}
        </div>
      ))}
    </div>
  );
}

export function AssessmentPage() {
  const s = useStore();

  function selectRuleset(version: string) {
    s.setSelectedRuleset(version);
    if (s.engine) s.runAnalysis(version);
  }

  return (
    <div className="space-y-5">
      <Disclaimer rulesetStatus={s.config?.ruleset_status} />
      <FlowStepper />

      {s.error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {s.error}
        </p>
      )}

      {/* Inputs & results on the left; a tall, always-visible chat on the right. */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_390px] lg:items-start">
        <div className="grid gap-5 sm:grid-cols-2">
          <motion.div custom={0} variants={panel} initial="hidden" animate="show">
            <ExtractPanel
              note={s.note}
              setNote={s.setNote}
              extractionEnabled={s.config?.extraction_enabled ?? false}
              ocrEnabled={s.config?.ocr_enabled ?? false}
              model={s.config?.extractor_model ?? "—"}
              onFacts={s.setExtractedFacts}
            />
          </motion.div>
          <motion.div custom={1} variants={panel} initial="hidden" animate="show">
            <VerifyFactsPanel
              facts={s.facts}
              setFact={s.setFact}
              onRun={() => s.runAnalysis()}
              running={s.running}
            />
          </motion.div>
          <motion.div
            custom={2}
            variants={panel}
            initial="hidden"
            animate="show"
            className="sm:col-span-2"
          >
            <ConclusionsPanel
              engine={s.engine}
              baseline={s.baseline}
              comparison={s.comparison}
              baselineEnabled={s.config?.extraction_enabled ?? false}
              rulesets={s.rulesets}
              selectedRuleset={s.selectedRuleset}
              onSelectRuleset={selectRuleset}
            />
          </motion.div>
        </div>

        <motion.div
          custom={1.5}
          variants={panel}
          initial="hidden"
          animate="show"
          className="h-[600px] min-h-[440px] lg:sticky lg:top-6 lg:h-[calc(100vh-6.5rem)]"
        >
          <ChatPanel />
        </motion.div>
      </div>
    </div>
  );
}
