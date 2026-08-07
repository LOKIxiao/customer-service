from app.memory.session_memory import RedisSessionMemory, SessionMemory


class FakeRedis:
    def __init__(self, store=None):
        self.store = store if store is not None else {}
        self.expirations = {}

    def ping(self):
        return True

    def pipeline(self, transaction=True):
        return self

    def rpush(self, key, value):
        self.store.setdefault(key, []).append(value)
        return self

    def ltrim(self, key, start, end):
        values = self.store.get(key, [])
        self.store[key] = values[start:] if end == -1 else values[start : end + 1]
        return self

    def expire(self, key, seconds):
        self.expirations[key] = seconds
        return self

    def execute(self):
        return []

    def lrange(self, key, start, end):
        values = self.store.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]

    def delete(self, key):
        self.store.pop(key, None)


class UnavailableRedis:
    def ping(self):
        raise ConnectionError("redis unavailable")


def test_session_memory_saves_messages():
    memory = SessionMemory()

    memory.add_message("s_001", "user", "我的订单什么时候到？")
    memory.add_message("s_001", "assistant", "你的订单已发货。")

    messages = memory.get_messages("s_001")

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "我的订单什么时候到？"


def test_session_memory_limits_message_count():
    memory = SessionMemory(max_messages=2)

    memory.add_message("s_001", "user", "第一句")
    memory.add_message("s_001", "assistant", "第二句")
    memory.add_message("s_001", "user", "第三句")

    messages = memory.get_messages("s_001")

    assert len(messages) == 2
    assert messages[0].content == "第二句"
    assert messages[1].content == "第三句"


def test_session_memory_clear():
    memory = SessionMemory()

    memory.add_message("s_001", "user", "你好")
    memory.clear("s_001")

    assert memory.get_messages("s_001") == []


def test_redis_session_memory_survives_new_memory_instance():
    shared_store = {}
    first_process = RedisSessionMemory(
        FakeRedis(shared_store), max_messages=10, ttl_seconds=3600
    )
    first_process.add_message("s_restart", "user", "耳机怎么连接？")
    first_process.add_message("s_restart", "assistant", "请打开蓝牙进行连接。")

    restarted_process = RedisSessionMemory(
        FakeRedis(shared_store), max_messages=10, ttl_seconds=3600
    )
    messages = restarted_process.get_messages("s_restart")

    assert [message.content for message in messages] == [
        "耳机怎么连接？",
        "请打开蓝牙进行连接。",
    ]


def test_redis_session_memory_trims_window_and_refreshes_ttl():
    redis = FakeRedis()
    memory = RedisSessionMemory(redis, max_messages=2, ttl_seconds=1800)

    memory.add_message("s_001", "user", "第一句")
    memory.add_message("s_001", "assistant", "第二句")
    memory.add_message("s_001", "user", "第三句")

    assert [item.content for item in memory.get_messages("s_001")] == ["第二句", "第三句"]
    assert redis.expirations["chat:session:s_001"] == 1800


def test_redis_session_memory_falls_back_when_redis_is_unavailable():
    memory = RedisSessionMemory(UnavailableRedis(), max_messages=10)

    memory.add_message("s_001", "user", "仍然可以处理当前请求")

    assert memory.is_using_redis is False
    assert memory.get_messages("s_001")[0].content == "仍然可以处理当前请求"
