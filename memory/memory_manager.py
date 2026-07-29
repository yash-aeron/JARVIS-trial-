import sqlite3
import os
import math
import time
import re
from typing import List, Optional, Tuple, Any, Dict, Set
from memory.schema import MemoryItemModel
from observability.logger import logger

class MemoryManager:
    """Production Semantic Memory Controller with Cosine Similarity vector search, multi-factor weighted formula, and access metrics."""
    
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
        logger.info(f"[MemoryManager] Stored semantic memory '{item.item_id}' [Tags: {tags_str}]")
        return item.item_id

    def semantic_recall(
        self, 
        query_text: str, 
        top_k: int = 5, 
        query_tags: Optional[List[str]] = None,
        project: Optional[str] = None,
        min_importance: float = 0.0
    ) -> List[Tuple[MemoryItemModel, float]]:
        """Multi-Factor Weighted Ranking Formula: 0.45 Semantic + 0.20 Importance + 0.20 Recency + 0.10 Project + 0.05 Confidence."""
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
        query_vec = self._text_to_vector(query_text)
        
        for r in rows:
            tags_list = r[2].split(",") if r[2] else []
            item = MemoryItemModel(
                item_id=r[0], content=r[1], tags=tags_list,
                importance=r[3], project=r[4], language=r[5],
                source=r[6], confidence=r[7], access_count=r[8],
                last_accessed=r[9], timestamp=r[10], embedding_version=r[11]
            )
            
            # 1. Semantic Cosine Similarity (Normalized 0.0 - 1.0)
            mem_vec = self._text_to_vector(item.content)
            semantic_score = self._cosine_similarity(query_vec, mem_vec)
            
            # 2. Importance Score (Normalized 0.0 - 1.0)
            importance_score = min(1.0, item.importance / 5.0)
            
            # 3. Recency Decay Score (24-hour half-life)
            age_hours = max(0.1, (now - item.timestamp) / 3600.0)
            recency_score = 1.0 / (1.0 + (age_hours / 24.0))
            
            # 4. Project Alignment Score
            project_score = 1.0 if (project and item.project and project.lower() == item.project.lower()) else 0.5
            
            # 5. Confidence Rating
            confidence_score = min(1.0, item.confidence)
            
            # Multi-Factor Weighted Scoring Formula
            score = (
                (0.45 * semantic_score) +
                (0.20 * importance_score) +
                (0.20 * recency_score) +
                (0.10 * project_score) +
                (0.05 * confidence_score)
            ) * 10.0  # Scale 0-10
            
            scored_items.append((item, score))
            
        scored_items.sort(key=lambda x: x[1], reverse=True)
        top_results = scored_items[:top_k]
        
        for item, _ in top_results:
            self._touch_access_metric(item.item_id)
            
        return top_results

    def query(self, tag: Optional[str] = None, project: Optional[str] = None, min_importance: float = 0.0) -> List[MemoryItemModel]:
        ranked_results = self.query_and_rank(query_tags=[tag] if tag else [], project=project, min_importance=min_importance)
        return [item for item, score in ranked_results]

    def query_and_rank(self, query_tags: List[str] = None, project: Optional[str] = None, min_importance: float = 0.0) -> List[Tuple[MemoryItemModel, float]]:
        return self.semantic_recall(query_text="", top_k=50, query_tags=query_tags, project=project, min_importance=min_importance)

    def _touch_access_metric(self, item_id: str) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE memories 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE item_id = ?
                """, (time.time(), item_id))
                conn.commit()
        except Exception as e:
            logger.debug(f"[MemoryManager] Error updating access metrics: {e}")

    def _text_to_vector(self, text: str) -> Dict[str, float]:
        words = re.findall(r'\w+', text.lower())
        vec: Dict[str, float] = {}
        for w in words:
            vec[w] = vec.get(w, 0.0) + 1.0
        return vec

    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum(vec1[x] * vec2[x] for x in intersection)
        
        sum1 = sum(v ** 2 for v in vec1.values())
        sum2 = sum(v ** 2 for v in vec2.values())
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        
        if not denominator:
            return 0.0
        return float(numerator) / denominator
