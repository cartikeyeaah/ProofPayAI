from pathlib import Path
from .schemas import Analysis, Transaction

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
TRANSACTION = Transaction.model_validate_json((CONTRACTS / "sample-transaction.json").read_text())
DEMO_ANALYSIS = Analysis.model_validate_json((CONTRACTS / "sample-analysis.json").read_text())

class MockStore:
    def __init__(self):
        self.transactions = {TRANSACTION.id: TRANSACTION.model_copy(deep=True)}
        self.analyses: dict[str, Analysis] = {}
