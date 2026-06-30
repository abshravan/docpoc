import { useEffect, useState } from "react";
import { Disclaimer } from "@/components/Disclaimer";
import { ExtractPanel } from "@/components/ExtractPanel";
import { VerifyFactsPanel } from "@/components/VerifyFactsPanel";
import { ConclusionsPanel } from "@/components/ConclusionsPanel";
import { EMPTY_FACTS, type Facts, type FactValue } from "@/lib/facts";
import {
  evaluateFacts,
  getConfig,
  llmBaseline,
  type AppConfig,
  type BaselineResult,
  type EngineResult,
} from "@/lib/api";

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [note, setNote] = useState("");
  const [facts, setFacts] = useState<Facts>(EMPTY_FACTS);
  const [engine, setEngine] = useState<EngineResult | null>(null);
  const [baseline, setBaseline] = useState<BaselineResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getConfig().then(setConfig).catch(() => setError("Could not reach the API."));
  }, []);

  function setFact(name: string, value: FactValue) {
    setFacts((prev) => ({ ...prev, [name]: value }));
  }

  function onExtractedFacts(extracted: Facts) {
    setFacts({ ...EMPTY_FACTS, ...extracted });
  }

  async function runAnalysis() {
    setRunning(true);
    setError("");
    setBaseline(null);
    try {
      const engineResult = await evaluateFacts(facts);
      setEngine(engineResult);
      // The LLM baseline is computed independently from the raw note, never
      // from the verified facts, and never feeds the engine result above.
      if (config?.extraction_enabled && note.trim()) {
        llmBaseline(note)
          .then(setBaseline)
          .catch(() => setBaseline(null));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-5">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">
          EPL-CDS — early pregnancy loss decision support
        </h1>
        <p className="text-sm text-muted-foreground">
          LLM extracts facts · clinician verifies · deterministic engine decides
        </p>
      </header>

      <Disclaimer rulesetStatus={config?.ruleset_status} />

      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <ExtractPanel
          note={note}
          setNote={setNote}
          extractionEnabled={config?.extraction_enabled ?? false}
          model={config?.extractor_model ?? "—"}
          onFacts={onExtractedFacts}
        />
        <VerifyFactsPanel facts={facts} setFact={setFact} onRun={runAnalysis} running={running} />
        <ConclusionsPanel
          engine={engine}
          baseline={baseline}
          baselineEnabled={config?.extraction_enabled ?? false}
        />
      </div>

      <footer className="flex flex-wrap justify-between gap-3 pt-2 text-xs text-muted-foreground">
        <span>
          Ruleset {config?.ruleset_version ?? "—"} · prompt {config?.prompt_version ?? "—"} ·
          baseline prompt {config?.baseline_prompt_version ?? "—"}
        </span>
        <span>Thresholds are unverified and awaiting expert sign-off.</span>
      </footer>
    </div>
  );
}
