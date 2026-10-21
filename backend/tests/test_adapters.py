from io import BytesIO
import pytest
import httpx
from backend.integrations.paypal import SandboxClient, SCOPE
from backend.app.errors import APIError

def test_sandbox_token_cache_mapping_and_scope():
    calls=[]
    def transport(request):
        calls.append(request.url.path)
        assert request.url.host=='api-m.sandbox.paypal.com'
        if request.url.path.endswith('/token'):
            return httpx.Response(200,json={'access_token':'synthetic-token','scope':SCOPE,'expires_in':3600})
        assert request.headers['Authorization']=='Bearer synthetic-token'
        return httpx.Response(200,json={'total_pages':1,'transaction_details':[{'transaction_info':{'transaction_id':'TEST-SANDBOX-1','transaction_status':'S','transaction_amount':{'value':'150.00','currency_code':'USD'},'transaction_initiation_date':'2026-10-15T10:30:00Z'}},{'transaction_info':{'transaction_status':'P','transaction_amount':{}}}]})
    client=SandboxClient('synthetic-client','synthetic-secret',httpx.MockTransport(transport))
    records,skipped=client.sync()
    assert records[0].amount=='150.00' and records[0].paypal_transaction_id=='TEST-SANDBOX-1' and skipped==1
    client.sync()
    assert calls.count('/v1/oauth2/token')==1
    client.expires=0; client.sync()
    assert calls.count('/v1/oauth2/token')==2

@pytest.mark.parametrize('status,payload,code',[(403,{'secret':'do-not-display'},'PAYPAL_PERMISSION_DENIED'),(200,{'access_token':'secret','scope':'wrong'},'PAYPAL_SCOPE_MISSING'),(500,{},'PAYPAL_UNAVAILABLE')])
def test_sandbox_failures_sanitized(status,payload,code):
    client=SandboxClient('synthetic','synthetic',httpx.MockTransport(lambda r:httpx.Response(status,json=payload)))
    with pytest.raises(APIError) as error: client.sync()
    assert error.value.code==code and 'do-not-display' not in error.value.message

@pytest.mark.parametrize('kind',['png','jpeg','pdf'])
def test_actual_local_ocr(kind,monkeypatch):
    from backend.app.ocr import available, configured_pipeline
    from backend.app.mock_data import TRANSACTION
    from ai_engine.schemas import PipelineInput,EvidenceDocument
    from PIL import Image,ImageDraw,ImageFont
    import base64
    monkeypatch.setenv('OCR_ENABLED','true')
    if not available(): pytest.skip('Install Tesseract, Poppler, Pillow and pytesseract for local OCR integration')
    image=Image.new('RGB',(1500,350),'white')
    draw=ImageDraw.Draw(image)
    draw.text((50,50),'Transaction ID: DEMO-1001\nTotal: USD 150.00',fill='black',font=ImageFont.load_default(size=42),spacing=25)
    output=BytesIO();image.save(output,format=kind.upper())
    doc=EvidenceDocument(id='doc_ocr',filename='synthetic.'+kind,document_type='invoice',media_type={'png':'image/png','jpeg':'image/jpeg','pdf':'application/pdf'}[kind],content_base64=base64.b64encode(output.getvalue()).decode())
    result=configured_pipeline(PipelineInput(analysis_id='analysis_ocr',transaction=TRANSACTION,documents=[doc]))
    assert result.analysis.status=='completed'
    assert any(f.name=='transaction_id' and f.value=='DEMO-1001' for f in result.facts)
    assert any(f.name=='amount' and f.value=='150.00' for f in result.facts)
