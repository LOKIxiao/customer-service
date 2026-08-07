import os

from dotenv import load_dotenv

from app.memory.session_memory import RedisSessionMemory, SessionMemory


def create_session_memory() -> SessionMemory:
    load_dotenv()
    max_messages = int(os.getenv("SESSION_MAX_MESSAGES", "10"))
    if os.getenv("REDIS_ENABLED", "false").lower() != "true":
        return SessionMemory(max_messages=max_messages)

    try:
        import redis

        client = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT_SECONDS", "1")),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "1")),
        )
        return RedisSessionMemory(
            redis_client=client,
            max_messages=max_messages,
            ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "86400")),
            key_prefix=os.getenv("REDIS_SESSION_KEY_PREFIX", "chat:session"),
        )
    except Exception:
        return SessionMemory(max_messages=max_messages)
