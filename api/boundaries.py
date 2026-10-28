"""Small local-only API boundary: exact origins, bounded bodies, structured errors."""
import os
from starlette.responses import JSONResponse
from api.rate_limits import RequestLimiter

ALLOWED_ORIGINS=set(os.getenv('RESEARCH_ALLOWED_ORIGINS','http://localhost:3000,http://127.0.0.1:3000').split(','))


class RequestBoundary:
    def __init__(self, app):
        self.app=app
        self.limiter=RequestLimiter()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope,receive,send)
        headers={key.decode().lower():value.decode() for key,value in scope['headers']}
        origin=headers.get('origin')
        if origin and origin not in ALLOWED_ORIGINS:
            return await JSONResponse({'error':{'code':'origin_denied','message':'Origin not allowed'}},403)(scope,receive,send)
        denied=self.limiter.admit(scope['method'],scope['path'])
        if denied:
            return await JSONResponse({'error':{'code':'rate_limited','message':'Local request rate limit reached',**denied}},429,
                headers={'Retry-After':str(denied['retry_after_seconds'])})(scope,receive,send)
        if scope['method'] in {'POST','PUT','PATCH'}:
            content_type=headers.get('content-type','').split(';')[0]
            if content_type not in {'application/json','text/csv'} and scope['path'] != '/trade':
                return await JSONResponse({'error':{'code':'content_type','message':'Use application/json or text/csv'}},415)(scope,receive,send)
            parts=[];size=0
            while True:
                message=await receive()
                if message['type']=='http.disconnect': return
                part=message.get('body',b''); size+=len(part)
                if size>2_000_000:
                    return await JSONResponse({'error':{'code':'body_limit','message':'Request exceeds 2 MB'}},413)(scope,receive,send)
                parts.append(part)
                if not message.get('more_body',False): break
            consumed=False
            async def replay():
                nonlocal consumed
                if not consumed:
                    consumed=True
                    return {'type':'http.request','body':b''.join(parts),'more_body':False}
                return await receive()
            return await self.app(scope,replay,send)
        return await self.app(scope,receive,send)
