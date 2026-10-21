-- PostgreSQL foundation only. The mock API does not execute this schema.
BEGIN;
CREATE TABLE merchants (
    id UUID PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    paypal_transaction_id TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    currency VARCHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    status TEXT NOT NULL,
    transaction_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (merchant_id, paypal_transaction_id),
    UNIQUE (merchant_id, id)
);
CREATE INDEX transactions_merchant_date_idx ON transactions(merchant_id, transaction_date);
CREATE TABLE evidence_documents (
    id UUID PRIMARY KEY,
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    storage_key TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    sha256 VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (merchant_id, storage_key),
    UNIQUE (merchant_id, id)
);
CREATE TABLE evidence_links (
    id UUID PRIMARY KEY,
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    transaction_id UUID NOT NULL,
    evidence_document_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (merchant_id, transaction_id) REFERENCES transactions(merchant_id, id),
    FOREIGN KEY (merchant_id, evidence_document_id) REFERENCES evidence_documents(merchant_id, id),
    UNIQUE (merchant_id, transaction_id, evidence_document_id)
);
CREATE INDEX evidence_links_document_idx ON evidence_links(merchant_id, evidence_document_id);
CREATE TABLE analysis_runs (
    id UUID PRIMARY KEY,
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    transaction_id UUID NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    draft_response TEXT,
    merchant_approval_required BOOLEAN NOT NULL DEFAULT TRUE CHECK (merchant_approval_required),
    failure_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (merchant_id, transaction_id) REFERENCES transactions(merchant_id, id),
    UNIQUE (merchant_id, id)
);
CREATE INDEX analysis_runs_transaction_idx ON analysis_runs(merchant_id, transaction_id, created_at);
CREATE INDEX analysis_runs_status_idx ON analysis_runs(merchant_id, status);
CREATE TABLE findings (
    id UUID PRIMARY KEY,
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    analysis_run_id UUID NOT NULL,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    explanation TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    FOREIGN KEY (merchant_id, analysis_run_id) REFERENCES analysis_runs(merchant_id, id),
    UNIQUE (merchant_id, id)
);
CREATE INDEX findings_analysis_idx ON findings(merchant_id, analysis_run_id);
CREATE TABLE finding_sources (
    id UUID PRIMARY KEY,
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    finding_id UUID NOT NULL,
    evidence_document_id UUID NOT NULL,
    FOREIGN KEY (merchant_id, finding_id) REFERENCES findings(merchant_id, id),
    FOREIGN KEY (merchant_id, evidence_document_id) REFERENCES evidence_documents(merchant_id, id),
    UNIQUE (merchant_id, finding_id, evidence_document_id)
);
CREATE INDEX finding_sources_document_idx ON finding_sources(merchant_id, evidence_document_id);
CREATE TABLE audit_events (
    id UUID PRIMARY KEY,
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    event_type TEXT NOT NULL,
    actor_id TEXT,
    resource_type TEXT,
    resource_id UUID,
    request_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_events_merchant_date_idx ON audit_events(merchant_id, created_at);
COMMIT;
