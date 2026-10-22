import type { AnalysisResult, AuditEntry, DraftReport, EvidenceDocument, Transaction } from "@/src/types/contracts";
import { findings, seedEvidence, transactions } from "@/src/lib/mock-data";
import type { ProofPayApi } from "./client";

const delay = () => new Promise<void>((resolve) => window.setTimeout(resolve, 320 + Math.random() * 400));
export const mockApi: ProofPayApi = {
  async listTransactions(): Promise<Transaction[]> { await delay(); return transactions; },
  async getTransaction(id): Promise<Transaction> { await delay(); const item = transactions.find((entry) => entry.id === id); if (!item) throw new Error("Transaction not found"); return item; },
  async listEvidence(id): Promise<EvidenceDocument[]> { await delay(); return seedEvidence.filter((entry) => entry.transactionId === id); },
  async uploadEvidence(id, files): Promise<EvidenceDocument[]> { await delay(); return files.map((file, index) => ({ id: `mock-${Date.now()}-${index}`, transactionId: id, fileName: file.name, mimeType: file.type || "application/octet-stream", sizeBytes: file.size, docType: /delivery|tracking/i.test(file.name) ? "delivery_receipt" : "other", uploadedAt: new Date().toISOString(), processing: "ready", previewUrl: "" })); },
  async deleteEvidence(id): Promise<void> { await delay(); void id; },
  async analyze(id): Promise<AnalysisResult> { await delay(); return { id: `analysis-${id}`, transactionId: id, runAt: new Date().toISOString(), status: "complete", facts: [], findings, timeline: [], readinessScore: { present: 3, total: 4 } }; },
  async getAnalysis(id): Promise<AnalysisResult> { await delay(); return { id: `analysis-${id}`, transactionId: id, runAt: new Date().toISOString(), status: "complete", facts: [], findings, timeline: [], readinessScore: { present: 3, total: 4 } }; },
  async generateReport(id): Promise<DraftReport> { await delay(); return { id: `report-${id}`, transactionId: id, version: 1, body: "Draft response prepared for merchant review.", citations: {}, warnings: [{ id: "gap", message: "Delivery proof is missing." }], suggestedAttachments: [], approvalState: "draft" }; },
  async updateReport(id, body): Promise<DraftReport> { await delay(); return { id, transactionId: id, version: 2, body, citations: {}, warnings: [], suggestedAttachments: [], approvalState: "draft" }; },
  async approveReport(id): Promise<DraftReport> { await delay(); return { id, transactionId: id, version: 1, body: "", citations: {}, warnings: [], suggestedAttachments: [], approvalState: "approved_ready", approvedAt: new Date().toISOString() }; },
  async getAudit(id): Promise<AuditEntry[]> { await delay(); return [{ id: "a1", at: new Date().toISOString(), actor: "system", action: "Case loaded", transactionId: id }]; },
  async paypalStatus(): Promise<{ connected: boolean; environment: "sandbox" | "mock" }> { await delay(); return { connected: true, environment: "sandbox" }; },
  async connectPaypal(): Promise<{ connected: boolean; environment: "sandbox" | "mock" }> { await delay(); return { connected: true, environment: "sandbox" }; },
};
