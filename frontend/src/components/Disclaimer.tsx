import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function Disclaimer({ rulesetStatus }: { rulesetStatus?: string }) {
  return (
    <Alert variant="warning">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Research decision-support demo — not a medical device</AlertTitle>
      <AlertDescription>
        This tool does <strong>not</strong> make a diagnosis. The LLM only proposes
        facts; a clinician verifies them; a deterministic engine then reports whether
        published criteria are met. A “suspicious” result recommends follow-up only.
        {rulesetStatus ? (
          <span className="mt-1 block text-xs text-muted-foreground">{rulesetStatus}</span>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
