"use client";

import { ShieldCheck, Loader2, ArrowRight } from "lucide-react";
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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FACT_FIELDS, type FactField, type Facts, type FactValue } from "@/lib/facts";

interface Props {
  facts: Facts;
  setFact: (name: string, value: FactValue) => void;
  onRun: () => void;
  running: boolean;
}

function boolToStr(v: FactValue): string {
  if (v === true) return "true";
  if (v === false) return "false";
  return "unknown";
}

function FieldRow({
  field,
  value,
  setFact,
}: {
  field: FactField;
  value: FactValue;
  setFact: (name: string, value: FactValue) => void;
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={field.name}>
        {field.label}
        {field.unit ? <span className="ml-1 opacity-60">({field.unit})</span> : null}
      </Label>
      {field.kind === "bool" ? (
        <Select
          value={boolToStr(value)}
          onValueChange={(v) =>
            setFact(field.name, v === "unknown" ? null : v === "true")
          }
        >
          <SelectTrigger id={field.name}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="unknown">unknown</SelectItem>
            <SelectItem value="true">present / yes</SelectItem>
            <SelectItem value="false">absent / no</SelectItem>
          </SelectContent>
        </Select>
      ) : (
        <Input
          id={field.name}
          type="number"
          step={field.kind === "int" ? "1" : "0.1"}
          value={value === null ? "" : String(value)}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === "") return setFact(field.name, null);
            const n = field.kind === "int" ? parseInt(raw, 10) : parseFloat(raw);
            setFact(field.name, Number.isNaN(n) ? null : n);
          }}
          placeholder="not documented"
        />
      )}
    </div>
  );
}

export function VerifyFactsPanel({ facts, setFact, onRun, running }: Props) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>2 · Verify facts</CardTitle>
          <Badge className="bg-[hsl(190,63%,34%)]">Clinician</Badge>
        </div>
        <CardDescription>
          Correct anything the model got wrong. The engine sees only what you confirm.
          Blank = not documented. <em>Bound to the AG-UI agent state.</em>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {FACT_FIELDS.map((f) => (
            <FieldRow key={f.name} field={f} value={facts[f.name] ?? null} setFact={setFact} />
          ))}
        </div>
        <Button className="w-full" onClick={onRun} disabled={running}>
          {running ? (
            <>
              <Loader2 className="animate-spin" /> Analyzing…
            </>
          ) : (
            <>
              <ShieldCheck /> Run engine + LLM baseline <ArrowRight />
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
