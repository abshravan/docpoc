"use client";

import { useState } from "react";
import { FileCog, Loader2, Download, AlertTriangle, ShieldAlert } from "lucide-react";
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
import { draftRuleset, type DraftResult } from "@/lib/api";
import { useStore } from "@/store";

export function AuthoringPage() {
  const { config } = useStore();
  const enabled = config?.extraction_enabled ?? false;
  const [source, setSource] = useState("");
  const [name, setName] = useState("Drafted ruleset");
  const [version, setVersion] = useState("draft-v1");
  const [draft, setDraft] = useState<DraftResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    if (!source.trim()) {
      setError("Paste some source text first.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      setDraft(await draftRuleset(source, name, version));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
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
          <FileCog className="h-5 w-5 text-primary" /> Ruleset authoring aid
        </h2>
        <p className="text-sm text-muted-foreground">
          Draft a candidate ruleset from a paper's text. The model only fills thresholds
          for known criteria — it cannot invent new ones.
        </p>
      </div>

      <Alert variant="warning">
        <ShieldAlert className="h-4 w-4" />
        <AlertTitle>Drafts only — never activated</AlertTitle>
        <AlertDescription>
          Output is <strong>UNVERIFIED</strong>, with <code>verify: true</code> on every rule.
          It is not loaded by the engine. A domain expert must review, correct, and sign off
          before the file is placed in the knowledge directory.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Source text</CardTitle>
          <CardDescription>
            {enabled
              ? "Paste the relevant section(s) of a guideline/paper."
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
          <Textarea
            rows={8}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Paste guideline / paper text describing the diagnostic criteria…"
          />
          <Button onClick={run} disabled={!enabled || loading}>
            {loading ? <Loader2 className="animate-spin" /> : <FileCog />}
            Draft candidate ruleset
          </Button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {draft && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Candidate ruleset (draft)</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{draft.rule_count} rules</Badge>
                <Button size="sm" variant="outline" onClick={download}>
                  <Download className="h-4 w-4" /> Download YAML
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {draft.warnings.length > 0 && (
              <div className="rounded-md bg-suspicious/10 p-2 text-xs text-foreground">
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
            <pre className="max-h-[420px] overflow-auto rounded-md bg-foreground/95 p-3 text-xs leading-relaxed text-background">
              {draft.yaml}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
