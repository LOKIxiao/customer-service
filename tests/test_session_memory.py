from app.memory.session_memory import SessionMemory


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