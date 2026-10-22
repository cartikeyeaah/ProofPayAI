export type TransactionStatus = "completed" | "under_review" | "disputed";
export type DocType = "invoice" | "order_confirmation" | "delivery_receipt" | "customer_message" | "other";
export type ProcessingStatus = "queued" | "parsing" | "extracting" | "ready" | "failed";
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type FindingKind = "missing_evidence" | "mismatch" | "duplicate_or_conflict" | "verified";
export type MatchConfidence = "confirmed" | "likely" | "uncertain";
export type ReviewState = "unreviewed" | "reviewed" | "needs_attention";
export type CaseStage = "collecting" | "analyzed" | "in_review" | "approved_ready";

export interface Transaction {
  id: string; amount: number; currency: string; createdAt: string;
  status: TransactionStatus; customer: { name: string; email: string };
  description?: string; disputeId?: string; disputeReason?: string;
  responseDueBy?: string; source: "paypal_sandbox" | "paypal_live" | "mock_fallback"; caseStage: CaseStage;
}
export interface EvidenceDocument {
  id: string; transactionId: string; fileName: string; mimeType: string;
  sizeBytes: number; docType: DocType; uploadedAt: string; processing: ProcessingStatus;
  processingError?: string; pageCount?: number; previewUrl: string;
}
export interface SourceRef {
  id: string; kind: "document" | "transaction_field"; documentId?: string; page?: number;
  textSpan?: { start: number; end: number; quote: string }; fieldPath?: string; label: string;
}
export interface Finding {
  id: string; kind: FindingKind; severity: Severity; title: string; explanation: string;
  matchConfidence: MatchConfidence; sources: SourceRef[]; expected?: string; found?: string;
  suggestedAction?: string; reviewState: ReviewState; producedBy: "rule" | "llm" | "rule+llm";
}
export interface ExtractedFact {
  id: string; documentId: string;
  key: "invoice_number" | "amount" | "currency" | "date" | "customer_name" | "customer_email" | "order_id" | "carrier" | "tracking_number" | "delivery_date" | "statement";
  value: string; confidence: number; source: SourceRef;
}
export interface TimelineEvent {
  id: string; at: string; label: string;
  type: "payment" | "invoice" | "order" | "shipment" | "delivery" | "message" | "dispute" | "gap";
  source?: SourceRef; findingId?: string; isGap?: boolean;
}
export interface AnalysisResult {
  id: string; transactionId: string; runAt: string; status: "idle" | "running" | "complete" | "failed";
  stage?: "extract" | "match" | "check" | "explain"; facts: ExtractedFact[]; findings: Finding[];
  timeline: TimelineEvent[]; readinessScore: { present: number; total: number };
}
export interface DraftReport {
  id: string; transactionId: string; version: number; body: string; citations: Record<string, SourceRef>;
  warnings: { id: string; message: string; findingId?: string }[];
  suggestedAttachments: { documentId: string; reason: string }[];
  approvalState: "draft" | "approved_ready"; approvedBy?: string; approvedAt?: string;
}
export interface AuditEntry {
  id: string; at: string; actor: "merchant" | "system" | "ai"; action: string; detail?: string; transactionId?: string;
}
