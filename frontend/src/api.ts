import type { JobSnapshot, RuleConfig } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`.trim();
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function getRules(): Promise<RuleConfig> {
  return parse<RuleConfig>(await fetch(`${BASE}/rules`));
}

export async function saveRules(config: RuleConfig): Promise<RuleConfig> {
  return parse<RuleConfig>(
    await fetch(`${BASE}/rules`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }),
  );
}

export async function createVerification(
  abFile: File,
  invoiceFile: File,
  priceToleranceEur?: number,
): Promise<JobSnapshot> {
  const form = new FormData();
  form.append("ab_file", abFile);
  form.append("invoice_file", invoiceFile);
  if (priceToleranceEur !== undefined) {
    form.append("price_tolerance_eur", String(priceToleranceEur));
  }
  return parse<JobSnapshot>(
    await fetch(`${BASE}/verifications`, { method: "POST", body: form }),
  );
}

export async function getVerification(runId: string): Promise<JobSnapshot> {
  return parse<JobSnapshot>(await fetch(`${BASE}/verifications/${runId}`));
}
