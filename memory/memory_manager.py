import sqlite3
import os
import math
import time
import re
from typing import List, Optional, Tuple, Any, Dict, Set
from memory.schema import MemoryItemModel, EpisodicMemoryItemModel, ProceduralMemoryItemModel
from observability.logger import logger

class MemoryManager:
    """Production Semantic, Episodic, and Procedural Memory Controller with real embedding vectorizer and rolling summarization."""

    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        self._embedding_model = None
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS procedural_memories (
                    procedure_id TEXT PRIMARY KEY,
                    user_goal TEXT NOT NULL,
                    capabilities_used TEXT NOT NULL,
                    successful_plan_json TEXT NOT NULL,
                    execution_count INTEGER NOT NULL,
                    success_rate REAL NOT NULL,
                    avg_latency_sec REAL NOT NULL,
                    last_executed REAL NOT NULL
                )
            """)

            cursor.execute("PRAGMA table_info(memories)")
            existing_cols = {col[1] for col in cursor.fetchall()}
            required_cols = {
                "project": "TEXT", "language": "TEXT", "source": "TEXT",
                "confidence": "REAL", "access_count": "INTEGER",
                "last_accessed": "REAL", "embedding_version": "TEXT"
            }
            # Backfill defaults: ALTER TABLE ADD COLUMN leaves NULL, but the
            # MemoryItemModel fields are non-Optional and would fail validation.
            col_defaults = {
                "project": "''", "language": "'en'", "source": "''",
                "confidence": "1.0", "access_count": "0",
                "last_accessed": "0.0", "embedding_version": "'v1'"
            }
            for col_name, col_type in required_cols.items():
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE memories ADD COLUMN {col_name} {col_type}")
                cursor.execute(
                    f"UPDATE memories SET {col_name} = {col_defaults[col_name]} WHERE {col_name} IS NULL"
                )

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

    def store_episodic(self, item: EpisodicMemoryItemModel) -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO episodic_memories
                (event_id, session_id, correlation_id, event_type, summary, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item.event_id, item.session_id, item.correlation_id,
                item.event_type, item.summary, item.details, item.timestamp
            ))
            conn.commit()
        logger.info(f"[MemoryManager] Stored episodic event '{item.event_id}' for session '{item.session_id}'")
        return item.event_id

    def get_session_episodes(self, session_id: str, limit: Optional[int] = 50) -> List[EpisodicMemoryItemModel]:
        sql = """
            SELECT event_id, session_id, correlation_id, event_type, summary, details, timestamp
            FROM episodic_memories WHERE session_id = ? ORDER BY timestamp ASC
        """
        params: List[Any] = [session_id]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            rows = cursor.execute(sql, params).fetchall()
        return [
            EpisodicMemoryItemModel(
                event_id=r[0], session_id=r[1], correlation_id=r[2],
                event_type=r[3], summary=r[4], details=r[5], timestamp=r[6]
            ) for r in rows
        ]

    def store_procedural(self, item: ProceduralMemoryItemModel) -> str:
        caps_str = ",".join(item.capabilities_used)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO procedural_memories
                (procedure_id, user_goal, capabilities_used, successful_plan_json, execution_count, success_rate, avg_latency_sec, last_executed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.procedure_id, item.user_goal, caps_str, item.successful_plan_json,
                item.execution_count, item.success_rate, item.avg_latency_sec, item.last_executed
            ))
            conn.commit()
        logger.info(f"[MemoryManager] Stored procedural memory sequence for goal '{item.user_goal}'")
        return item.procedure_id

    def recall_procedural(self, user_goal: str) -> Optional[ProceduralMemoryItemModel]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            rows = cursor.execute("""
                SELECT procedure_id, user_goal, capabilities_used, successful_plan_json, execution_count, success_rate, avg_latency_sec, last_executed
                FROM procedural_memories WHERE LOWER(user_goal) = LOWER(?) ORDER BY success_rate DESC, execution_count DESC LIMIT 1
            """, (user_goal,)).fetchall()

        if not rows:
            return None
        r = rows[0]
        caps = r[2].split(",") if r[2] else []
        return ProceduralMemoryItemModel(
            procedure_id=r[0], user_goal=r[1], capabilities_used=caps,
            successful_plan_json=r[3], execution_count=r[4], success_rate=r[5],
            avg_latency_sec=r[6], last_executed=r[7]
        )

    def summarize_session_to_semantic(self, session_id: str) -> Optional[str]:
        """Rolling Long-Term Summarization: Compress session episodic events into a semantic memory fact."""
        # No limit: the default cap silently dropped the most recent episodes,
        # which are exactly the ones a summary needs.
        episodes = self.get_session_episodes(session_id, limit=None)
        if not episodes:
            return None

        summaries = [e.summary for e in episodes]
        compressed_text = f"Session '{session_id}' Summary: " + "; ".join(summaries)
        semantic_item = MemoryItemModel(
            # Deterministic id so re-summarizing replaces the row instead of
            # accumulating divergent copies of the same session.
            item_id=f"summary_{session_id}",
            content=compressed_text,
            tags=["session_summary", session_id],
            importance=3.0,
            source="rolling_summary"
        )
        return self.store(semantic_item)

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
        wanted_tags = {t.lower() for t in query_tags if t}

        for r in rows:
            tags_list = r[2].split(",") if r[2] else []
            item = MemoryItemModel(
                item_id=r[0], content=r[1], tags=tags_list,
                importance=r[3] if r[3] is not None else 1.0,
                project=r[4] or "", language=r[5] or "en",
                source=r[6] or "",
                confidence=r[7] if r[7] is not None else 1.0,
                access_count=r[8] or 0,
                last_accessed=r[9] or 0.0,
                timestamp=r[10] if r[10] is not None else 0.0,
                embedding_version=r[11] or "v1"
            )

            # Tag filter: when tags are requested, an item must carry at least one.
            if wanted_tags and not wanted_tags & {t.strip().lower() for t in item.tags}:
                continue

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
        """Local Sentence-Transformers vectorizer with lightweight frequency fallback."""
        if not text:
            return {}
        try:
            if self._embedding_model is None:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            emb = self._embedding_model.encode(text).tolist()
            return {str(idx): float(val) for idx, val in enumerate(emb)}
        except Exception:
            # Word-frequency vector fallback if sentence-transformers is missing
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
