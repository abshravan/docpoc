import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { EMPTY_FACTS, type Facts, type FactValue } from "@/lib/facts";
import {
  evaluateFacts,
  getConfig,
  getRuleset,
  llmBaseline,
  type AppConfig,
  type BaselineResult,
  type EngineResult,
  type Ruleset,
} from "@/lib/api";

interface Store {
  config: AppConfig | null;
  ruleset: Ruleset | null;
  note: string;
  facts: Facts;
  engine: EngineResult | null;
  baseline: BaselineResult | null;
  running: boolean;
  error: string;
  setNote: (v: string) => void;
  setFact: (name: string, value: FactValue) => void;
  setExtractedFacts: (f: Facts) => void;
  runAnalysis: () => Promise<void>;
}

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [ruleset, setRuleset] = useState<Ruleset | null>(null);
  const [note, setNote] = useState("");
  const [facts, setFacts] = useState<Facts>(EMPTY_FACTS);
  const [engine, setEngine] = useState<EngineResult | null>(null);
  const [baseline, setBaseline] = useState<BaselineResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getConfig().then(setConfig).catch(() => setError("Could not reach the API."));
    getRuleset().then(setRuleset).catch(() => undefined);
  }, []);

  function setFact(name: string, value: FactValue) {
    setFacts((prev) => ({ ...prev, [name]: value }));
  }

  function setExtractedFacts(f: Facts) {
    setFacts({ ...EMPTY_FACTS, ...f });
  }

  async function runAnalysis() {
    setRunning(true);
    setError("");
    setBaseline(null);
    try {
      const result = await evaluateFacts(facts);
      setEngine(result);
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
    note,
    facts,
    engine,
    baseline,
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
