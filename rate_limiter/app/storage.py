from abc import ABC, abstractmethod
from typing import Optional, Dict, Any 
import json 

class Storage(ABC):
    @abstractmethod
    async def get_bucket_state(self, client_id:str) -> Optional[Dict[str, Any]]:
        pass
    @abstractmethod
    async def set_bucket_state(self, client_id:str, state: Dict[str,Any]) -> None:
        pass
    @abstractmethod
    async def close(self) -> None:
        pass 
    
class InMemoryStorage(Storage):
    def __init__(self):
        self.data= {}
        
    async def get_bucket_state(self, client_id:str):
        return self.data.get(client_id)
    
    async def set_bucket_state(self, client_id: str, state: Dict[str, Any]) -> None:
        self.data[client_id] = state 
        
    async def close(self) -> None:
        self.data.clear()
        
class RedisStorage(Storage):
    def __init__(self, host:str = "localhost", port:int=6379, password:str = ""):
        import redis.asyncio as redis 
        self.redis = redis.Redis(
            host= host,
            port = port,
            password= password if password else None,
            decode_responses = True
        )
        
    async def get_bucket_state(self, client_id: str) -> Optional[Dict[str, Any]]:
        data = await self.redis.get(f"rate_limit:{client_id}")
        if data:
            return json.loads(data)
        return None 
    async def set_bucket_state(self, client_id: str, state: Dict[str, Any]) -> None:
        await self.redis.setex(
            f"rate_limit:{client_id}",
            300,
            json.dumps(state)
            
        )
        
    async def close(self) -> None:
        await self.redis.close()
        await self.redis.connection_pool.disconnect()

      
