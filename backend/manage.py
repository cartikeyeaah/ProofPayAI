"""Local admin commands. Password input is hidden; never passed as CLI arguments."""
import argparse
import getpass
import os
from uuid import uuid4
from sqlalchemy import create_engine, select, update, delete
from backend.db import models as m
from backend.db.repository import now, internal
from backend.app.mock_data import TRANSACTION
from decimal import Decimal
from backend.app.auth import hash_password

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['create-user', 'reset-password'])
    parser.add_argument('--email', required=True)
    parser.add_argument('--merchant')
    args = parser.parse_args()
    if '@' not in args.email or len(args.email) > 254 or (args.command == 'create-user' and not (args.merchant or '').strip()):
        raise SystemExit('A valid email and merchant name are required.')
    password = getpass.getpass('Password (at least 12 characters): ')
    if len(password) < 12 or len(password) > 256: raise SystemExit('Password must contain 12–256 characters.')
    if password != getpass.getpass('Confirm password: '): raise SystemExit('Passwords do not match.')
    engine = create_engine(os.environ['DATABASE_URL'])
    if args.command == 'reset-password':
        with engine.begin() as conn:
            user = conn.execute(select(m.users).where(m.users.c.email == args.email.strip().lower()).with_for_update()).mappings().first()
            if not user: raise SystemExit('Account not found.')
            conn.execute(update(m.users).where(m.users.c.id == user['id']).values(password_hash=hash_password(password)))
            conn.execute(delete(m.sessions).where(m.sessions.c.user_id == user['id']))
        engine.dispose()
        print('Password reset. All account sessions were revoked.')
        return
    merchant = str(uuid4())
    with engine.begin() as conn:
        conn.execute(m.merchants.insert().values(id=merchant, name=args.merchant))
        conn.execute(m.users.insert().values(id=str(uuid4()), merchant_id=merchant, email=args.email.strip().lower(), password_hash=hash_password(password), created_at=now()))
        tid = 'txn_' + str(uuid4())
        transaction = TRANSACTION.model_copy(update={'id': tid, 'evidence_count': 0}, deep=True)
        conn.execute(m.transactions.insert().values(id=internal(merchant,tid), merchant_id=merchant, api_id=tid, paypal_transaction_id=transaction.paypal_transaction_id, amount=Decimal(transaction.amount), currency=transaction.currency, transaction_date=transaction.transaction_date, data=transaction.model_dump(mode='json'), origin='synthetic'))
    engine.dispose()
    print('Merchant account created with an explicitly synthetic sample transaction.')

if __name__ == '__main__': main()
