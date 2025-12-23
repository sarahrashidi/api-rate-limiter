import os
from dataclasses import dataclass 
from typing import Dict 

@dataclass
class RateLimitConfig:
    free_tier_capacity: int=60
    premium_tier_capacity: int = 300
    refill_rate_per_minute: int = 60
    endpoint_costs: Dict[str, int]= None 
    
    error_rate_threshold: float= 0.1 
    latency_threshold_ms: int= 500
    adaptive_reduction_factor: float = 0.5
    
    redis_host: str= "localhost"
    redis_port: int= 6379
    redis_password: str= ""
    
    def __post_init__(self):
        if self.endpoint_costs is None:
            self.endpoint_costs = {
                "GET /health": 1,
                "GET /metrics": 1,
                "GET /api/data": 5,
                "POST /api/data": 10,
                "GET /api/search": 20,
                
            }
            
def get_config() -> RateLimitConfig:
    return RateLimitConfig(
        free_tier_capacity= int(os.getenv("free_tier_capacity", "60")),
        premium_tier_capacity= int(os.getenv("premium_tier_capacity", "300")),
        refill_rate_per_minute=int(os.getenv("refill_rate", "60")),
        redis_host= os.getenv("redis_host", "localhost"),
        redis_port= int(os.getenv("redis_port", "6379")),
        redis_password= os.getenv("redis_password", ""),
        
    )