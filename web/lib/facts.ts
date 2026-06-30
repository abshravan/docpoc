// The fact schema, mirrored from epl_cds.contracts.Facts. Keep in sync with the
// backend; the engine only ever sees what the clinician confirms here.

export type FactValue = number | boolean | null;
export type Facts = Record<string, FactValue>;

export type FactKind = "number" | "int" | "bool";

export interface FactField {
  name: string;
  label: string;
  kind: FactKind;
  unit?: string;
  hint?: string;
}

export const FACT_FIELDS: FactField[] = [
  { name: "crl_mm", label: "Crown-rump length", kind: "number", unit: "mm" },
  { name: "cardiac_activity", label: "Cardiac activity", kind: "bool" },
  { name: "msd_mm", label: "Mean sac diameter", kind: "number", unit: "mm" },
  { name: "embryo_visible", label: "Embryo visible", kind: "bool" },
  { name: "yolk_sac_visible", label: "Yolk sac visible", kind: "bool" },
  { name: "yolk_sac_diameter_mm", label: "Yolk sac diameter", kind: "number", unit: "mm" },
  { name: "amnion_visible", label: "Amnion visible", kind: "bool" },
  {
    name: "days_since_sac_without_yolk",
    label: "Days since prior scan — sac without yolk",
    kind: "int",
    unit: "days",
  },
  {
    name: "days_since_sac_with_yolk",
    label: "Days since prior scan — sac with yolk",
    kind: "int",
    unit: "days",
  },
  { name: "days_since_lmp", label: "Days since last menstrual period", kind: "int", unit: "days" },
];

export const EMPTY_FACTS: Facts = Object.fromEntries(
  FACT_FIELDS.map((f) => [f.name, null])
);

export type Tier = "diagnostic_of_loss" | "suspicious_for_loss" | "no_criteria_met";

export const TIER_LABEL: Record<string, string> = {
  diagnostic_of_loss: "Diagnostic of loss",
  suspicious_for_loss: "Suspicious for loss",
  no_criteria_met: "No criteria met",
};
