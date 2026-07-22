from app.rag.document_loader import DocumentLoader


def test_document_loader_loads_markdown_files(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()

    (kb_dir / "refund_policy.md").write_text(
        "# 退款政策\n\n退款会在 1-3 个工作日内原路退回。",
        encoding="utf-8",
    )

    loader = DocumentLoader(knowledge_dir=kb_dir)

    chunks = loader.load()

    assert chunks
    assert chunks[0].source == "refund_policy.md"
    assert "退款政策" in chunks[0].content or "退款会在" in chunks[0].content


def test_document_loader_ignores_empty_files(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()

    (kb_dir / "empty.md").write_text("", encoding="utf-8")

    loader = DocumentLoader(knowledge_dir=kb_dir)

    assert loader.load() == []