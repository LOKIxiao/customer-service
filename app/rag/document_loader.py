from pathlib import Path

from app.rag.text_splitter import TextSplitter
from app.schemas.rag import DocumentChunk


class DocumentLoader:
    def __init__(
            self, 
            knowledge_dir: Path = Path('data/knowledge_base'),
            splitter: TextSplitter | None = None,
            ) -> None:
        self.knowledge_dir = knowledge_dir
        self.splitter = splitter or TextSplitter()

    def load(self) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []

        for file_path in sorted(self.knowledge_dir.glob("*.md")): # 保证文件读取顺序
            if not file_path.is_file():
                continue

            text = file_path.read_text(encoding='utf-8').strip()
            if not text:
                continue

            chunks.extend(
                self.splitter.split(
                    text=text,
                    source=file_path.name
                )
            )
            
        return chunks
