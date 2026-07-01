"use client";

import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileCog,
  Loader2,
  Download,
  AlertTriangle,
  ShieldAlert,
  Upload,
  Lightbulb,
  CheckCircle2,
  BadgeCheck,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  addProposal,
  approveRuleset,
  draftRuleset,
  extractText,
  type DraftProposal,
  type DraftResult,
} from "@/lib/api";
import { useStore } from "@/store";

export function AuthoringPage() {
  const { config } = useStore();
  const enabled = config?.extraction_enabled ?? false;
  const [source, setSource] = useState("");
  const [name, setName] = useState("Drafted ruleset");
  const [version, setVersion] = useState("draft-v1");
  const [draft, setDraft] = useState<DraftResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [approver, setApprover] = useState("");
  const [approveMsg, setApproveMsg] = useState("");
  const [queued, setQueued] = useState<Set<number>>(new Set());
  const fileInput = useRef<HTMLInputElement>(null);

  async function loadFile(file: File) {
    setUploading(true);
    setError("");
    try {
      const { text } = await extractText(file);
      setSource(text);
      setName(file.name.replace(/\.[^.]+$/, "") || "Drafted ruleset");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  async function run() {
    if (!source.trim()) {
      setError("Upload a file or paste source text first.");
      return;
    }
    setError("");
    setApproveMsg("");
    setLoading(true);
    try {
      setDraft(await draftRuleset(source, name, version));
      setQueued(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function approve() {
    if (!draft) return;
    if (!approver.trim()) {
      setError("Enter your name to sign off.");
      return;
    }
    setError("");
    try {
      const res = await approveRuleset(draft.yaml, approver.trim());
      setApproveMsg(`Approved "${res.label}" (${res.version}) — now selectable in Assessment.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function queueProposal(p: DraftProposal, i: number) {
    try {
      await addProposal(p);
      setQueued((q) => new Set(q).add(i));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  function download() {
    if (!draft) return;
    const blob = new Blob([draft.yaml], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${version}.draft.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <FileCog className="h-5 w-5 text-primary" /> Ruleset authoring
        </h2>
        <p className="text-sm text-muted-foreground">
          Upload a paper, draft a candidate ruleset, review it, and sign off. Thresholds become a
          selectable guideline; novel criteria are queued for implementation.
        </p>
      </div>

      <Alert variant="warning">
        <ShieldAlert className="h-4 w-4" />
        <AlertTitle>Human-in-the-loop by design</AlertTitle>
        <AlertDescription>
          Drafts are <strong>UNVERIFIED</strong> (<code>verify: true</code> on every rule) and not
          loaded until a clinician approves. Novel criteria can never be auto-activated — they need a
          coded evaluator + sign-off.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Source</CardTitle>
          <CardDescription>
            {enabled
              ? "Upload a guideline/paper (text or PDF/image via OCR), or paste text."
              : "No model configured — drafting is disabled. Set a provider to enable it."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="name">Ruleset name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="version">Version</Label>
              <Input id="version" value={version} onChange={(e) => setVersion(e.target.value)} />
            </div>
          </div>

          <input
            ref={fileInput}
            type="file"
            accept=".txt,.md,application/pdf,image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) loadFile(f);
            }}
          />
          <Button variant="outline" onClick={() => fileInput.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 className="animate-spin" /> : <Upload />} Upload file
          </Button>

          <Textarea
            rows={7}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="…or paste guideline / paper text describing the diagnostic criteria"
          />
          <Button onClick={run} disabled={!enabled || loading}>
            {loading ? <Loader2 className="animate-spin" /> : <FileCog />} Draft candidate ruleset
          </Button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      <AnimatePresence>
        {draft && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Candidate ruleset (draft)</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{draft.rule_count} rules</Badge>
                    <Button size="sm" variant="outline" onClick={download}>
                      <Download className="h-4 w-4" /> YAML
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {draft.warnings.length > 0 && (
                  <div className="rounded-md bg-suspicious/10 p-2 text-xs">
                    <div className="mb-1 flex items-center gap-1 font-medium text-suspicious">
                      <AlertTriangle className="h-3.5 w-3.5" /> Warnings
                    </div>
                    <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">
                      {draft.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <pre className="max-h-[320px] overflow-auto rounded-md bg-foreground/95 p-3 text-xs leading-relaxed text-background">
                  {draft.yaml}
                </pre>

                <div className="rounded-lg border bg-secondary/40 p-3">
                  <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                    <BadgeCheck className="h-4 w-4 text-ok" /> Clinician sign-off
                  </div>
                  <p className="mb-2 text-xs text-muted-foreground">
                    Only threshold rules with a coded evaluator can be approved. Approving records
                    your name and activates the ruleset for selection in Assessment.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Input
                      value={approver}
                      onChange={(e) => setApprover(e.target.value)}
                      placeholder="Approver name"
                      className="max-w-[220px]"
                    />
                    <Button onClick={approve} disabled={draft.rule_count === 0}>
                      <CheckCircle2 className="h-4 w-4" /> Approve &amp; activate
                    </Button>
                  </div>
                  {approveMsg && <p className="mt-2 text-xs text-ok">{approveMsg}</p>}
                </div>
              </CardContent>
            </Card>

            {draft.proposals.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Lightbulb className="h-4 w-4 text-suspicious" /> Novel criteria proposed
                  </CardTitle>
                  <CardDescription>
                    The source describes criteria the engine doesn&apos;t implement. Queue them for a
                    developer — they are never auto-activated.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  {draft.proposals.map((p, i) => (
                    <div
                      key={i}
                      className="flex items-start justify-between gap-3 rounded-md border border-dashed p-2"
                    >
                      <div>
                        <div className="text-sm font-medium">{p.name}</div>
                        <p className="text-xs text-muted-foreground">{p.description}</p>
                        <div className="text-[10px] text-muted-foreground">{p.citation}</div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={queued.has(i)}
                        onClick={() => queueProposal(p, i)}
                      >
                        {queued.has(i) ? "Queued" : "Queue"}
                      </Button>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
