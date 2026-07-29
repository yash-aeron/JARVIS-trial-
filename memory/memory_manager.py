import sqlite3
import os
import time
from typing import List, Optional, Tuple
from memory.schema import MemoryItemModel
from observability.logger import logger

class MemoryManager:
    """Unified Memory Controller supporting retrieval ranking by tag matching, importance rating, and recency."""
    
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
                    timestamp REAL,
                    version TEXT
                )
            """)
            conn.commit()

    def store(self, item: MemoryItemModel) -> str:
        tags_str = ",".join(item.tags)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO memories 
                (item_id, content, tags, importance, project, language, timestamp, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item.item_id, item.content, tags_str, item.importance, item.project, item.language, item.timestamp, item.version))
            conn.commit()
        logger.info(f"[MemoryManager] Stored memory '{item.item_id}' [Tags: {tags_str}]")
        return item.item_id

    def query(self, tag: Optional[str] = None, project: Optional[str] = None, min_importance: float = 0.0) -> List[MemoryItemModel]:
        ranked_results = self.query_and_rank(query_tags=[tag] if tag else [], project=project, min_importance=min_importance)
        return [item for item, score in ranked_results]

    def query_and_rank(self, query_tags: List[str] = None, project: Optional[str] = None, min_importance: float = 0.0) -> List[Tuple[MemoryItemModel, float]]:
        """Ranks retrieved memories based on tag matches, importance score, and recency decay."""
        query_tags = query_tags or []
        query_sql = "SELECT item_id, content, tags, importance, project, language, timestamp, version FROM memories WHERE importance >= ?"
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
                timestamp=r[6], version=r[7]
            )
            
            # Ranking formula: Tag match weight + Importance weight + Recency decay
            tag_matches = sum(1 for t in query_tags if t in tags_list)
            if query_tags and tag_matches == 0:
                continue
                
            age_hours = max(0.1, (now - item.timestamp) / 3600.0)
            recency_score = 1.0 / (1.0 + (age_hours / 24.0))  # Half life 24 hours
            
            score = (tag_matches * 2.0) + (item.importance * 1.0) + (recency_score * 0.5)
            scored_items.append((item, score))
            
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return scored_items
