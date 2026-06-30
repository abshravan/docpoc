import type { Facts } from "./facts";

export interface AppConfig {
  extraction_enabled: boolean;
  extractor_model: string;
  ruleset_version: string;
  ruleset_status: string;
  prompt_version: string;
  baseline_prompt_version: string;
  fact_fields: string[];
}

export interface FiredRule {
  id: string;
  tier: string;
  description: string;
  citation: string;
}

export interface EngineResult {
  determination: string;
  fired_rules: FiredRule[];
  rationale: string;
  ruleset_version: string;
  facts: Facts;
}

export interface BaselineResult {
  determination: string | null;
  rationale: string;
  model: string;
  prompt_version: string;
  authoritative: false;
}

export interface ComparisonEntry {
  label: string;
  version: string;
  determination: string;
  rationale: string;
  fired_rules: FiredRule[];
}

export interface ComparisonResult {
  concordant: boolean;
  entries: ComparisonEntry[];
}

export interface RulesetRule {
  id: string;
  tier: "diagnostic" | "suspicious";
  description: string;
  citation: string;
  params: Record<string, number>;
}

export interface Ruleset {
  version: string;
  status: string;
  rules: RulesetRule[];
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data?.error || `Request failed (${resp.status})`);
  return data as T;
}

export function getConfig(): Promise<AppConfig> {
  return fetch("/api/config").then((r) => r.json());
}

export function getRuleset(): Promise<Ruleset> {
  return fetch("/api/ruleset").then((r) => r.json());
}

export function evaluateFacts(facts: Facts): Promise<EngineResult> {
  // Drop nulls so the engine treats them as "not documented".
  const clean: Facts = {};
  for (const [k, v] of Object.entries(facts)) if (v !== null) clean[k] = v;
  return postJson<EngineResult>("/api/evaluate", { facts: clean });
}

export function llmBaseline(note: string): Promise<BaselineResult> {
  return postJson<BaselineResult>("/api/baseline", { note });
}

export function compareRulesets(facts: Facts): Promise<ComparisonResult> {
  const clean: Facts = {};
  for (const [k, v] of Object.entries(facts)) if (v !== null) clean[k] = v;
  return postJson<ComparisonResult>("/api/compare", { facts: clean });
}
