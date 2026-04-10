import os

import redis

# Usamos el host de localhost para desarrollo local
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def get_redis():
    return redis_client
