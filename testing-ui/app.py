import os
import streamlit as st
from api_client import APIClient, valid_url

st.set_page_config(page_title='ProofPay AI · Internal testing', layout='wide')
st.title('ProofPay AI — Internal testing')
st.caption('Synthetic test data only. Pipeline execution is separate from the static demo fixture.')
initial_url = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')
# Never prefill credentials or query tokens from the environment into the visible widget.
if not valid_url(initial_url):
    initial_url = 'http://127.0.0.1:8000'
base_url = st.text_input('Backend connection URL', value=initial_url).rstrip('/')
if st.session_state.get('backend_context') != base_url:
    for key in ('health', 'transactions', 'details', 'job', 'demo', 'transaction_context', 'diagnostics', 'capabilities', 'job_details'):
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith('evidence_'):
            st.session_state.pop(key, None)
    st.session_state.backend_context = base_url
client = APIClient(base_url)

def call_api(method, path, schema, array=False, **kwargs):
    result = client.call(method, path, schema, array=array, **kwargs)
    entries = st.session_state.get('diagnostics', [])
    # Only fixed route labels, never URLs, raw bodies, headers, or exception strings.
    entries.append({'method': method, 'response': schema, 'HTTP': result.status,
                    'elapsed_ms': result.elapsed_ms, 'outcome': result.error or 'Success',
                    'code': result.code, 'request_id': result.request_id})
    st.session_state.diagnostics = entries[-20:]
    if result.error:
        st.error(result.error)
    return result.data

def render_analysis(analysis, demo=False):
    st.subheader('Static demo analysis — fixture only' if demo else 'Backend analysis job — deterministic AI engine' if st.session_state.get('capabilities') else 'Backend analysis — engine unverified')
    st.text('Analysis ID: ' + analysis['analysis_id'])
    state = analysis['status']
    {'queued': st.info, 'processing': st.info, 'completed': st.success, 'failed': st.error}[state]('Analysis status: ' + state)
    if not demo and state == 'queued':
        st.caption('Job accepted. Refresh status to retrieve the worker result.')
    st.text('Merchant approval required: ' + ('Yes' if analysis['merchant_approval_required'] else 'No'))
    st.caption('Approval requirement is not approval granted. Use the Next.js workspace to edit and approve saved drafts. Submission is unavailable.')
    if not analysis['findings']:
        st.info('No findings returned for this job yet.' if state in ('queued', 'processing') else 'No findings returned.')
    for finding in analysis['findings']:
        with st.container(border=True):
            st.text('Issue: ' + finding['issue_type'])
            st.text('Severity: ' + finding['severity'])
            st.text('Explanation: ' + finding['explanation'])
            st.text('Recommendation: ' + finding['recommendation'])
            st.text('Source document IDs: ' + (', '.join(finding['source_ids']) or 'None supplied'))
    st.write('Draft response')
    if analysis['draft_response'] is None:
        st.info('No draft response returned.')
    else:
        st.text(analysis['draft_response'])
        st.caption('Review required. This dashboard cannot submit responses.')

check = st.button('Check backend health')
if check or 'health' not in st.session_state:
    st.session_state.health = call_api('GET', '/api/v1/health', 'Health')
    st.session_state.capabilities = call_api('GET', '/api/v1/capabilities', 'Capabilities')
if st.session_state.health:
    st.success('Connection: healthy · backend mode: ' + st.session_state.health['mode'])
else:
    st.warning('Connection: unavailable or health check failed')

if (st.session_state.get('capabilities') or {}).get('persistence') == 'postgresql':
    st.info('This internal dashboard supports local demo mode only. Use the Next.js merchant workspace to sign in to a persistent backend.')

refresh = st.button('Refresh transactions / retry')
if refresh or 'transactions' not in st.session_state:
    st.session_state.transactions = call_api('GET', '/api/v1/transactions', 'Transaction', array=True)
    st.session_state.pop('details', None)

st.caption('Health mode mock describes synthetic transaction storage. Capabilities identify the analysis engine. No hosted LLM is configured. OCR availability is reported by capabilities.')
transactions = st.session_state.transactions
if transactions:
    transaction_id = st.selectbox('Synthetic transaction', [t['id'] for t in transactions])
    if st.session_state.get('transaction_context') != transaction_id:
        for key in ('details', 'job', 'demo', 'job_details'):
            st.session_state.pop(key, None)
        st.session_state.transaction_context = transaction_id
    refresh_details = st.button('Refresh transaction details')
    if refresh_details or 'details' not in st.session_state:
        st.session_state.details = call_api('GET', f'/api/v1/transactions/{transaction_id}', 'Transaction')
    if st.session_state.details:
        st.subheader('Transaction details')
        st.json(st.session_state.details)
    st.subheader('Evidence testing')
    if st.session_state.get('capabilities'):
        st.caption('PDF, PNG, JPEG and UTF-8 text · max 10 MiB/file, 25 documents. Images/scans require the optional local OCR adapter. Upload stores bytes; analysis performs parsing.')
        uploaded = st.file_uploader('Synthetic evidence only', type=['pdf', 'png', 'jpg', 'jpeg', 'txt'], key='evidence_' + transaction_id)
        kind = st.selectbox('Document type', ['invoice', 'order_confirmation', 'delivery_record', 'other'])
        if st.button('Upload synthetic evidence', disabled=uploaded is None):
            if uploaded.size > 10 * 1024 * 1024:
                st.error('File exceeds 10 MiB.')
            else:
                result = call_api('POST', f'/api/v1/transactions/{transaction_id}/documents', 'EvidenceMetadata',
                                  files={'file': (uploaded.name, uploaded.getvalue(), uploaded.type)}, form={'document_type': kind})
                if result:
                    st.success('Upload stored. Parsing has not run yet. Create an analysis to process this evidence.')
                    st.session_state.pop('details', None)
        st.button('Refresh evidence status')
        documents = call_api('GET', f'/api/v1/transactions/{transaction_id}/documents', 'EvidenceMetadata', array=True)
        for doc in documents or []:
            with st.expander(doc['filename'] + ' — ' + doc['processing_status'], expanded=True):
                st.text('Document ID: ' + doc['id'])
                st.text('Upload: ' + doc['upload_status'] + ' | Parsing: ' + doc['processing_status'])
                st.text('Media type: ' + doc['media_type'] + ' | Bytes: ' + str(doc['size_bytes']))
                st.text('Last analysis: ' + (doc['analysis_id'] or 'None'))
                if doc['issue_codes']:
                    st.text('Processing issues: ' + ', '.join(doc['issue_codes']))
                if doc['facts']:
                    st.json(doc['facts'])
        if documents == []:
            st.info('No evidence uploaded for this transaction.')
    else:
        st.info('Evidence upload unavailable: backend capabilities could not be verified.')
    if st.button('Create analysis job'):
        result = call_api('POST', f'/api/v1/transactions/{transaction_id}/analyze', 'Analysis')
        if result:
            st.session_state.job = result
    if st.session_state.get('job'):
        if st.button('Refresh job status'):
            result = call_api('GET', f"/api/v1/analysis/{st.session_state.job['analysis_id']}", 'Analysis')
            if result:
                st.session_state.job = result
            else:
                st.warning('Refresh failed. Showing the last successful result below; it may be stale.')
        render_analysis(st.session_state.job)
        if st.session_state.get('capabilities'):
            job_details = call_api('GET', f"/api/v1/analysis/{st.session_state.job['analysis_id']}/details", 'AnalysisDetails')
            if job_details:
                st.text('Engine: ' + job_details['engine'])
                if job_details['failure_code']:
                    st.error('Worker failure: ' + job_details['failure_code'])
                if job_details['result']:
                    with st.expander('Validated source references and processing issues'):
                        st.json(job_details['result']['finding_sources'])
                        st.json(job_details['result']['issues'])
    if st.button('Retrieve static demo analysis'):
        st.session_state.demo = call_api('GET', f'/api/v1/transactions/{transaction_id}/demo-analysis', 'Analysis')
    if st.session_state.get('demo'):
        render_analysis(st.session_state.demo, demo=True)
else:
    st.info('No transactions available. Use Refresh transactions / retry after checking the backend.')

with st.expander('Request diagnostics — last 20 requests', expanded=True):
    st.caption('Status and elapsed time only, with safe error descriptions. Raw error bodies, credentials, and environment values are omitted.')
    st.dataframe(st.session_state.get('diagnostics', []), hide_index=True)
