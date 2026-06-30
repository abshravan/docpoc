"use client";

import { useEffect, useState } from "react";
import { BookOpen, Search, Loader2, Quote } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  askEvidence,
  getEvidenceStatus,
  type EvidenceAnswer,
  type EvidenceStatus,
} from "@/lib/api";

const SUGGESTIONS = [
  "What is the CRL threshold for diagnosing loss with no heartbeat?",
  "Why is the mean sac diameter cutoff set at 25 mm?",
  "Why is specificity prioritized in these criteria?",
];

export function EvidencePage() {
  const [status, setStatus] = useState<EvidenceStatus | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<EvidenceAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getEvidenceStatus().then(setStatus).catch(() => setError("Evidence API unavailable."));
  }, []);

  async function ask(q: string) {
    const query = q.trim();
    if (!query) return;
    setQuestion(query);
    setLoading(true);
    setError("");
    try {
      setAnswer(await askEvidence(query));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <BookOpen className="h-5 w-5 text-primary" /> Evidence lookup
        </h2>
        <p className="text-sm text-muted-foreground">
          Retrieval-augmented search over the literature corpus. Answers are grounded in
          and cite retrieved passages. This is explainability — it never affects a determination.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Ask about the criteria</CardTitle>
            {status && (
              <Badge variant="secondary" className="text-[11px]">
                {status.chunks} passages · {status.embed_provider}
                {status.synthesis ? " · synthesis on" : " · retrieval only"}
              </Badge>
            )}
          </div>
          <CardDescription>
            {status && !status.synthesis
              ? "No model configured — returns the most relevant cited passages (no synthesized answer)."
              : "Returns a grounded answer plus the passages it cites."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask(question)}
              placeholder="e.g. What is the evidence for the 7 mm CRL cutoff?"
            />
            <Button onClick={() => ask(question)} disabled={loading}>
              {loading ? <Loader2 className="animate-spin" /> : <Search />}
              Ask
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => ask(s)}
                className="rounded-full border bg-secondary px-3 py-1 text-xs text-secondary-foreground hover:bg-accent"
              >
                {s}
              </button>
            ))}
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {answer && (
        <Card>
          <CardContent className="space-y-4 pt-5">
            {answer.synthesized && answer.answer && (
              <div>
                <div className="mb-1 text-xs font-medium text-muted-foreground">
                  Grounded answer
                </div>
                <p className="whitespace-pre-wrap text-sm">{answer.answer}</p>
              </div>
            )}
            <div>
              <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Quote className="h-3.5 w-3.5" /> Cited passages
              </div>
              <ul className="space-y-2">
                {answer.citations.map((c, i) => (
                  <li key={i} className="rounded-md border-l-2 border-primary/40 bg-muted/50 p-2 text-xs">
                    <span className="font-semibold">[{i + 1}] {c.source}</span>
                    <p className="mt-1 text-muted-foreground">{c.text}</p>
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
