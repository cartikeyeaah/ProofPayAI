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
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()

def click(app, label):
    next(b for b in app.button if b.label == label).click().run()
    assert not app.exception

def test_dashboard_http_flow(live_backend):
    app = AppTest.from_file(str(Path(__file__).with_name('app.py'))).run()
    assert not app.exception and not app.error
    assert app.selectbox[0].value == 'txn_demo_001'
    assert 'ok' in app.success[0].value
    click(app, 'Create mock analysis job')
    assert app.session_state.job['status'] == 'queued'
    click(app, 'Refresh job status')
    assert app.session_state.job['status'] == 'queued'
    click(app, 'Retrieve static demo analysis')
    assert app.session_state.demo['findings'][0]['severity'] == 'high'
    assert any('missing_delivery_proof' in m.value for m in app.markdown)
    app.text_input[0].set_value('http://127.0.0.1:1').run()
    assert app.error and not app.exception
