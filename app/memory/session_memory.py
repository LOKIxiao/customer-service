from collections import defaultdict, deque
from dataclasses import dataclass
import json
from typing import Any




@dataclass
class MessageRecord:
    role: str
    content: str


class SessionMemory:
    def __init__(self, max_messages: int = 10) -> None:
        self.max_messages = max_messages
        # 滑动窗口切片max_messages条最近消息
        self._store: dict[str, deque[MessageRecord]] = defaultdict(
            lambda: deque(maxlen=max_messages)
        )

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self._store[session_id].append(
            MessageRecord(role=role, content=content)
        )
    
    def get_messages(self, session_id: str) -> list[MessageRecord]:
        return list(self._store[session_id])

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    def close(self) -> None:
        return None


class RedisSessionMemory(SessionMemory):
    """Redis-backed recent-message window with an in-memory fail-open fallback."""

    def __init__(
        self,
        redis_client: Any,
        max_messages: int = 10,
        ttl_seconds: int = 86400,
        key_prefix: str = "chat:session",
        fallback: SessionMemory | None = None,
    ) -> None:
        super().__init__(max_messages=max_messages)
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix.rstrip(":")
        self.fallback = fallback or SessionMemory(max_messages=max_messages)
        self._redis_available = self._ping()

    @property
    def is_using_redis(self) -> bool:
        return self._redis_available

    def _ping(self) -> bool:
        try:
            return bool(self.redis_client.ping())
        except Exception:
            return False

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}:{session_id}"

    def add_message(self, session_id: str, role: str, content: str) -> None:
        if not self._redis_available:
            self.fallback.add_message(session_id, role, content)
            return

        payload = json.dumps(
            {"role": role, "content": content},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            pipeline = self.redis_client.pipeline(transaction=True)
            pipeline.rpush(self._key(session_id), payload)
            pipeline.ltrim(self._key(session_id), -self.max_messages, -1)
            pipeline.expire(self._key(session_id), self.ttl_seconds)
            pipeline.execute()
        except Exception:
            self._redis_available = False
            self.fallback.add_message(session_id, role, content)

    def get_messages(self, session_id: str) -> list[MessageRecord]:
        if not self._redis_available:
            return self.fallback.get_messages(session_id)

        try:
            rows = self.redis_client.lrange(self._key(session_id), 0, -1)
            messages: list[MessageRecord] = []
            for row in rows:
                if isinstance(row, bytes):
                    row = row.decode("utf-8")
                data = json.loads(row)
                messages.append(
                    MessageRecord(role=str(data["role"]), content=str(data["content"]))
                )
            return messages
        except Exception:
            self._redis_available = False
            return self.fallback.get_messages(session_id)

    def clear(self, session_id: str) -> None:
        if not self._redis_available:
            self.fallback.clear(session_id)
            return
        try:
            self.redis_client.delete(self._key(session_id))
        except Exception:
            self._redis_available = False
            self.fallback.clear(session_id)

    def close(self) -> None:
        close = getattr(self.redis_client, "close", None)
        if callable(close):
            close()
