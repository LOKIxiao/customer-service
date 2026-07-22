from app.memory.long_term_store import UserMemoryStore
from app.rag.embedding import FakeEmbeddingClient


def test_long_term_store_saves_and_recalls_memory(tmp_path):
    store = UserMemoryStore(FakeEmbeddingClient(), persist_directory=tmp_path / "user_memory")

    store.add_memory("u_001", "preference", "用户偏好无线降噪耳机，更看重续航")

    results = store.search_memories("u_001", "耳机偏好是什么", top_k=3)

    assert results
    assert results[0].user_id == "u_001"
    assert results[0].category == "preference"


def test_long_term_store_isolates_memories_by_user(tmp_path):
    store = UserMemoryStore(FakeEmbeddingClient(), persist_directory=tmp_path / "user_memory")

    store.add_memory("u_001", "preference", "用户偏好无线降噪耳机")
    store.add_memory("u_002", "preference", "用户偏好机械键盘青轴")

    results = store.search_memories("u_002", "耳机偏好是什么", top_k=3)

    assert all(memory.user_id == "u_002" for memory in results)


def test_long_term_store_returns_empty_for_unknown_user(tmp_path):
    store = UserMemoryStore(FakeEmbeddingClient(), persist_directory=tmp_path / "user_memory")

    store.add_memory("u_001", "preference", "用户偏好无线降噪耳机")

    assert store.search_memories("u_999", "任何问题") == []
