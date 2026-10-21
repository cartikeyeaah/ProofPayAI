"""HTTP-only client; validate responses against the existing exported API contract."""
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
import re

import requests
import yaml
from jsonschema import Draft202012Validator, FormatChecker

SPEC = yaml.safe_load((Path(__file__).resolve().parents[1] / 'contracts/openapi.yaml').read_text())
MESSAGES = {
    'INVALID_FILE_SIZE': 'File is empty or exceeds the evidence size limit.',
    'UNSUPPORTED_FILE_TYPE': 'Supported evidence: PDF, PNG, JPEG and UTF-8 text.',
    'INVALID_FILE_SIGNATURE': 'File content does not match the selected type.',
    'INVALID_TEXT': 'Text evidence must use UTF-8.',
    'DOCUMENT_LIMIT': 'This transaction has reached its 25-document limit.',
    'ANALYSIS_ACTIVE': 'An analysis is active. Refresh its status before retrying.',
    'TRANSACTION_NOT_FOUND': 'The requested transaction was not found.',
    'ANALYSIS_NOT_FOUND': 'The requested analysis was not found. The backend may have restarted.',
    'VALIDATION_ERROR': 'The backend rejected the request. Check the API contract.',
    'INTERNAL_ERROR': 'The backend encountered an internal error.',
    'HTTP_ERROR': 'The backend rejected this HTTP request.',
}

def valid_url(value):
    try:
        parts = urlsplit(value)
        return bool(parts.scheme in ('http', 'https') and parts.hostname and parts.port != 0
                    and not parts.username and not parts.password and not parts.query
                    and not parts.fragment and not any(c.isspace() for c in value))
    except ValueError:
        return False

@dataclass
class Result:
    data: object = None
    status: int | None = None
    elapsed_ms: float = 0
    error: str | None = None
    code: str | None = None
    request_id: str | None = None

class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')

    def call(self, method, path, schema, *, array=False, files=None, form=None):
        start = perf_counter()
        result = Result()
        try:
            if not valid_url(self.base_url):
                result.error = 'Use an HTTP(S) base URL without credentials, query parameters, or fragments.'
                return result
            # Do not forward environment credentials/netrc or follow redirects to other services.
            with requests.Session() as session:
                session.trust_env = False
                response = session.request(method, self.base_url + path, timeout=(3, 10),
                                           allow_redirects=False, **({'files': files, 'data': form} if files else ({'json': {}} if method == 'POST' else {})))
            result.status = response.status_code
            rid = response.headers.get('X-Request-ID', '')
            if re.fullmatch(r'req_[0-9a-fA-F-]{36}', rid):
                result.request_id = rid
            try:
                payload = response.json()
            except ValueError:
                result.error = 'Backend returned non-JSON content. Check the server and retry.'
                return result
            if response.status_code != (201 if files else (202 if method == 'POST' else 200)):
                error = payload.get('error') if isinstance(payload, dict) else None
                code = error.get('code') if isinstance(error, dict) else None
                if isinstance(code, str) and code in MESSAGES:
                    result.code = code
                    result.error = MESSAGES[code]
                else:
                    result.error = 'API request failed. Check the backend logs using the request ID if available.'
                return result
            ref = {'$ref': f'#/components/schemas/{schema}'}
            check = {'type': 'array', 'items': ref} if array else ref
            validator = Draft202012Validator({**check, 'components': SPEC['components']}, format_checker=FormatChecker())
            if not validator.is_valid(payload):
                result.error = 'Backend response does not match the agreed API contract.'
                return result
            result.data = payload
            return result
        except requests.Timeout:
            result.error = 'Backend request timed out. Refresh to check state before creating another job.'
            return result
        except requests.RequestException:
            result.error = 'Cannot reach backend. Check the connection URL and retry.'
            return result
        finally:
            result.elapsed_ms = round((perf_counter() - start) * 1000, 1)
