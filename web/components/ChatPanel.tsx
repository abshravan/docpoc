"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Send, Loader2, Lock, Bot, User, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { chatSend, type ChatMessage, type EvidenceCitation } from "@/lib/api";
import { useStore } from "@/store";
import { cn } from "@/lib/utils";

interface Turn extends ChatMessage {
  citations?: EvidenceCitation[];
}

const SUGGESTIONS = [
  "Why did the engine reach this determination?",
  "What does the guideline say about the CRL cutoff?",
  "What follow-up is recommended here?",
];

function TypingDots() {
  return (
    <div className="flex gap-1 px-1 py-1.5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-muted-foreground/70"
          animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </div>
  );
}

function Avatar({ role }: { role: "user" | "assistant" }) {
  const isUser = role === "user";
  return (
    <div
      className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
        isUser ? "bg-primary text-primary-foreground" : "brand-gradient text-white"
      )}
    >
      {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
    </div>
  );
}

export function ChatPanel() {
  const { facts, config } = useStore();
  const enabled = config?.chat_enabled ?? false;
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy || !enabled) return;
    setError("");
    const next: Turn[] = [...turns, { role: "user", content }];
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
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b bg-gradient-to-r from-accent/60 to-transparent px-5 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg brand-gradient text-white shadow-sm">
            <MessageSquare className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold leading-tight">Case discussion</div>
            <div className="text-[11px] text-muted-foreground">
              Grounded in the verified facts + uploaded papers
            </div>
          </div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border bg-background/70 px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
          <Lock className="h-3 w-3" /> advisory · never changes the result
        </span>
      </div>

      <CardContent className="flex min-h-0 flex-1 flex-col p-0">
        {/* Messages */}
        <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-auto px-5 py-4">
          {turns.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 py-8 text-center">
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="flex h-12 w-12 items-center justify-center rounded-2xl brand-gradient text-white shadow-md"
              >
                <Sparkles className="h-6 w-6" />
              </motion.div>
              <p className="text-sm text-muted-foreground">
                {enabled
                  ? "Ask about the findings, the guideline, or the evidence."
                  : "No model configured — chat is unavailable."}
              </p>
              {enabled && (
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((s) => (
                    <motion.button
                      key={s}
                      whileHover={{ scale: 1.04 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => send(s)}
                      className="rounded-full border bg-secondary px-3 py-1.5 text-xs text-secondary-foreground hover:border-primary/40 hover:bg-accent"
                    >
                      {s}
                    </motion.button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {turns.map((t, i) => {
                const isUser = t.role === "user";
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 10, x: isUser ? 12 : -12 }}
                    animate={{ opacity: 1, y: 0, x: 0 }}
                    transition={{ type: "spring", stiffness: 260, damping: 24 }}
                    className={cn("flex items-end gap-2", isUser && "flex-row-reverse")}
                  >
                    <Avatar role={t.role} />
                    <div
                      className={cn(
                        "max-w-[78%] rounded-2xl px-3.5 py-2.5 text-sm shadow-sm",
                        isUser
                          ? "rounded-br-sm bg-primary text-primary-foreground"
                          : "rounded-bl-sm bg-muted text-foreground"
                      )}
                    >
                      <p className="whitespace-pre-wrap leading-relaxed">{t.content}</p>
                      {t.citations && t.citations.length > 0 && (
                        <div className="mt-2 space-y-1 border-t border-border/40 pt-1.5">
                          {t.citations.map((c, j) => (
                            <div key={j} className="text-[11px] text-muted-foreground">
                              <span className="font-medium">[{j + 1}] {c.source}</span> —{" "}
                              {c.text.slice(0, 110)}
                              {c.text.length > 110 ? "…" : ""}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          )}

          {busy && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-end gap-2"
            >
              <Avatar role="assistant" />
              <div className="rounded-2xl rounded-bl-sm bg-muted px-2 py-1">
                <TypingDots />
              </div>
            </motion.div>
          )}
        </div>

        {error && <p className="px-5 pb-2 text-xs text-destructive">{error}</p>}

        {/* Composer */}
        <div className="border-t bg-background/60 p-3">
          <div className="flex items-center gap-2 rounded-full border bg-background px-2 py-1 shadow-sm focus-within:ring-1 focus-within:ring-ring">
            <input
              value={input}
              disabled={!enabled || busy}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(input)}
              placeholder={enabled ? "Ask about this case…" : "Chat unavailable"}
              className="flex-1 bg-transparent px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
            />
            <Button
              size="icon"
              className="h-8 w-8 rounded-full"
              onClick={() => send(input)}
              disabled={!enabled || busy || !input.trim()}
            >
              {busy ? <Loader2 className="animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
