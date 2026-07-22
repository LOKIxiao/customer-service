from app.rag.embedding import FakeEmbeddingClient


def test_fake_embedding_returns_fixed_dimensions():
    client = FakeEmbeddingClient(dimensions=16)

    embedding = client.embed("退款多久到账？")

    assert len(embedding) == 16


def test_fake_embedding_normalizes_vector():
    client = FakeEmbeddingClient(dimensions=16)

    embedding = client.embed("退款")

    assert round(sum(value * value for value in embedding), 6) == 1.0