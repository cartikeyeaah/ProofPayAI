import type { AnalysisResult, AuditEntry, DraftReport, EvidenceDocument, Transaction } from "@/src/types/contracts";

export interface ProofPayApi {
  listTransactions(): Promise<Transaction[]>;
  getTransaction(id: string): Promise<Transaction>;
  listEvidence(id: string): Promise<EvidenceDocument[]>;
  uploadEvidence(id: string, files: File[]): Promise<EvidenceDocument[]>;
  deleteEvidence(id: string): Promise<void>;
  analyze(id: string): Promise<AnalysisResult>;
  getAnalysis(id: string): Promise<AnalysisResult>;
  generateReport(id: string): Promise<DraftReport>;
  updateReport(id: string, body: string): Promise<DraftReport>;
  approveReport(id: string): Promise<DraftReport>;
  getAudit(id: string): Promise<AuditEntry[]>;
  paypalStatus(): Promise<{ connected: boolean; environment: "sandbox" | "mock" }>;
  connectPaypal(): Promise<{ connected: boolean; environment: "sandbox" | "mock" }>;
}

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, init);
  if (!response.ok) throw new Error(`ProofPay service error (${response.status})`);
  return response.json() as Promise<T>;
}
export const httpApi: ProofPayApi = {
  listTransactions: () => request("/transactions"),
  getTransaction: (id) => request(`/transactions/${encodeURIComponent(id)}`),
  listEvidence: (id) => request(`/transactions/${encodeURIComponent(id)}/evidence`),
  uploadEvidence: (id, files) => { const body = new FormData(); files.forEach((file) => body.append("files", file)); return request(`/transactions/${encodeURIComponent(id)}/evidence`, { method: "POST", body }); },
  deleteEvidence: (id) => request(`/evidence/${encodeURIComponent(id)}`, { method: "DELETE" }).then(() => undefined),
  analyze: (id) => request(`/transactions/${encodeURIComponent(id)}/analyze`, { method: "POST" }),
  getAnalysis: (id) => request(`/transactions/${encodeURIComponent(id)}/analysis`),
  generateReport: (id) => request(`/transactions/${encodeURIComponent(id)}/report/generate`, { method: "POST" }),
  updateReport: (id, body) => request(`/reports/${encodeURIComponent(id)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body }) }),
  approveReport: (id) => request(`/reports/${encodeURIComponent(id)}/approve`, { method: "POST" }),
  getAudit: (id) => request(`/audit?transactionId=${encodeURIComponent(id)}`),
  paypalStatus: () => request("/integrations/paypal/status"),
  connectPaypal: () => request("/integrations/paypal/connect", { method: "POST" }),
};
