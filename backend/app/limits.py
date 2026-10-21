"""Bound bodies before multipart parsing, including chunked requests."""
from fastapi.responses import JSONResponse

class BodyLimitMiddleware:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        limit = 10*1024*1024+65536 if scope['path'].endswith('/documents') else 256*1024
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect': return
            chunk = message.get('body',b''); size += len(chunk)
            if size > limit:
                rid=scope.get('state',{}).get('request_id','')
                response=JSONResponse(status_code=413,content={'error':{'code':'REQUEST_TOO_LARGE','message':'Request body exceeds the permitted size.','request_id':rid}},headers={'X-Request-ID':rid})
                return await response(scope,receive,send)
            chunks.append(chunk)
            if not message.get('more_body',False): break
        sent=False
        async def replay():
            nonlocal sent
            if not sent:
                sent=True
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope,replay,send)
