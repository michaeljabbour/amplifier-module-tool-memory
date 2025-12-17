"""
Memory storage using SQLite.

Provides persistent storage for memories with:
- Categories for organization
- Importance scoring
- Tags for flexible filtering
- Keyword search
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

MemoryCategory = Literal[
    "learning",        # Knowledge acquired (facts, concepts)
    "decision",        # Decisions made (architecture, design)
    "issue_solved",    # Problems and solutions
    "preference",      # User preferences
    "pattern",         # Recurring behaviors
    "recipe",          # Reusable workflows
    "coding_style",    # Code style preferences
    "tech_stack",      # Technology preferences
    "project_context", # Project-specific knowledge
    "communication",   # Communication preferences
    "general",         # General memories (default)
]

MEMORY_CATEGORIES = [
    "learning", "decision", "issue_solved", "preference", "pattern",
    "recipe", "coding_style", "tech_stack", "project_context", 
    "communication", "general"
]


@dataclass
class Memory:
    """A memory entry."""
    id: str
    content: str
    category: str
    importance: float
    tags: list[str]
    metadata: dict
    created_at: datetime
    accessed_count: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "importance": self.importance,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "accessed_count": self.accessed_count,
        }


class MemoryStore:
    """SQLite-based memory storage."""

    def __init__(self, db_path: Optional[str | Path] = None, max_memories: int = 1000):
        """
        Initialize the memory store.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.amplifier/memories.db
            max_memories: Maximum memories to store (oldest removed when exceeded)
        """
        if db_path is None:
            db_path = Path.home() / ".amplifier" / "memories.db"
        elif isinstance(db_path, str):
            db_path = Path(db_path)
            
        self.db_path = db_path
        self.max_memories = max_memories
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    importance REAL DEFAULT 0.5,
                    tags_json TEXT DEFAULT '[]',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    accessed_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance)")
            conn.commit()

    def add(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> Memory:
        """
        Add a new memory.

        Args:
            content: The memory content
            category: Category for organization
            importance: Importance score (0.0 to 1.0)
            tags: Optional tags for filtering
            metadata: Optional additional metadata

        Returns:
            The created Memory
        """
        memory_id = str(uuid.uuid4())
        created_at = datetime.now()
        tags = tags or []
        metadata = metadata or {}
        
        # Validate category
        if category not in MEMORY_CATEGORIES:
            category = "general"
        
        # Clamp importance
        importance = max(0.0, min(1.0, importance))
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO memories (id, content, category, importance, tags_json, metadata_json, created_at, accessed_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_id,
                content,
                category,
                importance,
                json.dumps(tags),
                json.dumps(metadata),
                created_at.isoformat(),
                0,
            ))
            conn.commit()
        
        # Enforce limit
        self._enforce_limit()
        
        logger.info(f"Added memory {memory_id}: [{category}] {content[:50]}...")
        
        return Memory(
            id=memory_id,
            content=content,
            category=category,
            importance=importance,
            tags=tags,
            metadata=metadata,
            created_at=created_at,
            accessed_count=0,
        )

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID and increment access count."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Check if memory exists
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                return None
            
            # Increment access count
            conn.execute("UPDATE memories SET accessed_count = accessed_count + 1 WHERE id = ?", (memory_id,))
            conn.commit()
            
            # Re-fetch to get updated count
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            return self._row_to_memory(row)

    def list_all(
        self,
        limit: Optional[int] = None,
        category: Optional[str] = None,
        min_importance: Optional[float] = None,
    ) -> list[Memory]:
        """
        List memories with optional filtering.

        Args:
            limit: Maximum number to return
            category: Filter by category
            min_importance: Filter by minimum importance

        Returns:
            List of memories
        """
        query = "SELECT * FROM memories WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if min_importance is not None:
            query += " AND importance >= ?"
            params.append(min_importance)
        
        query += " ORDER BY importance DESC, created_at DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_memory(row) for row in rows]

    def search(self, query: str, limit: int = 10) -> list[Memory]:
        """
        Search memories by keyword.

        Args:
            query: Search query (case-insensitive)
            limit: Maximum results

        Returns:
            List of matching memories sorted by relevance
        """
        search_terms = query.lower().split()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY importance DESC, created_at DESC"
            ).fetchall()
            
            results = []
            for row in rows:
                content_lower = row["content"].lower()
                tags = json.loads(row["tags_json"])
                tags_lower = " ".join(tags).lower()
                
                # Count matching terms
                matches = sum(1 for term in search_terms if term in content_lower or term in tags_lower)
                if matches > 0:
                    memory = self._row_to_memory(row)
                    score = matches * memory.importance
                    results.append((score, memory))
            
            # Sort by score
            results.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in results[:limit]]

    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        category: Optional[str] = None,
        importance: Optional[float] = None,
        tags: Optional[list[str]] = None,
    ) -> Optional[Memory]:
        """
        Update a memory.

        Args:
            memory_id: ID of memory to update
            content: New content
            category: New category
            importance: New importance
            tags: New tags

        Returns:
            Updated memory or None if not found
        """
        existing = self.get(memory_id)
        if not existing:
            return None
        
        updates = []
        params = []
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if category is not None and category in MEMORY_CATEGORIES:
            updates.append("category = ?")
            params.append(category)
        if importance is not None:
            updates.append("importance = ?")
            params.append(max(0.0, min(1.0, importance)))
        if tags is not None:
            updates.append("tags_json = ?")
            params.append(json.dumps(tags))
        
        if not updates:
            return existing
        
        params.append(memory_id)
        query = f"UPDATE memories SET {', '.join(updates)} WHERE id = ?"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(query, params)
            conn.commit()
        
        return self.get(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def count(self) -> int:
        """Get total memory count."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert database row to Memory."""
        return Memory(
            id=row["id"],
            content=row["content"],
            category=row["category"],
            importance=row["importance"],
            tags=json.loads(row["tags_json"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            accessed_count=row["accessed_count"],
        )

    def _enforce_limit(self):
        """Remove oldest/least accessed memories if over limit."""
        count = self.count()
        if count <= self.max_memories:
            return
        
        to_remove = count - self.max_memories
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                DELETE FROM memories WHERE id IN (
                    SELECT id FROM memories
                    ORDER BY accessed_count ASC, created_at ASC
                    LIMIT {to_remove}
                )
            """)
            conn.commit()
            logger.info(f"Removed {to_remove} old memories to stay under limit")
