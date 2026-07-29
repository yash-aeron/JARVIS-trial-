"""
tools/system_tools/memory_tool.py — Structured Memory & Document Indexing Tool for JARVIS.

Capabilities:
  recall            — Semantic memory search with importance, recency, & project weighting.
  store             — Save explicit user preference, fact, or project rule.
  index_doc         — Parse, chunk, and index a single document.
  index_dir         — Scan and index an entire directory for project memory.
  query_project     — Retrieve all indexed memories for a specific project.
"""

import asyncio
import os
from typing import Optional, List, Dict, Any

from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel
from memory.memory_manager import MemoryManager
from memory.document_indexer import DocumentIndexer
from memory.schema import MemoryItemModel
from observability.logger import logger


class MemoryManagementTool(ITool):
    """
    JARVIS tool for storing, recalling, and indexing project memories and documentation.
    """

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self._mem = memory_manager or MemoryManager()
        self._indexer = DocumentIndexer(self._mem)

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="memory_tool",
            description=(
                "Search, store, and index semantic memories, user preferences, "
                "project rules, and local documentation files."
            ),
            capabilities=[
                "recall_memory", "store_memory", "index_document",
                "index_directory", "query_project_memory"
            ],
            permission_level="LOW",
            args_schema={
                "action":      "str  — recall | store | index_doc | index_dir | query_project",
                "query":       "str? — search query text for recall action",
                "content":     "str? — text content for store action",
                "project":     "str? — project context tag (e.g. 'JARVIS')",
                "path":        "str? — file or directory path for indexing",
                "importance":  "float? — importance score 1.0 to 5.0 (default 3.0)",
                "tags":        "list[str]? — custom tags for stored items",
            }
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        action     = request.args.get("action", "recall").strip().lower()
        query_text = request.args.get("query", "").strip()
        content    = request.args.get("content", "").strip()
        project    = request.args.get("project", None)
        path       = request.args.get("path", "").strip()
        importance = float(request.args.get("importance", 3.0))
        tags       = request.args.get("tags", [])

        logger.info(f"[MemoryTool] action='{action}' project='{project}' query='{query_text[:30]}' [CID: {request.correlation_id}]")

        loop = asyncio.get_event_loop()

        try:
            if action in ("recall", "search"):
                results = await loop.run_in_executor(
                    None,
                    lambda: self._mem.semantic_recall(
                        query_text=query_text,
                        top_k=5,
                        project=project,
                        min_importance=0.0
                    )
                )
                data = [
                    {
                        "item_id": item.item_id,
                        "content": item.content,
                        "score": round(score, 3),
                        "importance": item.importance,
                        "project": item.project,
                        "source": item.source,
                        "tags": item.tags
                    }
                    for item, score in results
                ]
                return ToolResultModel(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status="completed",
                    result={"memories": data, "count": len(data)}
                )

            elif action in ("store", "save"):
                if not content:
                    return ToolResultModel(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        status="failed",
                        error="Content is required for store action."
                    )

                item_id = f"mem_{os.urandom(4).hex()}"
                mem_item = MemoryItemModel(
                    item_id=item_id,
                    content=content,
                    tags=tags or ["user_fact"],
                    importance=importance,
                    project=project,
                    source="user_explicit",
                    confidence=1.0
                )
                stored_id = await loop.run_in_executor(None, lambda: self._mem.store(mem_item))
                return ToolResultModel(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status="completed",
                    result={"item_id": stored_id, "action": "stored"}
                )

            elif action in ("index_doc", "index_file"):
                if not path or not os.path.isfile(path):
                    return ToolResultModel(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        status="failed",
                        error=f"Valid file path is required for index_doc (got: '{path}')"
                    )

                chunk_ids = await loop.run_in_executor(
                    None,
                    lambda: self._indexer.index_document(file_path=path, project=project, importance=importance, tags=tags)
                )
                return ToolResultModel(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status="completed",
                    result={"chunks_indexed": len(chunk_ids), "path": path, "project": project}
                )

            elif action in ("index_dir", "index_directory"):
                if not path or not os.path.isdir(path):
                    return ToolResultModel(
                        request_id=request.request_id,
                        correlation_id=request.correlation_id,
                        status="failed",
                        error=f"Valid directory path is required for index_dir (got: '{path}')"
                    )

                stats = await loop.run_in_executor(
                    None,
                    lambda: self._indexer.index_directory(dir_path=path, project=project)
                )
                return ToolResultModel(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status="completed",
                    result=stats
                )

            elif action in ("query_project", "project"):
                results = await loop.run_in_executor(
                    None,
                    lambda: self._mem.query(project=project)
                )
                data = [
                    {
                        "item_id": item.item_id,
                        "content": item.content,
                        "importance": item.importance,
                        "source": item.source,
                        "tags": item.tags
                    }
                    for item in results
                ]
                return ToolResultModel(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status="completed",
                    result={"memories": data, "count": len(data), "project": project}
                )

            else:
                return ToolResultModel(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status="failed",
                    error=f"Unknown action '{action}'. Valid: recall, store, index_doc, index_dir, query_project"
                )

        except Exception as exc:
            logger.error(f"[MemoryTool] Execution error: {exc}")
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error=str(exc)
            )

    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="undone",
            result={"note": "Memory indexing/recall operations do not support undo."}
        )
