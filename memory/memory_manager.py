import sqlite3
import os
from typing import List, Optional
from memory.schema import MemoryItemModel
from observability.logger import logger

class MemoryManager:
    """Unified Memory Controller for tagged & timed memory items backed by SQLite schema."""
    
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
        query_sql = "SELECT item_id, content, tags, importance, project, language, timestamp, version FROM memories WHERE importance >= ?"
        params: List[Any] = [min_importance]
        
        if project:
            query_sql += " AND project = ?"
            params.append(project)
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            rows = cursor.execute(query_sql, params).fetchall()
            
        results = []
        for r in rows:
            tags_list = r[2].split(",") if r[2] else []
            if tag and tag not in tags_list:
                continue
            results.append(MemoryItemModel(
                item_id=r[0], content=r[1], tags=tags_list,
                importance=r[3], project=r[4], language=r[5],
                timestamp=r[6], version=r[7]
            ))
        return results
