"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { EMPTY_FACTS, type Facts, type FactValue } from "@/lib/facts";
import {
  compareRulesets,
  evaluateFacts,
  getConfig,
  getRuleset,
  getRulesets,
  llmBaseline,
  type AppConfig,
  type BaselineResult,
  type ComparisonResult,
  type EngineResult,
  type Ruleset,
  type RulesetInfo,
} from "@/lib/api";

interface Store {
  config: AppConfig | null;
  ruleset: Ruleset | null;
  rulesets: RulesetInfo[];
  selectedRuleset: string;
  setSelectedRuleset: (version: string) => void;
  note: string;
  facts: Facts;
  engine: EngineResult | null;
  baseline: BaselineResult | null;
  comparison: ComparisonResult | null;
  running: boolean;
  error: string;
  setNote: (v: string) => void;
  setFact: (name: string, value: FactValue) => void;
  setExtractedFacts: (f: Facts) => void;
  runAnalysis: (rulesetVersion?: string) => Promise<void>;
}

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [ruleset, setRuleset] = useState<Ruleset | null>(null);
  const [rulesets, setRulesets] = useState<RulesetInfo[]>([]);
  const [selectedRuleset, setSelectedRuleset] = useState("");
  const [note, setNote] = useState("");
  const [facts, setFacts] = useState<Facts>(EMPTY_FACTS);
  const [engine, setEngine] = useState<EngineResult | null>(null);
  const [baseline, setBaseline] = useState<BaselineResult | null>(null);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getConfig()
      .then((c) => {
        setConfig(c);
        setSelectedRuleset((prev) => prev || c.ruleset_version);
      })
      .catch(() => setError("Could not reach the API."));
    getRuleset().then(setRuleset).catch(() => undefined);
    getRulesets().then((r) => setRulesets(r.rulesets)).catch(() => undefined);
  }, []);

  function setFact(name: string, value: FactValue) {
    setFacts((prev) => ({ ...prev, [name]: value }));
  }

  function setExtractedFacts(f: Facts) {
    setFacts({ ...EMPTY_FACTS, ...f });
  }

  async function runAnalysis(rulesetVersion?: string) {
    const version = rulesetVersion || selectedRuleset || undefined;
    setRunning(true);
    setError("");
    setBaseline(null);
    setComparison(null);
    try {
      const result = await evaluateFacts(facts, version);
      setEngine(result);
      // Deterministic cross-guideline comparison (independent engine verdicts).
      compareRulesets(facts).then(setComparison).catch(() => setComparison(null));
      // LLM baseline is independent of the engine and never feeds it.
      if (config?.extraction_enabled && note.trim()) {
        llmBaseline(note).then(setBaseline).catch(() => setBaseline(null));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  const value: Store = {
    config,
    ruleset,
    rulesets,
    selectedRuleset,
    setSelectedRuleset,
    note,
    facts,
    engine,
    baseline,
    comparison,
    running,
    error,
    setNote,
    setFact,
    setExtractedFacts,
    runAnalysis,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStore must be used within StoreProvider");
  return ctx;
}
