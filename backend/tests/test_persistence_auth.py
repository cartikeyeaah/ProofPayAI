"""Set PROOFPAY_TEST_DATABASE_URL to a migrated, disposable PostgreSQL database."""
import os
from uuid import uuid4
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.auth import hash_password
from backend.db import models as m
from backend.db.repository import now
from sqlalchemy import select

URL = os.getenv('PROOFPAY_TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='PostgreSQL integration needs PROOFPAY_TEST_DATABASE_URL')
PASSWORD = 'Synthetic-test-password-42'

def account(app):
    merchant, user = str(uuid4()), str(uuid4())
    email = user + '@example.test'
    repo = app.state.repository
    with repo.engine.begin() as conn:
        conn.execute(m.merchants.insert().values(id=merchant,name='Synthetic Merchant'))
        conn.execute(m.users.insert().values(id=user,merchant_id=merchant,email=email,password_hash=hash_password(PASSWORD),created_at=now()))
    store = repo.seed(merchant)
    return merchant,email,next(iter(store.transactions))

def login(client,email):
    response=client.post('/api/v1/auth/login',json={'email':email,'password':PASSWORD})
    assert response.status_code==200,response.text
    client.headers['X-CSRF-Token']=response.json()['csrf_token']
    return response

def test_persistence_draft_approval_and_restart(tmp_path):
    app=create_app(URL,str(tmp_path))
    with TestClient(app) as client:
        merchant,email,tid=account(app)
        assert client.get('/api/v1/transactions').status_code==401
        response=login(client,email)
        assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
        assert client.get('/api/v1/auth/me').json()['mode']=='persistent'
        base='/api/v1/transactions/'+tid
        upload=client.post(base+'/documents',files={'file':('invoice.txt',b'Transaction ID: DEMO-1001\nTotal: USD 150.00\n','text/plain')},data={'document_type':'invoice'})
        assert upload.status_code==201,upload.text
        did=upload.json()['id']
        job=client.post(base+'/analyze',json={},headers={'Idempotency-Key':'test-one'})
        assert job.status_code==202,job.text
        aid=job.json()['analysis_id']
        again=client.post(base+'/analyze',json={},headers={'Idempotency-Key':'test-one'})
        assert again.json()['analysis_id']==aid
        assert client.get('/api/v1/analysis/'+aid).json()['status']=='completed'
        draft=client.get('/api/v1/analysis/'+aid+'/draft').json()
        assert draft['version']==1
        edited=client.put('/api/v1/analysis/'+aid+'/draft',json={'text':draft['text']+' Merchant note.', 'version':1})
        assert edited.status_code==200,edited.text
        assert 'manual_edits_not_source_validated' in edited.json()['warnings']
        assert client.put('/api/v1/analysis/'+aid+'/draft',json={'text':'stale','version':1}).status_code==409
        assert client.post('/api/v1/analysis/'+aid+'/draft/approve',json={'version':2}).status_code==422
        approved=client.post('/api/v1/analysis/'+aid+'/draft/approve',json={'version':2,'acknowledge_warnings':True})
        assert approved.status_code==200 and approved.json()['status']=='approved'
        assert client.get('/api/v1/analysis/'+aid+'/audit').json()['revisions'][-1]['status']=='approved'
        with app.state.repository.engine.connect() as conn:
            assert conn.execute(select(m.transactions.c.amount).where(m.transactions.c.api_id==tid)).scalar().__class__.__name__=='Decimal'
        cookies=dict(client.cookies)
    assert (tmp_path/merchant/did).exists()
    with TestClient(create_app(URL,str(tmp_path))) as client:
        client.cookies.update(cookies)
        assert client.get('/api/v1/transactions/'+tid).status_code==200
        assert client.get('/api/v1/analysis/'+aid+'/draft').json()['status']=='approved'
        assert client.get(base+'/documents/'+did+'/content').status_code==200
        assert client.get('/api/v1/analysis/'+aid+'/details').json()['result']['facts']
        login(client,email)
        assert client.post('/api/v1/auth/logout').status_code==200
        assert client.get('/api/v1/transactions').status_code==401

def test_cross_merchant_access_and_csrf(tmp_path):
    app=create_app(URL,str(tmp_path))
    with TestClient(app) as client:
        _,a,tid=account(app); _,b,other=account(app)
        login(client,a)
        base='/api/v1/transactions/'+tid
        did=client.post(base+'/documents',files={'file':('a.txt',b'Transaction ID: DEMO-1001\nTotal: USD 150.00','text/plain')},data={'document_type':'invoice'}).json()['id']
        aid=client.post(base+'/analyze',json={}).json()['analysis_id']
        login(client,b)
        for path in [base,base+'/documents',base+'/documents/'+did,base+'/documents/'+did+'/content','/api/v1/analysis/'+aid,'/api/v1/analysis/'+aid+'/details','/api/v1/analysis/'+aid+'/draft','/api/v1/analysis/'+aid+'/audit']:
            assert client.get(path).status_code==404,path
        assert client.post(base+'/analyze',json={}).status_code==404
        assert client.put('/api/v1/analysis/'+aid+'/draft',json={'text':'bad','version':1}).status_code==404
        assert client.post('/api/v1/analysis/'+aid+'/draft/approve',json={'version':1}).status_code==404
        assert client.get('/api/v1/transaction-page').json()['total']==1
        client.headers.pop('X-CSRF-Token')
        assert client.post('/api/v1/transactions/'+other+'/analyze',json={}).status_code==403
        assert client.post('/api/v1/auth/login',json={'email':b,'password':PASSWORD},headers={'Origin':'https://evil.example'}).status_code==403

def test_login_rate_limit_and_bad_password(tmp_path):
    with TestClient(create_app(URL,str(tmp_path))) as client:
        for _ in range(5):
            assert client.post('/api/v1/auth/login',json={'email':'unknown@example.test','password':'wrong'}).status_code==401
        assert client.post('/api/v1/auth/login',json={'email':'unknown@example.test','password':'wrong'}).status_code==429

def test_restart_marks_interrupted_job_failed(tmp_path):
    from backend.app.schemas import Analysis
    from backend.app.integration_schemas import AnalysisDetails
    from backend.db.repository import save
    app=create_app(URL,str(tmp_path))
    with TestClient(app) as client:
        merchant,email,tid=account(app)
        store=app.state.repository.store(merchant)
        aid='analysis_'+str(uuid4())
        store.analyses[aid]=Analysis(analysis_id=aid,transaction_id=tid,status='processing',findings=[],draft_response=None,merchant_approval_required=True)
        store.details[aid]=AnalysisDetails(analysis_id=aid)
        save(store)
    with TestClient(create_app(URL,str(tmp_path))) as client:
        login(client,email)
        assert client.get('/api/v1/analysis/'+aid).json()['status']=='failed'
        assert client.get('/api/v1/analysis/'+aid+'/details').json()['failure_code']=='PIPELINE_ERROR'


def test_secure_cookie_and_admin_provisioning_while_running(tmp_path, monkeypatch):
    from unittest.mock import patch
    from backend.manage import main
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('FRONTEND_ORIGINS', 'https://testserver')
    monkeypatch.setenv('DATABASE_URL', URL)
    email = str(uuid4())+'@example.test'
    with TestClient(create_app(URL,str(tmp_path)),base_url='https://testserver') as client:
        with patch('sys.argv',['manage','create-user','--email',email,'--merchant','Synthetic CLI Store']), patch('getpass.getpass',return_value=PASSWORD):
            main()
        response=login(client,email)
        assert 'Secure' in response.headers['set-cookie']
        assert client.get('/api/v1/transactions').status_code==200
        assert len(client.get('/api/v1/transactions').json())==1


def test_transaction_search_pagination_and_sort(tmp_path):
    from backend.db.repository import save
    app=create_app(URL,str(tmp_path))
    with TestClient(app) as client:
        merchant,email,tid=account(app)
        store=app.state.repository.store(merchant)
        extra=store.transactions[tid].model_copy(update={'id':'txn_extra','paypal_transaction_id':'SYNTHETIC-EXTRA','amount':'20.00'})
        store.transactions[extra.id]=extra; store.origins[extra.id]='synthetic'; save(store)
        login(client,email)
        page=client.get('/api/v1/transaction-page',params={'sort':'amount','direction':'asc','page_size':1}).json()
        assert page['total']==2 and page['items'][0]['id']=='txn_extra'
        assert client.get('/api/v1/transaction-page',params={'q':'synthetic-extra'}).json()['total']==1
        assert client.get('/api/v1/transaction-page',params={'page':2,'page_size':1,'sort':'amount','direction':'asc'}).json()['items'][0]['id']==tid
        assert client.get('/api/v1/transaction-page',params={'analyzed':'yes'}).json()['total']==0
        assert client.get('/api/v1/transaction-page',params={'page_size':101}).status_code==422


def test_password_change_revokes_sessions_and_expired_session_denied(tmp_path):
    from datetime import timedelta
    from sqlalchemy import update
    app=create_app(URL,str(tmp_path))
    with TestClient(app) as client:
        _,email,_=account(app)
        login(client,email)
        old_cookies=dict(client.cookies)
        response=client.post('/api/v1/auth/password',json={'current_password':'wrong','new_password':'New-synthetic-password-43'})
        assert response.status_code==401 and response.json()['error']['code']=='INVALID_PASSWORD'
        assert client.get('/api/v1/auth/me').status_code==200
        assert client.post('/api/v1/auth/password',json={'current_password':PASSWORD,'new_password':'short'}).status_code==422
        assert client.post('/api/v1/auth/password',json={'current_password':PASSWORD,'new_password':'New-synthetic-password-43'}).status_code==200
        client.cookies.update(old_cookies)
        assert client.get('/api/v1/auth/me').status_code==401
        assert client.post('/api/v1/auth/login',json={'email':email,'password':PASSWORD}).status_code==401
        assert client.post('/api/v1/auth/login',json={'email':email,'password':'New-synthetic-password-43'}).status_code==200
        with app.state.repository.engine.begin() as conn:
            user_id=conn.execute(select(m.users.c.id).where(m.users.c.email==email)).scalar_one()
            conn.execute(update(m.sessions).where(m.sessions.c.user_id==user_id).values(expires_at=now()-timedelta(seconds=1)))
        response=client.get('/api/v1/auth/me')
        assert response.status_code==401 and response.headers['cache-control']=='no-store'


def test_admin_password_reset_revokes_existing_sessions(tmp_path,monkeypatch):
    from unittest.mock import patch
    from backend.manage import main
    monkeypatch.setenv('DATABASE_URL',URL)
    app=create_app(URL,str(tmp_path))
    with TestClient(app) as client:
        _,email,_=account(app);login(client,email)
        with patch('sys.argv',['manage','reset-password','--email',email]),patch('getpass.getpass',return_value='Reset-synthetic-password-44'):
            main()
        assert client.get('/api/v1/auth/me').status_code==401
        assert client.post('/api/v1/auth/login',json={'email':email,'password':'Reset-synthetic-password-44'}).status_code==200


def test_sandbox_check_sync_persistence_and_merchant_binding(tmp_path,monkeypatch):
    import httpx
    from backend.integrations.paypal import SandboxClient,SCOPE
    from backend.app import integrations
    app=create_app(URL,str(tmp_path))
    with TestClient(app) as client:
        merchant,email,_=account(app);_,other,_=account(app);login(client,email)
        monkeypatch.setenv('PAYPAL_CLIENT_ID','synthetic-client')
        monkeypatch.setenv('PAYPAL_CLIENT_SECRET','synthetic-secret')
        monkeypatch.setenv('PAYPAL_MERCHANT_ID',merchant)
        def transport(request):
            if request.url.path.endswith('/token'): return httpx.Response(200,json={'access_token':'synthetic','scope':SCOPE,'expires_in':3600})
            return httpx.Response(200,json={'total_pages':1,'transaction_details':[{'transaction_info':{'transaction_id':'SANDBOX-INTEGRATION-1','transaction_status':'S','transaction_amount':{'value':'1.00','currency_code':'USD'},'transaction_initiation_date':'2026-11-12T10:00:00Z'}}]})
        monkeypatch.setattr(integrations,'SandboxClient',lambda *a:SandboxClient(*a,transport=httpx.MockTransport(transport)))
        assert client.post('/api/v1/integrations/paypal/check').json()['reporting_access'] is True
        assert client.get('/api/v1/transactions').json().__len__()==1
        assert client.post('/api/v1/integrations/paypal/sync').json()['imported']==1
        assert client.post('/api/v1/integrations/paypal/sync').json()['imported']==0
        assert client.get('/api/v1/integrations').json()['paypal_verified'] is True
        login(client,other)
        assert client.post('/api/v1/integrations/paypal/check').status_code==503
        assert client.post('/api/v1/integrations/paypal/sync').status_code==503
    with TestClient(create_app(URL,str(tmp_path))) as client:
        login(client,email)
        page=client.get('/api/v1/transaction-page').json()
        assert page['total']==2 and 'sandbox' in page['origins'].values()
        monkeypatch.delenv('PAYPAL_CLIENT_SECRET')
        assert client.get('/api/v1/integrations').json()['paypal']=='not-configured'


def test_registration_login_duplicate_validation_and_isolation(tmp_path):
    from sqlalchemy import func
    app=create_app(URL,str(tmp_path))
    with TestClient(app) as client:
        email=str(uuid4())+'@example.test'
        payload={'merchant_name':'New Merchant','email':email.upper(),'password':PASSWORD}
        assert client.post('/api/v1/auth/register',json={**payload,'password':'short'}).status_code==422
        assert client.post('/api/v1/auth/register',json={**payload,'email':'invalid'}).status_code==422
        assert client.post('/api/v1/auth/register',json=payload,headers={'Origin':'https://evil.example'}).status_code==403
        assert client.post('/api/v1/auth/register',json=payload).status_code==201
        with app.state.repository.engine.connect() as conn:
            count=conn.execute(select(func.count()).select_from(m.merchants)).scalar()
            stored=conn.execute(select(m.users.c.password_hash).where(m.users.c.email==email)).scalar_one()
            assert stored != PASSWORD and stored.startswith('scrypt$')
        assert client.post('/api/v1/auth/register',json=payload).status_code==409
        with app.state.repository.engine.connect() as conn:
            assert conn.execute(select(func.count()).select_from(m.merchants)).scalar()==count
        login(client,email)
        assert client.get('/api/v1/auth/me').json()['merchant_name']=='New Merchant'
        assert client.get('/api/v1/transactions').json()==[]
        for _ in range(3):client.post('/api/v1/auth/register',json=payload)
        assert client.post('/api/v1/auth/register',json=payload).status_code==429


def test_new_account_can_start_upload_without_paypal(tmp_path):
    app=create_app(URL,str(tmp_path))
    with TestClient(app) as client:
        email=str(uuid4())+'@example.test'
        assert client.post('/api/v1/auth/register',json={'merchant_name':'Upload test','email':email,'password':PASSWORD}).status_code==201
        login(client,email)
        r=client.post('/api/v1/transactions/synthetic');assert r.status_code==200
        tid=r.json()['id']
        assert client.post('/api/v1/transactions/synthetic').json()['id']==tid
        assert client.get('/api/v1/transaction-page').json()['origins'][tid]=='synthetic'
        r=client.post('/api/v1/transactions/'+tid+'/documents',files={'file':('test.txt',b'Synthetic test evidence','text/plain')},data={'document_type':'other'})
        assert r.status_code==201
        cookies=dict(client.cookies)
    with TestClient(create_app(URL,str(tmp_path))) as client:
        client.cookies.update(cookies)
        assert client.get('/api/v1/transactions/'+tid).json()['evidence_count']==1
