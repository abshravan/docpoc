"use client";

import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Loader2, Upload, FileText, ScanLine } from "lucide-react";
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
import { extractFromFile } from "@/lib/api";
import type { Facts } from "@/lib/facts";
import { cn } from "@/lib/utils";

interface Props {
  note: string;
  setNote: (v: string) => void;
  extractionEnabled: boolean;
  ocrEnabled: boolean;
  model: string;
  onFacts: (facts: Facts) => void;
}

export function ExtractPanel({
  note,
  setNote,
  extractionEnabled,
  ocrEnabled,
  model,
  onFacts,
}: Props) {
  const [streaming, setStreaming] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [ocrText, setOcrText] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setError("");
    setMessage("");
    setUploading(true);
    try {
      const res = await extractFromFile(file);
      setOcrText(res.ocr_text || "");
      if (res.ocr_text) setNote(res.ocr_text);
      if (res.facts) {
        onFacts(res.facts);
        setMessage("Facts read from the scan — verify them in panel 2.");
      } else if (res.extract_error) {
        setError(res.extract_error);
      } else {
        setMessage("Text extracted — no model to parse facts, review panel 2.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  async function runPaste() {
    if (!note.trim()) {
      setError("Paste a report or upload a file first.");
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
          <CardTitle>
            <span className="step-badge mr-2">1</span>Extraction
          </CardTitle>
          <Badge className="bg-[hsl(258,60%,52%)]">LLM + OCR</Badge>
        </div>
        <CardDescription>
          {extractionEnabled
            ? `Model: ${model}. Reads facts only — never a determination.`
            : "No model configured — enter facts manually in panel 2."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* File upload / OCR (primary path) */}
        <motion.div
          whileHover={{ scale: ocrEnabled ? 1.01 : 1 }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f && ocrEnabled) handleFile(f);
          }}
          onClick={() => ocrEnabled && fileInput.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors",
            dragOver ? "border-primary bg-accent" : "border-input hover:border-primary/50",
            !ocrEnabled && "cursor-not-allowed opacity-60"
          )}
        >
          <input
            ref={fileInput}
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
          {uploading ? (
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          ) : (
            <Upload className="h-6 w-6 text-primary" />
          )}
          <div className="text-sm font-medium">
            {uploading ? "Reading scan…" : "Upload scan report"}
          </div>
          <div className="text-xs text-muted-foreground">
            {ocrEnabled
              ? "Drag & drop or click — image or PDF, OCR reads the values"
              : "OCR unavailable on the server — paste text below instead"}
          </div>
        </motion.div>

        <AnimatePresence>
          {ocrText && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="flex items-center gap-1.5 pb-1 text-xs font-medium text-muted-foreground">
                <ScanLine className="h-3.5 w-3.5" /> OCR text
              </div>
              <pre className="max-h-28 overflow-auto rounded-md bg-muted px-3 py-2 text-[11px] leading-snug text-muted-foreground whitespace-pre-wrap">
                {ocrText}
              </pre>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Paste + AG-UI (secondary path) */}
        <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <FileText className="h-3.5 w-3.5" /> or paste report text
        </div>
        <Textarea
          rows={5}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Paste an ultrasound report…"
        />
        <Button
          variant="secondary"
          onClick={runPaste}
          disabled={!extractionEnabled || streaming}
        >
          {streaming ? (
            <>
              <Loader2 className="animate-spin" /> Extracting…
            </>
          ) : (
            <>
              <Sparkles /> Extract from text (AG-UI)
            </>
          )}
        </Button>
        {message && (
          <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">{message}</p>
        )}
        {error && <p className="text-xs text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}
