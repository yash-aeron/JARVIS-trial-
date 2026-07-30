"""
memory/document_indexer.py — Production document chunking, indexing, and project memory manager.

Features:
  1. Chunking engine for text/markdown/code documents (recursive paragraph/heading splitting with overlap).
  2. Document indexing into SQLite memory store with project tags and semantic metadata.
  3. Project-scoped memory management (query, index directory, update, purge).
"""

import os
import re
import uuid
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from memory.schema import MemoryItemModel
from memory.memory_manager import MemoryManager
from observability.logger import logger


class DocumentChunkModel(BaseModel):
    chunk_id:      str
    doc_path:      str
    content:       str
    chunk_index:   int
    total_chunks:  int
    project:       Optional[str] = None
    language:      Optional[str] = None


class DocumentIndexer:
    """
    Parses, chunks, and indexes source code, markdown, and text documents
    into the MemoryManager database with project scoping.
    """

    def __init__(self, memory_manager: MemoryManager):
        self._mem = memory_manager

    # ── Chunking Engine ────────────────────────────────────────────────────────
    def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[str]:
        """
        Recursive text splitter: splits on paragraph breaks (\n\n), line breaks (\n),
        or sentences (. ), maintaining overlap between adjacent chunks.
        """
        if not text or not text.strip():
            return []

        # Split by double newline first (paragraphs)
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) <= chunk_size:
                current_chunk = f"{current_chunk}\n\n{para}".strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # If a single paragraph exceeds chunk_size, split by lines or words
                if len(para) > chunk_size:
                    sub_parts = self._split_large_block(para, chunk_size, chunk_overlap)
                    chunks.extend(sub_parts[:-1])
                    current_chunk = sub_parts[-1] if sub_parts else ""
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        # Apply overlap if chunks were created
        if chunk_overlap > 0 and len(chunks) > 1:
            overlapped: List[str] = [chunks[0]]
            for i in range(1, len(chunks)):
                prev_tail = chunks[i - 1][-chunk_overlap:]
                overlapped.append(f"...{prev_tail}\n{chunks[i]}")
            return overlapped

        return chunks

    def _split_large_block(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        lines = text.splitlines()
        chunks = []
        curr = ""
        for line in lines:
            if len(curr) + len(line) <= chunk_size:
                curr = f"{curr}\n{line}".strip()
            else:
                if curr:
                    chunks.append(curr)
                curr = line
        if curr:
            chunks.append(curr)
        return chunks or [text[:chunk_size]]

    # ── Single Document Indexing ───────────────────────────────────────────────
    def index_document(
        self,
        file_path: str,
        project: Optional[str] = None,
        importance: float = 3.0,
        tags: Optional[List[str]] = None,
    ) -> List[str]:
        """Reads, chunks, and stores a document in project memory."""
        if not os.path.isfile(file_path):
            logger.warning(f"[DocumentIndexer] File not found: {file_path}")
            return []

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            ext = os.path.splitext(file_path)[1].lstrip(".").lower()
            doc_name = os.path.basename(file_path)

            raw_chunks = self.chunk_text(content, chunk_size=600, chunk_overlap=60)
            indexed_ids: List[str] = []

            base_tags = list(tags) if tags else ["document", ext or "txt"]
            if project and project not in base_tags:
                base_tags.append(project)

            now = time.time()
            for idx, text_chunk in enumerate(raw_chunks):
                item_id = f"doc_{uuid.uuid4().hex[:12]}"
                mem_item = MemoryItemModel(
                    item_id=item_id,
                    content=f"[{doc_name} | Chunk {idx+1}/{len(raw_chunks)}]\n{text_chunk}",
                    tags=base_tags,
                    importance=importance,
                    project=project or os.path.basename(os.path.dirname(file_path)),
                    language=ext or "text",
                    source=file_path,
                    confidence=1.0,
                    access_count=0,
                    last_accessed=now,
                    timestamp=now,
                    embedding_version="tf-idf-v1"
                )
                self._mem.store(mem_item)
                indexed_ids.append(item_id)

            logger.info(f"[DocumentIndexer] Indexed '{doc_name}' ({len(raw_chunks)} chunks, Project: '{project}')")
            return indexed_ids

        except Exception as exc:
            logger.error(f"[DocumentIndexer] Failed to index '{file_path}': {exc}")
            return []

    # ── Directory Indexing ────────────────────────────────────────────────────
    def index_directory(
        self,
        dir_path: str,
        project: Optional[str] = None,
        extensions: Optional[List[str]] = None,
        max_files: int = 100,
    ) -> Dict[str, int]:
        """Recursively scans and indexes supported files in a directory."""
        valid_exts = set(e.lower().lstrip(".") for e in (extensions or ["py", "md", "txt", "json", "yml", "yaml", "rst", "js", "ts"]))
        proj_name = project or os.path.basename(os.path.abspath(dir_path))
        indexed_count = 0
        total_chunks = 0

        for root, _, files in os.walk(dir_path):
            # Skip hidden / venv directories
            if any(part.startswith(".") or part in ("venv", "__pycache__", "node_modules", "dist", "build") for part in root.split(os.sep)):
                continue

            for file in files:
                if indexed_count >= max_files:
                    break
                ext = os.path.splitext(file)[1].lstrip(".").lower()
                if ext in valid_exts:
                    full_path = os.path.join(root, file)
                    chunks = self.index_document(full_path, project=proj_name)
                    if chunks:
                        indexed_count += 1
                        total_chunks += len(chunks)

        return {"files_indexed": indexed_count, "total_chunks": total_chunks, "project": proj_name}
