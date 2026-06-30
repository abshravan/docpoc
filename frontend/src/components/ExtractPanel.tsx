import { useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { runExtractionAgent } from "@/lib/agui";
import type { Facts } from "@/lib/facts";

interface Props {
  note: string;
  setNote: (v: string) => void;
  extractionEnabled: boolean;
  model: string;
  onFacts: (facts: Facts) => void;
}

export function ExtractPanel({ note, setNote, extractionEnabled, model, onFacts }: Props) {
  const [streaming, setStreaming] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function run() {
    if (!note.trim()) {
      setError("Paste a report first.");
      return;
    }
    setError("");
    setMessage("");
    setStreaming(true);
    try {
      await runExtractionAgent(note, {
        onMessage: (d) => setMessage((m) => m + d),
        onState: (s) => s.facts && onFacts(s.facts),
        onError: (m) => setError(m),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setStreaming(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>1 · Extraction</CardTitle>
          <Badge className="bg-[hsl(258,60%,52%)]">LLM</Badge>
        </div>
        <CardDescription>
          {extractionEnabled
            ? `Model: ${model}. Returns structured facts only — never a determination.`
            : "No model configured — enter facts manually in panel 2."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea
          rows={9}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Paste an ultrasound report…"
        />
        <Button onClick={run} disabled={!extractionEnabled || streaming}>
          {streaming ? (
            <>
              <Loader2 className="animate-spin" /> Extracting…
            </>
          ) : (
            <>
              <Sparkles /> Extract facts (AG-UI)
            </>
          )}
        </Button>
        {message && (
          <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
            {message}
          </p>
        )}
        {error && <p className="text-xs text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}
