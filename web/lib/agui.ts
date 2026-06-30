// AG-UI protocol consumer. The backend (/api/agui/extract) emits canonical
// AG-UI events over SSE; the extraction agent proposes Facts as shared state
// (STATE_SNAPSHOT), which the Verify-facts panel binds to. We use @ag-ui/core's
// EventType so the event vocabulary is the real protocol's, not ad-hoc strings.

import { EventType } from "@ag-ui/core";
import type { Facts } from "./facts";

export interface AguiHandlers {
  onMessage?: (delta: string) => void;
  onState?: (state: { facts?: Facts; promptVersion?: string }) => void;
  onError?: (message: string, code?: string) => void;
  onFinish?: () => void;
}

export async function runExtractionAgent(
  note: string,
  handlers: AguiHandlers,
  signal?: AbortSignal
): Promise<void> {
  const resp = await fetch("/api/agui/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      note,
      threadId: crypto.randomUUID(),
      runId: crypto.randomUUID(),
    }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    handlers.onError?.(`Extraction request failed (${resp.status})`);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep).trim();
      buffer = buffer.slice(sep + 2);
      if (!frame.startsWith("data:")) continue;
      const payload = frame.slice(frame.indexOf(":") + 1).trim();
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(payload);
      } catch {
        continue;
      }
      dispatch(event, handlers);
    }
  }
}

function dispatch(event: Record<string, unknown>, h: AguiHandlers): void {
  switch (event.type) {
    case EventType.TEXT_MESSAGE_CONTENT:
      h.onMessage?.(String(event.delta ?? ""));
      break;
    case EventType.STATE_SNAPSHOT:
      h.onState?.((event.snapshot as { facts?: Facts }) ?? {});
      break;
    case EventType.RUN_ERROR:
      h.onError?.(String(event.message ?? "Run error"), event.code as string | undefined);
      break;
    case EventType.RUN_FINISHED:
      h.onFinish?.();
      break;
    default:
      break;
  }
}
