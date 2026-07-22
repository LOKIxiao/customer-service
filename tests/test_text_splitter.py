from app.rag.text_splitter import TextSplitter


def test_text_splitter_splits_paragraphs():
    splitter = TextSplitter(chunk_size=100)

    chunks = splitter.split(
        text="第一段内容。\n\n第二段内容。",
        source="test.md",
    )

    assert len(chunks) == 2
    assert chunks[0].source == "test.md"
    assert chunks[0].chunk_id == "test.md:0"
    assert chunks[0].content == "第一段内容。"
    assert chunks[1].content == "第二段内容。"


def test_text_splitter_splits_long_paragraph():
    splitter = TextSplitter(chunk_size=10, chunk_overlap=2)

    chunks = splitter.split(
        text="这是一个很长很长很长很长的段落。",
        source="long.md",
    )

    assert len(chunks) > 1
    assert all(chunk.source == "long.md" for chunk in chunks)