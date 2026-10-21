import hashlib
import hmac
import secrets
import time
from datetime import timedelta
from uuid import uuid4
from fastapi import APIRouter, Request, Response
from pydantic import Field
from sqlalchemy import select, delete
from backend.db import models as m
from backend.db.repository import now, event, save
from .schemas import ContractModel
from .errors import APIError

router = APIRouter(prefix='/api/v1/auth')
COOKIE = 'proofpay_session'

class Login(ContractModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

class Account(ContractModel):
    email: str
    merchant_name: str
    mode: str
    csrf_token: str

class Logout(ContractModel):
    status: str = 'logged_out'

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return 'scrypt$' + salt + '$' + value

def check_password(password, stored):
    try:
        _, salt, _ = stored.split('$')
        return hmac.compare_digest(hash_password(password, salt), stored)
    except (ValueError, TypeError): return False

def rate_limit(app, key, count=10, window=60):
    with app.state.rate_lock:
        current = time.monotonic()
        entries = [t for t in app.state.rate_attempts.get(key, []) if t > current-window]
        if len(entries) >= count: raise APIError(429, 'RATE_LIMITED', 'Too many requests. Wait before retrying.')
        entries.append(current)
        app.state.rate_attempts[key] = entries
        if len(app.state.rate_attempts) > 10000:
            app.state.rate_attempts = {k:v for k,v in app.state.rate_attempts.items() if v[-1] > current-window}

PUBLIC = {'/api/v1/health', '/api/v1/ready', '/api/v1/capabilities', '/api/v1/auth/login', '/docs', '/openapi.json', '/docs/oauth2-redirect'}

def authorize(request):
    app = request.app
    request.state.store = app.state.store
    request.state.actor = 'demo'
    if app.state.repository is None: return
    path = request.url.path
    mutation = request.method not in ('GET','HEAD','OPTIONS')
    if mutation and request.headers.get('origin') and request.headers['origin'] not in app.state.origins:
        raise APIError(403, 'ORIGIN_DENIED', 'The request origin is not allowed.')
    if path in PUBLIC or request.method == 'OPTIONS': return
    token = request.cookies.get(COOKIE, '')
    digest = hashlib.sha256(token.encode()).hexdigest()
    with app.state.repository.engine.connect() as conn:
        row = conn.execute(select(m.sessions.c.csrf, m.users.c.id, m.users.c.merchant_id, m.users.c.email, m.merchants.c.name).select_from(m.sessions.join(m.users).join(m.merchants)).where(m.sessions.c.token_hash == digest, m.sessions.c.expires_at > now())).mappings().first()
    if not row: raise APIError(401, 'AUTH_REQUIRED', 'Sign in to continue.')
    if mutation and not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), row['csrf']):
        raise APIError(403, 'CSRF_FAILED', 'Refresh your session before retrying.')
    request.state.actor = row['id']
    request.state.account = Account(email=row['email'], merchant_name=row['name'], mode='persistent', csrf_token=row['csrf'])
    request.state.store = app.state.repository.store(row['merchant_id'])

@router.post('/login', response_model=Account)
def login(request: Request, response: Response, payload: Login):
    repo = request.app.state.repository
    if repo is None: raise APIError(409, 'DEMO_MODE', 'Demo mode has no login. Configure PostgreSQL for accounts.')
    rate_limit(request.app, ('login', request.client.host if request.client else 'unknown'), count=5)
    with repo.engine.begin() as conn:
        user = conn.execute(select(m.users, m.merchants.c.name).join(m.merchants).where(m.users.c.email == payload.email.strip().lower())).mappings().first()
        # Perform the same password derivation for unknown accounts.
        valid = check_password(payload.password, user['password_hash'] if user else request.app.state.dummy_password_hash)
        if not user or not valid: raise APIError(401, 'INVALID_LOGIN', 'Email or password is incorrect.')
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        conn.execute(delete(m.sessions).where(m.sessions.c.expires_at <= now()))
        conn.execute(m.sessions.insert().values(id=str(uuid4()), user_id=user['id'], token_hash=hashlib.sha256(token.encode()).hexdigest(), csrf=csrf, expires_at=now()+timedelta(hours=8)))
    response.set_cookie(COOKIE, token, httponly=True, secure=request.app.state.secure_cookies, samesite='lax', max_age=8*3600, path='/')
    response.headers['Cache-Control'] = 'no-store'
    return Account(email=user['email'], merchant_name=user['name'], mode='persistent', csrf_token=csrf)

@router.get('/me', response_model=Account)
def me(request: Request):
    if request.app.state.repository is None:
        return Account(email='demo@proofpay.local', merchant_name='Demo merchant', mode='demo', csrf_token='')
    return request.state.account

@router.post('/logout', response_model=Logout)
def logout(request: Request, response: Response):
    if request.app.state.repository:
        with request.app.state.repository.engine.begin() as conn:
            conn.execute(delete(m.sessions).where(m.sessions.c.user_id == request.state.actor))
    response.delete_cookie(COOKIE, path='/')
    return Logout()
