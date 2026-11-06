export type StepStatus = "queued" | "running" | "done" | "error";

export interface Step {
  id: number;
  key: string;
  title: string;
  description: string;
  status: StepStatus;
}

export interface LogEntry {
  time: string;
  type: string;
  message: string;
}

export type VerificationStatus = "POSITIVE" | "NEGATIVE";

export interface VerificationResult {
  status: VerificationStatus;
  invoice_price: number;
  ab_price: number;
  difference: number;
  tolerance: number;
  discrepancies: string[];
  ab_number?: string | null;
  invoice_number?: string | null;
  ab_filename?: string | null;
  invoice_filename?: string | null;
  checked_at: string;
}

export type JobState = "running" | "completed" | "error";

export interface JobSnapshot {
  run_id: string;
  state: JobState;
  steps: Step[];
  log: LogEntry[];
  result?: VerificationResult | null;
  error?: string | null;
}

export interface RuleConfig {
  price_tolerance_eur: number;
}
