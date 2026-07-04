from collections import defaultdict, deque
from dataclasses import dataclass




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
