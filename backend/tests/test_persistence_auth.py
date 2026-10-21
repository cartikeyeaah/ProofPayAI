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
