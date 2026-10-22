import type { EvidenceDocument, Finding, SourceRef, Transaction } from "@/src/types/contracts";

export const demoId = "PP-7K92-2041";
export const transactions: Transaction[] = [
  { id: demoId, amount: 150, currency: "USD", createdAt: "2026-10-16T14:32:00Z", status: "disputed", customer: { name: "Priya Nair", email: "priya.nair@example.com" }, description: "Ceramic pour-over set · Order 88213", disputeId: "PP-D-2041", disputeReason: "Item not received", responseDueBy: "2026-10-28T18:00:00Z", source: "paypal_sandbox", caseStage: "analyzed" },
  { id: "PP-7K92-2038", amount: 82.5, currency: "USD", createdAt: "2026-10-21T09:14:00Z", status: "under_review", customer: { name: "Marcus Lee", email: "marcus.lee@example.com" }, description: "Linen table runner", source: "paypal_sandbox", caseStage: "collecting" },
  { id: "PP-7K92-2034", amount: 324, currency: "USD", createdAt: "2026-10-20T16:48:00Z", status: "completed", customer: { name: "Elena Rossi", email: "elena.rossi@example.com" }, description: "Hand-thrown dinner set", source: "paypal_sandbox", caseStage: "approved_ready" },
  { id: "PP-7K92-2029", amount: 46, currency: "USD", createdAt: "2026-10-19T11:02:00Z", status: "completed", customer: { name: "Ava Chen", email: "ava.chen@example.com" }, source: "mock_fallback", caseStage: "analyzed" },
  { id: "PP-7K92-2021", amount: 210, currency: "USD", createdAt: "2026-10-18T08:33:00Z", status: "disputed", customer: { name: "Noah Williams", email: "noah.williams@example.com" }, disputeReason: "Unrecognized transaction", source: "mock_fallback", caseStage: "collecting" },
  { id: "PP-7K92-2017", amount: 118, currency: "USD", createdAt: "2026-10-17T17:20:00Z", status: "completed", customer: { name: "Sofia Patel", email: "sofia.patel@example.com" }, source: "paypal_sandbox", caseStage: "analyzed" },
  { id: "PP-7K92-2012", amount: 65, currency: "USD", createdAt: "2026-10-16T13:05:00Z", status: "completed", customer: { name: "Theo Martin", email: "theo.martin@example.com" }, source: "mock_fallback", caseStage: "collecting" },
  { id: "PP-7K92-2008", amount: 490, currency: "USD", createdAt: "2026-10-15T10:14:00Z", status: "under_review", customer: { name: "Mina Park", email: "mina.park@example.com" }, source: "paypal_sandbox", caseStage: "in_review" },
  { id: "PP-7K92-2002", amount: 39, currency: "USD", createdAt: "2026-10-14T12:51:00Z", status: "completed", customer: { name: "Jules Carter", email: "jules.carter@example.com" }, source: "mock_fallback", caseStage: "approved_ready" },
  { id: "PP-7K92-1997", amount: 175, currency: "USD", createdAt: "2026-10-13T15:41:00Z", status: "completed", customer: { name: "Iris Shah", email: "iris.shah@example.com" }, source: "paypal_sandbox", caseStage: "analyzed" },
  { id: "PP-7K92-1991", amount: 92, currency: "USD", createdAt: "2026-10-12T08:15:00Z", status: "completed", customer: { name: "Oliver Grant", email: "oliver.grant@example.com" }, source: "mock_fallback", caseStage: "collecting" },
  { id: "PP-7K92-1986", amount: 260, currency: "USD", createdAt: "2026-10-11T19:27:00Z", status: "completed", customer: { name: "Amara Okafor", email: "amara.okafor@example.com" }, source: "paypal_sandbox", caseStage: "in_review" },
];

export const seedEvidence: EvidenceDocument[] = [
  { id: "doc-invoice", transactionId: demoId, fileName: "invoice_INV-2041.pdf", mimeType: "application/pdf", sizeBytes: 182400, docType: "invoice", uploadedAt: "2026-10-17T10:08:00Z", processing: "ready", pageCount: 1, previewUrl: "" },
  { id: "doc-order", transactionId: demoId, fileName: "order_confirmation_88213.pdf", mimeType: "application/pdf", sizeBytes: 241000, docType: "order_confirmation", uploadedAt: "2026-10-17T10:09:00Z", processing: "ready", pageCount: 2, previewUrl: "" },
  { id: "doc-message", transactionId: demoId, fileName: "customer_messages.txt", mimeType: "text/plain", sizeBytes: 3200, docType: "customer_message", uploadedAt: "2026-10-17T10:10:00Z", processing: "ready", previewUrl: "" },
];

const invoiceRef: SourceRef = { id: "S1", kind: "document", documentId: "doc-invoice", page: 1, textSpan: { start: 0, end: 28, quote: "Total paid: $150.00 USD" }, label: "Invoice INV-2041 · p.1" };
const orderRef: SourceRef = { id: "S2", kind: "document", documentId: "doc-order", page: 1, textSpan: { start: 0, end: 26, quote: "Order confirmation 88213" }, label: "Order confirmation · p.1" };
const paymentRef: SourceRef = { id: "S3", kind: "transaction_field", fieldPath: "transaction.amount", label: "PayPal payment amount" };
const messageRef: SourceRef = { id: "S4", kind: "document", documentId: "doc-message", textSpan: { start: 0, end: 54, quote: "Priya N.: I still haven't received my package." }, label: "Customer message · line 1" };
export const findings: Finding[] = [
  { id: "f-invoice", kind: "verified", severity: "info", title: "Invoice amount matches the payment", explanation: "The invoice total is $150.00 USD, matching the PayPal transaction amount.", matchConfidence: "confirmed", sources: [invoiceRef, paymentRef], reviewState: "unreviewed", producedBy: "rule" },
  { id: "f-order", kind: "verified", severity: "info", title: "Order confirmation is present", explanation: "Order 88213 is present in the supplied documents and matches the transaction description.", matchConfidence: "confirmed", sources: [orderRef], reviewState: "unreviewed", producedBy: "rule" },
  { id: "f-delivery", kind: "missing_evidence", severity: "critical", title: "No delivery receipt found", explanation: "No delivery receipt was found in the supplied documents. The customer message also says the package has not arrived.", matchConfidence: "likely", sources: [messageRef], suggestedAction: "Request valid delivery proof from your carrier or fulfilment provider. Do not infer the outcome.", reviewState: "unreviewed", producedBy: "rule+llm" },
  { id: "f-name", kind: "mismatch", severity: "medium", title: "Customer name needs a human check", explanation: "The message uses “Priya N.” while the PayPal payer name is “Priya Nair”. This may be an abbreviation; verify it before approval.", matchConfidence: "uncertain", expected: "Priya Nair", found: "Priya N.", sources: [messageRef], reviewState: "needs_attention", producedBy: "rule+llm" },
];
