"use client";

import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Send, Loader2, Lock, Quote } from "lucide-react";
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
import { chatSend, type ChatMessage, type EvidenceCitation } from "@/lib/api";
import { useStore } from "@/store";
import { cn } from "@/lib/utils";

interface Turn extends ChatMessage {
  citations?: EvidenceCitation[];
}

export function ChatPanel() {
  const { facts, config } = useStore();
  const enabled = config?.chat_enabled ?? false;
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setError("");
    const next: Turn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setInput("");
    setBusy(true);
    try {
      const reply = await chatSend(
        next.map(({ role, content }) => ({ role, content })),
        facts
      );
      setTurns((t) => [
        ...t,
        { role: "assistant", content: reply.answer, citations: reply.citations },
      ]);
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="h-4 w-4 text-primary" /> Case discussion
          </CardTitle>
          <Badge variant="outline" className="gap-1 text-[11px]">
            <Lock className="h-3 w-3" /> advisory · does not change the result
          </Badge>
        </div>
        <CardDescription>
          Discuss this case with the model, grounded in the verified facts and the uploaded
          papers. It explains and cites — it never makes the determination.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="max-h-[340px] space-y-3 overflow-auto">
          {turns.length === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">
              {enabled
                ? "Ask about the findings, the guideline, or the evidence…"
                : "No model configured — chat is unavailable."}
            </p>
          )}
          <AnimatePresence initial={false}>
            {turns.map((t, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className={cn("flex", t.role === "user" ? "justify-end" : "justify-start")}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-3 py-2 text-sm",
                    t.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-foreground"
                  )}
                >
                  <p className="whitespace-pre-wrap">{t.content}</p>
                  {t.citations && t.citations.length > 0 && (
                    <div className="mt-2 space-y-1 border-t border-border/50 pt-1.5">
                      {t.citations.map((c, j) => (
                        <div key={j} className="flex gap-1 text-[11px] text-muted-foreground">
                          <Quote className="mt-0.5 h-3 w-3 shrink-0" />
                          <span>
                            <span className="font-medium">[{j + 1}] {c.source}</span> — {c.text.slice(0, 120)}
                            {c.text.length > 120 ? "…" : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={endRef} />
        </div>

        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex gap-2">
          <Input
            value={input}
            disabled={!enabled || busy}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder={enabled ? "Ask about this case…" : "Chat unavailable"}
          />
          <Button onClick={send} disabled={!enabled || busy || !input.trim()}>
            {busy ? <Loader2 className="animate-spin" /> : <Send />}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
