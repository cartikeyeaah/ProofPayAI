from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4, uuid5, NAMESPACE_URL
from threading import RLock
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert
from . import models as m
from backend.app.mock_data import MockStore, TRANSACTION
from backend.app.schemas import Transaction, Analysis
from backend.app.integration_schemas import EvidenceMetadata, AnalysisDetails

def now(): return datetime.now(timezone.utc)
def internal(merchant, key): return str(uuid5(NAMESPACE_URL, merchant + ':' + key))
def event(store, action, resource_id, actor='system'):
    store.events.append({'id': str(uuid4()), 'action': action, 'resource_id': resource_id, 'actor': actor, 'created_at': now().isoformat()})

def get_store(request): return getattr(request.state, 'store', request.app.state.store)
def save(store):
    if store.repository is not None:
        try: store.repository.save(store)
        except Exception:
            # Failed writes must never remain visible as a committed cached mutation.
            with store.repository.lock: store.repository.stores.pop(store.merchant_id, None)
            raise

class Repository:
    def __init__(self, url, storage_root):
        if not url.startswith('postgresql+psycopg://'): raise RuntimeError('PostgreSQL psycopg URL required')
        self.engine = create_engine(url, pool_pre_ping=True)
        self.root = Path(storage_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.stores = {}
        self.lock = RLock()
        self.lease = self.engine.connect()
        # One supervisor per database: cached stores must never race across processes.
        from sqlalchemy import text
        if not self.lease.execute(text('SELECT pg_try_advisory_lock(6170251022)')).scalar():
            self.lease.close()
            raise RuntimeError('Another ProofPay backend owns this database; use one worker.')
        self.lease.commit()

    def close(self):
        self.lease.close(); self.engine.dispose()

    def store(self, merchant):
        with self.lock:
            if merchant in self.stores: return self.stores[merchant]
            store = MockStore()
            store.storage.cleanup()
            folder = self.root / merchant
            folder.mkdir(mode=0o700, exist_ok=True)
            store.storage = SimpleNamespace(name=str(folder), cleanup=lambda: None)
            store.repository, store.merchant_id = self, merchant
            store.transactions = {}
            with self.engine.connect() as conn:
                for row in conn.execute(select(m.transactions).where(m.transactions.c.merchant_id == merchant)).mappings():
                    store.transactions[row['api_id']] = Transaction.model_validate(row['data']); store.origins[row['api_id']] = row['origin']
                for row in conn.execute(select(m.evidence).where(m.evidence.c.merchant_id == merchant)).mappings():
                    store.documents[row['api_id']] = EvidenceMetadata.model_validate(row['data'])
                for row in conn.execute(select(m.analyses).where(m.analyses.c.merchant_id == merchant)).mappings():
                    store.analyses[row['api_id']] = Analysis.model_validate(row['data'])
                    store.details[row['api_id']] = AnalysisDetails.model_validate(row['details'])
                for row in conn.execute(select(m.drafts).where(m.drafts.c.merchant_id == merchant)).mappings(): store.drafts[row['data']['analysis_id']] = row['data']
                for row in conn.execute(select(m.revisions).where(m.revisions.c.merchant_id == merchant)).mappings(): store.revisions.append(row['data'])
                for row in conn.execute(select(m.audit).where(m.audit.c.merchant_id == merchant).order_by(m.audit.c.created_at)).mappings(): store.events.append(row['data'])
                for row in conn.execute(select(m.idempotency).where(m.idempotency.c.merchant_id == merchant)).mappings(): store.idempotency[row['key']] = row['api_id']
            order = {e['resource_id']: index for index,e in enumerate(store.events) if e['action']=='analysis_queued'}
            store.analyses = dict(sorted(store.analyses.items(), key=lambda item:order.get(item[0],-1)))
            for aid, analysis in list(store.analyses.items()):
                if analysis.status in ('queued', 'processing'):
                    store.analyses[aid] = analysis.model_copy(update={'status': 'failed'})
                    store.details[aid] = AnalysisDetails(analysis_id=aid, failure_code='PIPELINE_ERROR')
                    event(store, 'analysis_interrupted_by_restart', aid)
                    for doc in store.documents.values():
                        if doc.analysis_id == aid and doc.processing_status == 'processing':
                            doc.processing_status = 'failed'; doc.issue_codes = ['PIPELINE_ERROR']
            self.stores[merchant] = store
            self.save(store)
            return store

    def seed(self, merchant):
        store = self.store(merchant)
        with store.lock:
            if not store.transactions:
                tid = 'txn_' + str(uuid4())
                store.transactions[tid] = TRANSACTION.model_copy(update={'id': tid, 'evidence_count': 0}, deep=True)
                store.origins[tid] = 'synthetic'
                event(store, 'synthetic_transaction_created', tid)
                self.save(store)
        return store

    def save(self, store):
        merchant = store.merchant_id
        def upsert(conn, table, values):
            stmt = insert(table).values(**values)
            conn.execute(stmt.on_conflict_do_update(index_elements=[table.c.id], set_={key: stmt.excluded[key] for key in values if key != 'id'}))
        with store.lock, self.engine.begin() as conn:
            for tid, transaction in store.transactions.items():
                upsert(conn, m.transactions, dict(id=internal(merchant, tid), merchant_id=merchant, api_id=tid, paypal_transaction_id=transaction.paypal_transaction_id, amount=Decimal(transaction.amount), currency=transaction.currency, transaction_date=transaction.transaction_date, data=transaction.model_dump(mode='json'), origin=store.origins.get(tid, 'synthetic')))
            for did, doc in store.documents.items():
                upsert(conn, m.evidence, dict(id=internal(merchant,did), merchant_id=merchant, transaction_id=internal(merchant,doc.transaction_id), api_id=did, storage_key=did, data=doc.model_dump(mode='json')))
            for aid, analysis in store.analyses.items():
                detail = store.details[aid]
                upsert(conn, m.analyses, dict(id=internal(merchant,aid), merchant_id=merchant, transaction_id=internal(merchant,analysis.transaction_id), api_id=aid, status=analysis.status, data=analysis.model_dump(mode='json'), details=detail.model_dump(mode='json')))
                for finding in analysis.findings:
                    fid = internal(merchant,aid + ':' + finding.id)
                    upsert(conn, m.findings, dict(id=fid, merchant_id=merchant, analysis_id=internal(merchant,aid), data=finding.model_dump(mode='json')))
                    for did in finding.source_ids:
                        spans = [s.model_dump(mode='json') for s in detail.result.finding_sources.get(finding.id, []) if s.document_id == did] if detail.result else []
                        upsert(conn, m.sources, dict(id=internal(merchant,aid+':'+finding.id+':'+did), merchant_id=merchant, finding_id=fid, document_id=internal(merchant,did), spans=spans))
            for aid, data in store.drafts.items(): upsert(conn, m.drafts, dict(id=internal(merchant,'draft:'+aid), merchant_id=merchant, analysis_id=internal(merchant,aid), data=data))
            for data in store.revisions: upsert(conn, m.revisions, dict(id=internal(merchant,'revision:'+data['analysis_id']+':'+str(data['version'])), merchant_id=merchant, analysis_id=internal(merchant,data['analysis_id']), version=data['version'], data=data))
            for data in store.events: conn.execute(insert(m.audit).values(id=data['id'], merchant_id=merchant, created_at=datetime.fromisoformat(data['created_at']), data=data).on_conflict_do_nothing(index_elements=[m.audit.c.id]))
            for key, aid in store.idempotency.items(): upsert(conn, m.idempotency, dict(id=internal(merchant,'key:'+key), merchant_id=merchant, key=key, analysis_id=internal(merchant,aid), api_id=aid))
