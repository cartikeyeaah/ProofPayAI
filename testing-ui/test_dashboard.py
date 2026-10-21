"""Exercise the actual Streamlit script against a live local HTTP backend."""
from pathlib import Path
import socket
import threading
import time
import pytest
import uvicorn
from streamlit.testing.v1 import AppTest
from backend.app.main import create_app

@pytest.fixture
def live_backend(monkeypatch):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(), log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        assert server.started
        monkeypatch.setenv('BACKEND_URL', f'http://127.0.0.1:{port}')
        yield server.config.app
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()

def click(app, label):
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception

def test_dashboard_http_flow(live_backend):
    app = AppTest.from_file(str(Path(__file__).with_name('app.py')), default_timeout=15).run()
    assert not app.exception and not app.error
    assert app.selectbox[0].value == 'txn_demo_001'
    assert 'healthy' in app.success[0].value
    click(app, 'Create analysis job')
    assert app.session_state.job['status'] == 'queued'
    wait_worker(live_backend)
    click(app, 'Refresh job status')
    assert app.session_state.job['status'] == 'completed'
    click(app, 'Retrieve static demo analysis')
    assert app.session_state.demo['findings'][0]['severity'] == 'high'
    assert any('missing_delivery_proof' in m.value for m in app.text)
    app.text_input[0].set_value('http://127.0.0.1:1').run()
    assert app.error and not app.exception
    assert 'job' not in app.session_state
    assert 'demo' not in app.session_state
    assert not app.get('file_uploader')

@pytest.mark.parametrize('state', ['processing', 'completed', 'failed'])
def test_supported_analysis_rendering(live_backend, state):
    """Inject contract-compatible server results; this is not a real worker test."""
    from backend.app.mock_data import DEMO_ANALYSIS
    app = AppTest.from_file(str(Path(__file__).with_name('app.py')), default_timeout=15).run()
    click(app, 'Check backend health')
    click(app, 'Create analysis job')
    wait_worker(live_backend)
    job_id = app.session_state.job['analysis_id']
    live_backend.state.store.analyses[job_id] = DEMO_ANALYSIS.model_copy(update={
        'analysis_id': job_id, 'status': state, 'draft_response': 'Synthetic draft for merchant review.'})
    click(app, 'Refresh job status')
    assert app.session_state.job['status'] == state
    texts = [item.value for item in app.text]
    assert 'Synthetic draft for merchant review.' in texts
    assert 'Merchant approval required: Yes' in texts
    assert 'Source document IDs: doc_demo_001' in texts
    assert 'Recommendation: Upload a verifiable delivery record if available.' in texts
    assert any('Analysis status: ' + state == e.value for e in list(app.info) + list(app.success) + list(app.error))

def test_refresh_failure_retains_job_and_retry(live_backend):
    app = AppTest.from_file(str(Path(__file__).with_name('app.py')), default_timeout=15).run()
    click(app, 'Create analysis job')
    wait_worker(live_backend)
    job_id = app.session_state.job['analysis_id']
    saved = live_backend.state.store.analyses.pop(job_id)
    click(app, 'Refresh job status')
    assert app.error
    assert app.session_state.job['analysis_id'] == job_id
    assert any('stale' in item.value for item in app.warning)
    live_backend.state.store.analyses[job_id] = saved
    click(app, 'Refresh job status')
    assert not app.error
    click(app, 'Refresh transactions / retry')
    assert app.session_state.details['id'] == 'txn_demo_001'


def wait_worker(backend):
    deadline = time.monotonic() + 10
    while backend.state.store.active_transactions and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not backend.state.store.active_transactions


def test_real_upload_analysis_ui(live_backend):
    import os
    from api_client import APIClient
    api = APIClient(os.environ['BACKEND_URL'])
    result = api.call('POST', '/api/v1/transactions/txn_demo_001/documents', 'EvidenceMetadata',
        files={'file': ('synthetic.txt', b'Transaction ID: DEMO-1001\nTotal: USD 151.00\n', 'text/plain')},
        form={'document_type': 'invoice'})
    assert result.status == 201 and not result.error
    doc_id = result.data['id']
    app = AppTest.from_file(str(Path(__file__).with_name('app.py')), default_timeout=15).run()
    assert app.get('file_uploader')
    assert any('not_processed' in item.value for item in app.text)
    click(app, 'Create analysis job')
    wait_worker(live_backend)
    click(app, 'Refresh job status')
    click(app, 'Refresh evidence status')
    assert app.session_state.job['status'] == 'completed'
    assert any('amount_mismatch' in item.value for item in app.text)
    assert any('Source document IDs: ' + doc_id == item.value for item in app.text)
    assert any('Parsing: parsed' in item.value for item in app.text)
    assert app.session_state.job['draft_response']
    assert not app.exception and not app.error
