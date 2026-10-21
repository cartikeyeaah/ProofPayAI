from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from .schemas import Analysis, Transaction

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
TRANSACTION = Transaction.model_validate_json((CONTRACTS / "sample-transaction.json").read_text())
DEMO_ANALYSIS = Analysis.model_validate_json((CONTRACTS / "sample-analysis.json").read_text())

class MockStore:
    def __init__(self):
        self.transactions = {TRANSACTION.id: TRANSACTION.model_copy(update={'evidence_count': 0}, deep=True)}
        self.lock = RLock()
        self.storage = TemporaryDirectory(prefix='proofpay-evidence-')
        self.documents = {}
        self.details = {}
        self.active_transactions = set()
        self.repository = None
        self.merchant_id = 'demo'
        self.origins = {TRANSACTION.id: 'synthetic'}
        self.drafts = {}
        self.revisions = []
        self.events = []
        self.idempotency = {}
        self.analyses: dict[str, Analysis] = {}
