from app.agents.memory_agent import MemoryAgent
from app.memory.session_memory import SessionMemory


def test_memory_agent_returns_previous_user_message():
    memory = SessionMemory()
    memory.add_message("s_001", "user", "我的订单什么时候到？")
    memory.add_message("s_001", "assistant", "你的订单已发货。")
    memory.add_message("s_001", "user", "刚才我问了什么？")

    agent = MemoryAgent(memory)

    reply = agent.handle("s_001")

    assert reply == "你刚才问的是：我的订单什么时候到？"


def test_memory_agent_handles_empty_history():
    memory = SessionMemory()
    memory.add_message("s_001", "user", "刚才我问了什么？")

    agent = MemoryAgent(memory)

    reply = agent.handle("s_001")

    assert "没有足够的历史对话记录" in reply