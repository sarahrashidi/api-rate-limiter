from prometheus_client import Counter, Histogram, generate_latest, REGISTRY 
from fastapi import Response

REQUESTS_ALLOWED = Counter(
    'rate_limiter_requests_allowed_total',
    'total number of allowed requests',
    ['endpoint']
    
)

REQUESTS_BLOCKED = Counter(
    'rate_limiter_requests_blocked_total',
    'total number of blucked requests',
    ['endpoint']
)

TOKENS_CONSUMED = Counter(
    'rate_limiter_tokens_consumed_total',
    'total tokens consumed',
    ['endpoint']
)


REQUESTED_LATENCY = Histogram(
    'rate_limiter_request_latency_seconds',
    'request latency in seconds',
    ['endpoint'],
    buckets = [0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)
def record_request(endpoint: str, allowed: bool, tokens_consumed: int):
    if allowed:
        REQUESTS_ALLOWED.labels(endpoint=endpoint).inc()
        TOKENS_CONSUMED.labels(endpoint=endpoint).inc(tokens_consumed)
    else:
        REQUESTS_BLOCKED.labels(endpoint=endpoint).inc()


def get_metrics_response():
    return Response(generate_latest(REGISTRY), media_type="text/plain")
