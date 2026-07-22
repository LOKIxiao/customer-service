import re

from app.schemas.rag import DocumentChunk

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")


class TextSplitter:
    def __init__(self, chunk_size: int=500, chunk_overlap: int=80) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap #防止语意断裂


    def split(self, text: str, source: str) -> list[DocumentChunk]:
        paragraphs = [
            paragraph.strip()
            for paragraph in text.split('\n\n')
            if paragraph.strip()
        ]

        chunks: list[DocumentChunk] = []
        chunk_index = 0
        heading_stack: dict[int, str] = {} # 按标题层级记录当前上下文，用于给正文 chunk 加面包屑前缀

        for paragraph in paragraphs:
            heading_match = HEADING_PATTERN.match(paragraph)
            if heading_match:
                level = len(heading_match.group(1))
                heading_stack = {lvl: h for lvl, h in heading_stack.items() if lvl < level}
                heading_stack[level] = paragraph
                continue

            breadcrumb = " > ".join(heading_stack[lvl] for lvl in sorted(heading_stack))

            for piece in self._window(paragraph):
                content = f"{breadcrumb}\n\n{piece}" if breadcrumb else piece
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{source}:{chunk_index}",
                        source=source,
                        content=content,
                        metadata={"chunk_index": chunk_index, "heading": breadcrumb},
                    )
                )
                chunk_index += 1

        return chunks

    def _window(self, paragraph: str) -> list[str]:
        if len(paragraph) <= self.chunk_size:
            return [paragraph]

        pieces: list[str] = []
        start = 0
        while start < len(paragraph):
            end = start + self.chunk_size
            piece = paragraph[start:end].strip()

            if piece:
                pieces.append(piece)

            if end >= len(paragraph):
                break

            start = max(end - self.chunk_overlap, start + 1)

        return pieces

