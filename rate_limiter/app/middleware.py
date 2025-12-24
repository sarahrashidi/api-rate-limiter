import time
from typing import Optional 
from fastapi import FastAPI, Request, Response 
from fastapi.responses import JSONResponse 
from .rate_limiter import RateLimiter 
from .storage import Storage, InMemoryStorage, RedisStorage
from .config import get_config
from .metrics import record_request 

class RateLimitMiddleware:
    def __init__(self, app:FastAPI, use_redis:bool =False):
        self.app = app
        self.config= get_config
        
        if use_redis:
            self.storage= RedisStorage(
                host = self.config.redis_host,
                port = self.config.redis_port,
                password= self.config.redis_password
                
            )
        else:
            self.storage = InMemoryStorage()
        self.rate_limiter= RateLimiter(self.storage, self.config)
        
        @app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next):
            return await self._process_request(request, call_next)
        
        @app.on_event("shutdown")
        async def shutdown_event():
            await self.storage.close()
            
    def _get_client_id(self, request: Request) -> str:
        api_key = request.header.get("x_api_key")
        if api_key:
            return f"api_key:{api_key}"
        
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    
    def _get_api_key(self, request: Request) ->Optional[str]:
        return request.headers.get("x-api-key")

    async def _process_request(self, request: Request, call_next):
        start_time= time.time()
        if request.url.path == "/metrics":
            return await call_next(request)
        
        client_id = self._get_client_id(request)
        api_key = self._get_api_key(request)
        
        result = await self.rate_limiter.check_rate_limit(
            client_id=client_id,
            method = request.method,
            path = request.url.path,
            api_key = api_key
        )            
        
        endpoint_key= f"{request.method} {request.url.path}"
        record_request(
            endpoint = endpoint_key,
            allowed = result.allowed,
            tokens_consumed = self.rate_limiter.get_endpoint_cost(
                request.method, request.url.path 
            )
        )
        if not result.allowed:
            response = JSONResponse(
                status_code = 429,
                content = {
                    "error":"rate limit exceeded",
                    "retry_after": result.retry_after
                }
            )
            response.headers["retry_after"] = str(int(result.retry_after))
        else: 
            try:
                response = await call_next(request)
                request_latency_ms=(time.time() - start_time) * 1000
                is_error = response.status.code >= 500
                
                await self.rate_limiter.check_rate_limit(
                    client_id = client_id,
                    method = request.method,
                    path = request.url.path,
                    api_key = api_key,
                    request_latency_ms = request_latency_ms,
                    is_error = is_error
                )        
            except Exception as e: 
                request_latency_ms = (time.time() - start_time) * 1000
                await self.rate_limiter.check_rate_limit(
                    client_id = client_id,
                    method = request.method,
                    path = request.url.path,
                    api_key = api_key,
                    request_latency_ms = request_latency_ms,
                    is_error = True
                )
                raise
        response.headers["x_RateLimit_limit"] = str(
            self.rate_limiter.get_client_capacity(api_key)
        )
        response.headers["x_RateLimit_remaining"] = str(result.remaining_tokens)
        return response
