import sqlite3
import os
import time
from typing import List, Optional, Tuple, Any
from memory.schema import MemoryItemModel
from observability.logger import logger

class MemoryManager:
    """Unified Memory Controller supporting rich metadata persistence and semantic retrieval ranking."""
    
    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or "data", exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    item_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    tags TEXT,
                    importance REAL,
                    project TEXT,
                    language TEXT,
                    source TEXT,
                    confidence REAL,
                    access_count INTEGER,
                    last_accessed REAL,
                    timestamp REAL,
                    embedding_version TEXT
                )
            """)
            conn.commit()

    def store(self, item: MemoryItemModel) -> str:
        tags_str = ",".join(item.tags)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO memories 
                (item_id, content, tags, importance, project, language, source, confidence, access_count, last_accessed, timestamp, embedding_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.item_id, item.content, tags_str, item.importance, 
                item.project, item.language, item.source, item.confidence, 
                item.access_count, item.last_accessed, item.timestamp, item.embedding_version
            ))
            conn.commit()
        logger.info(f"[MemoryManager] Stored rich memory '{item.item_id}' [Tags: {tags_str}]")
        return item.item_id

    def query(self, tag: Optional[str] = None, project: Optional[str] = None, min_importance: float = 0.0) -> List[MemoryItemModel]:
        ranked_results = self.query_and_rank(query_tags=[tag] if tag else [], project=project, min_importance=min_importance)
        return [item for item, score in ranked_results]

    def query_and_rank(self, query_tags: List[str] = None, project: Optional[str] = None, min_importance: float = 0.0) -> List[Tuple[MemoryItemModel, float]]:
        """Semantic retrieval ranking algorithm combining tag match, importance, access count, and recency decay."""
        query_tags = query_tags or []
        query_sql = "SELECT item_id, content, tags, importance, project, language, source, confidence, access_count, last_accessed, timestamp, embedding_version FROM memories WHERE importance >= ?"
        params: List[Any] = [min_importance]
        
        if project:
            query_sql += " AND project = ?"
            params.append(project)
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            rows = cursor.execute(query_sql, params).fetchall()
            
        now = time.time()
        scored_items: List[Tuple[MemoryItemModel, float]] = []
        
        for r in rows:
            tags_list = r[2].split(",") if r[2] else []
            item = MemoryItemModel(
                item_id=r[0], content=r[1], tags=tags_list,
                importance=r[3], project=r[4], language=r[5],
                source=r[6], confidence=r[7], access_count=r[8],
                last_accessed=r[9], timestamp=r[10], embedding_version=r[11]
            )
            
            tag_matches = sum(1 for t in query_tags if t in tags_list)
            if query_tags and tag_matches == 0:
                continue
                
            age_hours = max(0.1, (now - item.timestamp) / 3600.0)
            recency_score = 1.0 / (1.0 + (age_hours / 24.0))  # 24 hour half-life
            access_boost = min(1.5, 1.0 + (item.access_count * 0.05))
            
            # Semantic ranking score formula
            score = (tag_matches * 2.5) + (item.importance * 1.2) + (item.confidence * 1.0) + (recency_score * 0.8) * access_boost
            scored_items.append((item, score))
            
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return scored_items
