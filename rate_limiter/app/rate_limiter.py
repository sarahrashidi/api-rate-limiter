import time 
from dataclasses import dataclass
from typing import Optional
from .config import RateLimitConfig

@dataclass
class RateLimitResult:
    allowed: bool
    remaining_tokens: int 
    retry_after: Optional[float] =None 
    
class TokenBucket:
    def __init__(
        self,
        client_id: str,
        capacity: int,
        refill_rate_per_minute: int,
        storage,
        config: RateLimitConfig
    ):
        self.client_id = client_id
        self.capacity = capacity
        self.refill_rate_per_second = refill_rate_per_minute / 60
        self.storage = storage
        self.config= config
        self.current_refill_rate = refill_rate_per_minute
        self.error_count = 0
        self.request_count = 0
        self.total_latency_ms=0
    
    async def consume(
        self,
        tokens: int, 
        endpoint: str,
        request_latency_ms: float =0,
        is_error: bool = False
    ) -> RateLimitResult:
        await self._update_adaptive_metrics(request_latency_ms, is_error)
        
        current_state = await self.storage.get_bucket_state(self.client_id)
        now= time.time()
        
        if current_state is None:
            current_state= {
                'tokens': self.capacity,
                'last_update': now
            }
        time_passed = now - current_state['last_update']
        refill_amount = time_passed* (self.current_refill_rate/ 60)
        
        current_tokens = min(
            self.capacity,
            current_state['tokens'] + refill_amount
        )
        if current_tokens >= tokens:
            current_tokens -= tokens
            allowed = True 
            retry_after= None 
        else:
            allowed = False 
            needed_tokens = tokens - current_tokens
            retry_after = needed_tokens / (self.current_refill_rate / 60)
        
        new_state = {
            'tokens': current_tokens,
            'last_update':now
        }
        await self.storage.set_bucket_state(self.client_id, new_state)
        return RateLimitResult(
            allowed=allowed,
            remaining_tokens= int(current_tokens),
            retry_after= retry_after
        )
        
    async def _update_adaptive_metrics(
        self, 
        request_latency_ms: float,
        is_error: bool
        
    ) -> None:
        self.request_count +=1
        self.total_latency_ms += request_latency_ms
        if is_error:
            self.error_count +=1
        if self.request_count % 100 == 0:
            await self._adjust_refill_rate()
    
    async def _adjust_refill_rate(self) -> None:
        if self.request_count == 0:
            return
        
        error_rate = self.error_count / self.request_count
        avg_latency = self.total_latency_ms/ self.request_count
        
        should_reduce = (
            error_rate > self.config.error_rate_threshold or  avg_latency > self.config.latency_threshold_ms
        )
        if should_reduce:
            self.current_refill_rate = max(
                1,
                self.current_refill_rate * self.config.adaptive_reduction_factor
            )
        
        #  *** reset metrics for next window ***
        self.error_count=0
        self.request_count=0
        self.total_latency_ms=0
        
        
    class RateLimiter:
        def __init__(self, storage, config:RateLimitConfig):
            self.storage = storage
            self.config= config
            self.buckets = {}
        
        def get_endpoint_cost(self, method:str, path:str) ->int:
            key= f"{method} {path}"
            return self.config.endpoint_costs.get(key, 5) 
        
        def get_client_capacity(self, api_key: Optional[str]) -> int:
            if api_key and api_key.startswith("premium_"):
                return self.config.premium_tier_capacity
            return self.config.free_tier_capacity
        
        async def check_rate_limit(
            self,
            client_id: str,
            method: str,
            path: str,
            api_key: Optional[str]=None,
            request_latency_ms: float=0,
            is_error: bool=False 
            
        ) -> RateLimitResult:
            capacity= self.get_client_capacity(api_key)
            cost= self.get_endpoint_cost(method, path)
            bucket_key = f"{client_id}_{capacity}"
            if bucket_key not in self.buckets:
                self.buckets[bucket_key] = TokenBucket(
                    client_id= client_id,
                    capacity= capacity,
                    refill_rate_per_minute=self.config.refill_rate_per_minute,
                    storage= self.storage,
                    config= self.config
                )
            bucket= self.buckets[bucket_key]
            
            
            return await bucket.consume(
                tokens = cost,
                endpoint = f"{method} {path}",
                request_latency_ms = request_latency_ms,
                is_error = is_error
            )
            