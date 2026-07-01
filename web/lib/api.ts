import type { Facts } from "./facts";

export interface AppConfig {
  extraction_enabled: boolean;
  ocr_enabled: boolean;
  chat_enabled: boolean;
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
  ruleset_label?: string;
  facts: Facts;
}

export interface RuleDetail {
  id: string;
  tier: string;
  description: string;
  citation: string;
  params: Record<string, number>;
}

export interface RulesetInfo {
  label: string;
  version: string;
  status: string;
  rule_count: number;
  rules?: RuleDetail[];
}

export interface ProposedMethod {
  name: string;
  description: string;
  citation: string;
  status: string;
  created_at: string;
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

export function getRulesets(): Promise<{ rulesets: RulesetInfo[] }> {
  return fetch("/api/rulesets").then((r) => r.json());
}

function dropNulls(facts: Facts): Facts {
  const clean: Facts = {};
  for (const [k, v] of Object.entries(facts)) if (v !== null) clean[k] = v;
  return clean;
}

export function evaluateFacts(facts: Facts, rulesetVersion?: string): Promise<EngineResult> {
  return postJson<EngineResult>("/api/evaluate", {
    facts: dropNulls(facts),
    ruleset_version: rulesetVersion,
  });
}

export function llmBaseline(note: string): Promise<BaselineResult> {
  return postJson<BaselineResult>("/api/baseline", { note });
}

export interface FileExtractResult {
  ocr_text: string;
  facts?: Facts;
  extract_error?: string;
}

export async function extractFromFile(file: File): Promise<FileExtractResult> {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("/api/extract/file", { method: "POST", body: form });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data?.error || `Upload failed (${resp.status})`);
  return data as FileExtractResult;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatReply {
  answer: string;
  advisory: true;
  citations: EvidenceCitation[];
}

export function chatSend(messages: ChatMessage[], facts: Facts): Promise<ChatReply> {
  return postJson<ChatReply>("/api/chat", { messages, facts: dropNulls(facts) });
}

export function compareRulesets(facts: Facts): Promise<ComparisonResult> {
  const clean: Facts = {};
  for (const [k, v] of Object.entries(facts)) if (v !== null) clean[k] = v;
  return postJson<ComparisonResult>("/api/compare", { facts: clean });
}

export interface EvidenceCitation {
  source: string;
  text: string;
}

export interface EvidenceStatus {
  enabled: boolean;
  chunks: number;
  sources: string[];
  embed_provider: string;
  synthesis: boolean;
}

export interface EvidenceAnswer {
  answer: string;
  synthesized: boolean;
  prompt_version: string;
  citations: EvidenceCitation[];
}

export function getEvidenceStatus(): Promise<EvidenceStatus> {
  return fetch("/api/evidence/status").then((r) => r.json());
}

export function askEvidence(question: string): Promise<EvidenceAnswer> {
  return postJson<EvidenceAnswer>("/api/evidence", { question });
}

export interface DraftProposal {
  name: string;
  description: string;
  citation: string;
}

export interface DraftResult {
  yaml: string;
  rule_count: number;
  warnings: string[];
  prompt_version: string;
  proposals: DraftProposal[];
  activated: false;
}

export function draftRuleset(
  source_text: string,
  name: string,
  version: string
): Promise<DraftResult> {
  return postJson<DraftResult>("/api/authoring/draft", { source_text, name, version });
}

export function approveRuleset(
  yaml: string,
  approver: string
): Promise<{ activated: boolean; version: string; label: string }> {
  return postJson("/api/authoring/approve", { yaml, approver });
}

export function listProposals(): Promise<{ proposals: ProposedMethod[] }> {
  return fetch("/api/proposals").then((r) => r.json());
}

export function addProposal(p: DraftProposal): Promise<{ ok: boolean }> {
  return postJson("/api/proposals", p);
}

export function listPapers(): Promise<{ sources: string[] }> {
  return fetch("/api/papers").then((r) => r.json());
}

export async function uploadPaper(
  file: File
): Promise<{ source: string; chunks_added: number; total_chunks: number }> {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("/api/papers", { method: "POST", body: form });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data?.error || `Upload failed (${resp.status})`);
  return data;
}

export async function extractText(file: File): Promise<{ text: string }> {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("/api/extract/text", { method: "POST", body: form });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data?.error || `Extract failed (${resp.status})`);
  return data;
}
