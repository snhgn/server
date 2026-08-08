import logging
from pathlib import Path

logger = logging.getLogger("ai-service.rag.loader")


def load_file(file_path: str) -> str:
    """解析文件，返回纯文本"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()
    if suffix == ".md":
        return path.read_text(encoding="utf-8")
    elif suffix == ".txt":
        return path.read_text(encoding="utf-8")
    elif suffix == ".pdf":
        return _load_pdf(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _load_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text)
    return "\n\n".join(texts)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """将文本切分为重叠的片段"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks
