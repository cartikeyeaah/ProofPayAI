"""Local prototype worker: killable subprocess, no duplicate AI implementation."""
import contextlib
import multiprocessing
import os
import signal
from ai_engine import PipelineInput, PipelineResult, run_pipeline
from ai_engine.validation.output_validator import validate_output
from .integration_schemas import AnalysisDetails
from backend.db.repository import save, event


def pipeline_process(connection, payload, runner):
    # Parser diagnostics can include document text; never forward them to web logs.
    try:
        if hasattr(os, 'setsid'): os.setsid()
        with open(os.devnull, 'w') as sink, contextlib.redirect_stderr(sink), contextlib.redirect_stdout(sink):
            value = runner(PipelineInput.model_validate(payload))
            if isinstance(value, PipelineResult):
                value = value.model_dump(mode='json')
            connection.send(('ok', value))
    except Exception:
        connection.send(('error', None))
    finally:
        connection.close()


def execute_job(app, payload, store=None):
    store = store or app.state.store
    aid = payload.analysis_id
    ids = [doc.id for doc in payload.documents]
    with store.lock:
        store.analyses[aid] = store.analyses[aid].model_copy(update={'status': 'processing'})
        for doc_id in ids:
            store.documents[doc_id].processing_status = 'processing'
            store.documents[doc_id].analysis_id = aid
            store.documents[doc_id].facts = []
            store.documents[doc_id].issue_codes = []
        save(store)
    result, failure = None, None
    ctx = multiprocessing.get_context('spawn')
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=pipeline_process, args=(sender, payload.model_dump(mode='json'), app.state.pipeline_runner), daemon=True)
    try:
        process.start()
        sender.close()
        if not receiver.poll(app.state.pipeline_timeout):
            failure = 'PIPELINE_TIMEOUT'
        else:
            outcome, raw = receiver.recv()
            if outcome != 'ok':
                failure = 'PIPELINE_ERROR'
            else:
                try:
                    result = PipelineResult.model_validate(raw)
                    validate_output(payload, result)
                    if result.analysis.status not in ('completed', 'failed'):
                        raise ValueError('Non-terminal worker result')
                except Exception:
                    result, failure = None, 'INVALID_PIPELINE_OUTPUT'
    except Exception:
        failure = 'PIPELINE_ERROR'
    finally:
        receiver.close()
        sender.close()
        if process.pid is not None:
            process.join(timeout=0.1)
            if process.is_alive():
                try:
                    if hasattr(os, 'killpg'): os.killpg(process.pid, signal.SIGTERM)
                    else: process.terminate()
                except ProcessLookupError: process.terminate()
                process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
    with store.lock:
        if result is not None:
            store.analyses[aid] = result.analysis
            for doc_id in ids:
                metadata = store.documents[doc_id]
                metadata.facts = [fact for fact in result.facts if fact.source.document_id == doc_id]
                metadata.issue_codes = [issue.code for issue in result.issues if issue.document_id == doc_id]
                match = next(m for m in result.matches if m.document_id == doc_id)
                if match.status == 'duplicate':
                    metadata.processing_status = 'duplicate'
                elif any(code in ('IMAGE_OCR_REQUIRED', 'PDF_OCR_REQUIRED', 'PDF_READER_UNAVAILABLE') for code in metadata.issue_codes):
                    metadata.processing_status = 'unsupported'
                elif match.status == 'unreadable':
                    metadata.processing_status = 'failed'
                else:
                    metadata.processing_status = 'parsed'
        else:
            store.analyses[aid] = store.analyses[aid].model_copy(update={'status': 'failed'})
            for doc_id in ids:
                store.documents[doc_id].processing_status = 'failed'
                store.documents[doc_id].issue_codes = [failure]
        store.details[aid] = AnalysisDetails(analysis_id=aid, failure_code=failure, result=result)
        store.active_transactions.discard(payload.transaction.id)
        if result is not None:
            from .workspace import initialize_draft
            initialize_draft(store, result.analysis)
        event(store, 'analysis_' + store.analyses[aid].status, aid)
        save(store)
