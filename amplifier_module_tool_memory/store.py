"""
Memory storage using SQLite with FTS5 full-text search.

Provides persistent storage for memories/observations with:
- Rich schema (type, title, facts, narrative, concepts)
- Session and project tracking
- File references (read/modified)
- FTS5 full-text search
- Categories and importance scoring
- Tags for flexible filtering

Inspired by claude-mem's observation architecture.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Observation types (matching claude-mem)
ObservationType = Literal[
    "bugfix",     # Something was broken, now fixed
    "feature",    # New capability or functionality added
    "refactor",   # Code restructured, behavior unchanged
    "change",     # Generic modification (docs, config, misc)
    "discovery",  # Learning about existing system
    "decision",   # Architectural/design choice with rationale
]

OBSERVATION_TYPES = [
    "bugfix", "feature", "refactor", "change", "discovery", "decision"
]

# Concept types (knowledge categories from claude-mem)
ConceptType = Literal[
    "how-it-works",    # Understanding mechanisms
    "why-it-exists",   # Purpose or rationale
    "what-changed",    # Modifications made
    "problem-solution", # Issues and their fixes
    "gotcha",          # Traps or edge cases
    "pattern",         # Reusable approach
    "trade-off",       # Pros/cons of a decision
]

CONCEPT_TYPES = [
    "how-it-works", "why-it-exists", "what-changed", 
    "problem-solution", "gotcha", "pattern", "trade-off"
]

# Legacy category support (for backward compatibility)
MemoryCategory = Literal[
    "learning", "decision", "issue_solved", "preference", "pattern",
    "recipe", "coding_style", "tech_stack", "project_context", 
    "communication", "general",
]

MEMORY_CATEGORIES = [
    "learning", "decision", "issue_solved", "preference", "pattern",
    "recipe", "coding_style", "tech_stack", "project_context", 
    "communication", "general"
]


@dataclass
class Memory:
    """A memory/observation entry with rich metadata."""
    id: str
    
    # Core content (claude-mem style)
    type: str  # bugfix, feature, refactor, change, discovery, decision
    title: str  # Short title
    subtitle: str  # One sentence explanation
    content: str  # Full narrative (backward compat with old 'content' field)
    facts: list[str]  # Concise, self-contained statements
    
    # Knowledge classification
    concepts: list[str]  # how-it-works, problem-solution, etc.
    
    # File tracking
    files_read: list[str]
    files_modified: list[str]
    
    # Session/project context
    session_id: Optional[str]
    project: Optional[str]
    
    # Legacy fields (backward compatibility)
    category: str
    importance: float
    tags: list[str]
    metadata: dict
    
    # Timestamps and access
    created_at: datetime
    accessed_count: int
    
    # Token economics (claude-mem ROI tracking)
    discovery_tokens: int  # Tokens spent discovering this
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "subtitle": self.subtitle,
            "content": self.content,
            "facts": self.facts,
            "concepts": self.concepts,
            "files_read": self.files_read,
            "files_modified": self.files_modified,
            "session_id": self.session_id,
            "project": self.project,
            "category": self.category,
            "importance": self.importance,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "accessed_count": self.accessed_count,
            "discovery_tokens": self.discovery_tokens,
        }
    
    def to_index(self) -> dict:
        """Return index view (progressive disclosure layer 1)."""
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "subtitle": self.subtitle,
            "concepts": self.concepts,
            "created_at": self.created_at.isoformat(),
            "token_estimate": len(self.content) // 4,
        }


@dataclass
class SessionSummary:
    """Session progress summary (claude-mem style)."""
    id: str
    session_id: str
    project: Optional[str]
    
    # Summary fields
    request: str  # What user asked
    investigated: str  # What was explored
    learned: str  # Insights gained
    completed: str  # Work done
    next_steps: str  # Current trajectory
    notes: str  # Additional observations
    
    # File tracking
    files_read: list[str]
    files_edited: list[str]
    
    # Token economics
    discovery_tokens: int
    
    # Timestamp
    created_at: datetime
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "project": self.project,
            "request": self.request,
            "investigated": self.investigated,
            "learned": self.learned,
            "completed": self.completed,
            "next_steps": self.next_steps,
            "notes": self.notes,
            "files_read": self.files_read,
            "files_edited": self.files_edited,
            "discovery_tokens": self.discovery_tokens,
            "created_at": self.created_at.isoformat(),
        }


@dataclass  
class Session:
    """Active session tracking."""
    id: str
    session_id: str  # External session ID (from Claude/app)
    project: Optional[str]
    user_prompt: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    status: str  # active, completed, failed
    prompt_count: int
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "project": self.project,
            "user_prompt": self.user_prompt,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "prompt_count": self.prompt_count,
        }


class MemoryStore:
    """SQLite-based memory storage with FTS5 search."""

    SCHEMA_VERSION = 2  # Bump when schema changes

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
            db_path = Path(db_path).expanduser()
            
        self.db_path = db_path
        self.max_memories = max_memories
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
        self._run_migrations()

    def _init_db(self):
        """Initialize the SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Schema version tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                )
            """)
            
            # Main memories table with rich schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    
                    -- Core content (claude-mem style)
                    type TEXT NOT NULL DEFAULT 'change',
                    title TEXT NOT NULL DEFAULT '',
                    subtitle TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    facts_json TEXT DEFAULT '[]',
                    
                    -- Knowledge classification
                    concepts_json TEXT DEFAULT '[]',
                    
                    -- File tracking
                    files_read_json TEXT DEFAULT '[]',
                    files_modified_json TEXT DEFAULT '[]',
                    
                    -- Session/project context
                    session_id TEXT,
                    project TEXT,
                    
                    -- Legacy fields
                    category TEXT NOT NULL DEFAULT 'general',
                    importance REAL DEFAULT 0.5,
                    tags_json TEXT DEFAULT '[]',
                    metadata_json TEXT DEFAULT '{}',
                    
                    -- Timestamps and access
                    created_at TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    accessed_count INTEGER DEFAULT 0,
                    
                    -- Token economics
                    discovery_tokens INTEGER DEFAULT 0
                )
            """)
            
            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    session_id TEXT UNIQUE NOT NULL,
                    project TEXT,
                    user_prompt TEXT,
                    started_at TEXT NOT NULL,
                    started_at_epoch INTEGER NOT NULL,
                    completed_at TEXT,
                    completed_at_epoch INTEGER,
                    status TEXT NOT NULL DEFAULT 'active',
                    prompt_count INTEGER DEFAULT 0
                )
            """)
            
            # Session summaries table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_summaries (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    project TEXT,
                    request TEXT,
                    investigated TEXT,
                    learned TEXT,
                    completed TEXT,
                    next_steps TEXT,
                    notes TEXT,
                    files_read_json TEXT DEFAULT '[]',
                    files_edited_json TEXT DEFAULT '[]',
                    discovery_tokens INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            
            # User prompts table (for searchable prompt history)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_prompts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    prompt_number INTEGER NOT NULL,
                    prompt_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            
            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at_epoch DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project)")
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_session ON session_summaries(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_project ON session_summaries(project)")
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prompts_session ON user_prompts(session_id)")
            
            conn.commit()

    def _run_migrations(self):
        """Run database migrations."""
        with sqlite3.connect(self.db_path) as conn:
            # Get current version
            try:
                row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
                current_version = row[0] if row and row[0] else 0
            except sqlite3.OperationalError:
                current_version = 0
            
            if current_version < 1:
                self._migrate_v1(conn)
            
            if current_version < 2:
                self._migrate_v2_fts5(conn)

    def _migrate_v1(self, conn: sqlite3.Connection):
        """Migration v1: Add new columns to existing tables."""
        logger.info("Running migration v1: Adding new columns")
        
        # Check if columns exist and add if missing
        cursor = conn.execute("PRAGMA table_info(memories)")
        columns = {row[1] for row in cursor.fetchall()}
        
        new_columns = [
            ("type", "TEXT NOT NULL DEFAULT 'change'"),
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("subtitle", "TEXT NOT NULL DEFAULT ''"),
            ("facts_json", "TEXT DEFAULT '[]'"),
            ("concepts_json", "TEXT DEFAULT '[]'"),
            ("files_read_json", "TEXT DEFAULT '[]'"),
            ("files_modified_json", "TEXT DEFAULT '[]'"),
            ("session_id", "TEXT"),
            ("project", "TEXT"),
            ("created_at_epoch", "INTEGER"),
            ("discovery_tokens", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_def in new_columns:
            if col_name not in columns:
                try:
                    conn.execute(f"ALTER TABLE memories ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Added column: {col_name}")
                except sqlite3.OperationalError as e:
                    logger.debug(f"Column {col_name} might already exist: {e}")
        
        # Backfill created_at_epoch from created_at
        conn.execute("""
            UPDATE memories 
            SET created_at_epoch = CAST(strftime('%s', created_at) AS INTEGER) * 1000
            WHERE created_at_epoch IS NULL
        """)
        
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (1)")
        conn.commit()
        logger.info("Migration v1 complete")

    def _migrate_v2_fts5(self, conn: sqlite3.Connection):
        """Migration v2: Add FTS5 full-text search."""
        logger.info("Running migration v2: Adding FTS5 search")
        
        # Create FTS5 virtual table for memories
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title,
                subtitle,
                content,
                facts_json,
                concepts_json,
                content='memories',
                content_rowid='rowid'
            )
        """)
        
        # Populate FTS table with existing data
        conn.execute("""
            INSERT OR IGNORE INTO memories_fts(rowid, title, subtitle, content, facts_json, concepts_json)
            SELECT rowid, title, subtitle, content, facts_json, concepts_json
            FROM memories
        """)
        
        # Triggers to keep FTS in sync
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, title, subtitle, content, facts_json, concepts_json)
                VALUES (new.rowid, new.title, new.subtitle, new.content, new.facts_json, new.concepts_json);
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, subtitle, content, facts_json, concepts_json)
                VALUES('delete', old.rowid, old.title, old.subtitle, old.content, old.facts_json, old.concepts_json);
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, subtitle, content, facts_json, concepts_json)
                VALUES('delete', old.rowid, old.title, old.subtitle, old.content, old.facts_json, old.concepts_json);
                INSERT INTO memories_fts(rowid, title, subtitle, content, facts_json, concepts_json)
                VALUES (new.rowid, new.title, new.subtitle, new.content, new.facts_json, new.concepts_json);
            END
        """)
        
        # FTS5 for session summaries
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS summaries_fts USING fts5(
                request,
                investigated,
                learned,
                completed,
                next_steps,
                notes,
                content='session_summaries',
                content_rowid='rowid'
            )
        """)
        
        conn.execute("""
            INSERT OR IGNORE INTO summaries_fts(rowid, request, investigated, learned, completed, next_steps, notes)
            SELECT rowid, request, investigated, learned, completed, next_steps, notes
            FROM session_summaries
        """)
        
        # Triggers for summaries
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS summaries_ai AFTER INSERT ON session_summaries BEGIN
                INSERT INTO summaries_fts(rowid, request, investigated, learned, completed, next_steps, notes)
                VALUES (new.rowid, new.request, new.investigated, new.learned, new.completed, new.next_steps, new.notes);
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS summaries_ad AFTER DELETE ON session_summaries BEGIN
                INSERT INTO summaries_fts(summaries_fts, rowid, request, investigated, learned, completed, next_steps, notes)
                VALUES('delete', old.rowid, old.request, old.investigated, old.learned, old.completed, old.next_steps, old.notes);
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS summaries_au AFTER UPDATE ON session_summaries BEGIN
                INSERT INTO summaries_fts(summaries_fts, rowid, request, investigated, learned, completed, next_steps, notes)
                VALUES('delete', old.rowid, old.request, old.investigated, old.learned, old.completed, old.next_steps, old.notes);
                INSERT INTO summaries_fts(rowid, request, investigated, learned, completed, next_steps, notes)
                VALUES (new.rowid, new.request, new.investigated, new.learned, new.completed, new.next_steps, new.notes);
            END
        """)
        
        # FTS5 for user prompts
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts USING fts5(
                prompt_text,
                content='user_prompts',
                content_rowid='rowid'
            )
        """)
        
        conn.execute("""
            INSERT OR IGNORE INTO prompts_fts(rowid, prompt_text)
            SELECT rowid, prompt_text FROM user_prompts
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS prompts_ai AFTER INSERT ON user_prompts BEGIN
                INSERT INTO prompts_fts(rowid, prompt_text) VALUES (new.rowid, new.prompt_text);
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS prompts_ad AFTER DELETE ON user_prompts BEGIN
                INSERT INTO prompts_fts(prompts_fts, rowid, prompt_text) VALUES('delete', old.rowid, old.prompt_text);
            END
        """)
        
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (2)")
        conn.commit()
        logger.info("Migration v2 (FTS5) complete")

    # -------------------------------------------------------------------------
    # Memory CRUD Operations
    # -------------------------------------------------------------------------
    
    def add(
        self,
        content: str,
        type: str = "change",
        title: str = "",
        subtitle: str = "",
        facts: Optional[list[str]] = None,
        concepts: Optional[list[str]] = None,
        files_read: Optional[list[str]] = None,
        files_modified: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        project: Optional[str] = None,
        category: str = "general",
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
        discovery_tokens: int = 0,
    ) -> Memory:
        """
        Add a new memory/observation.

        Args:
            content: The memory content (narrative)
            type: Observation type (bugfix, feature, refactor, change, discovery, decision)
            title: Short title
            subtitle: One sentence explanation
            facts: List of concise statements
            concepts: Knowledge categories (how-it-works, problem-solution, etc.)
            files_read: Files that were read
            files_modified: Files that were modified
            session_id: Session identifier
            project: Project name/path
            category: Legacy category for organization
            importance: Importance score (0.0 to 1.0)
            tags: Optional tags for filtering
            metadata: Optional additional metadata
            discovery_tokens: Tokens spent discovering this

        Returns:
            The created Memory
        """
        memory_id = str(uuid.uuid4())
        created_at = datetime.now()
        created_at_epoch = int(created_at.timestamp() * 1000)
        
        facts = facts or []
        concepts = concepts or []
        files_read = files_read or []
        files_modified = files_modified or []
        tags = tags or []
        metadata = metadata or {}
        
        # Validate type
        if type not in OBSERVATION_TYPES:
            type = "change"
        
        # Validate category
        if category not in MEMORY_CATEGORIES:
            category = "general"
        
        # Clamp importance
        importance = max(0.0, min(1.0, importance))
        
        # Auto-generate title if not provided
        if not title and content:
            title = content[:50] + ("..." if len(content) > 50 else "")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO memories (
                    id, type, title, subtitle, content, facts_json, concepts_json,
                    files_read_json, files_modified_json, session_id, project,
                    category, importance, tags_json, metadata_json,
                    created_at, created_at_epoch, accessed_count, discovery_tokens
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_id, type, title, subtitle, content,
                json.dumps(facts), json.dumps(concepts),
                json.dumps(files_read), json.dumps(files_modified),
                session_id, project,
                category, importance, json.dumps(tags), json.dumps(metadata),
                created_at.isoformat(), created_at_epoch, 0, discovery_tokens,
            ))
            conn.commit()
        
        # Enforce limit
        self._enforce_limit()
        
        logger.info(f"Added memory {memory_id}: [{type}] {title}")
        
        return Memory(
            id=memory_id,
            type=type,
            title=title,
            subtitle=subtitle,
            content=content,
            facts=facts,
            concepts=concepts,
            files_read=files_read,
            files_modified=files_modified,
            session_id=session_id,
            project=project,
            category=category,
            importance=importance,
            tags=tags,
            metadata=metadata,
            created_at=created_at,
            accessed_count=0,
            discovery_tokens=discovery_tokens,
        )

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID and increment access count."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                return None
            
            # Increment access count
            conn.execute("UPDATE memories SET accessed_count = accessed_count + 1 WHERE id = ?", (memory_id,))
            conn.commit()
            
            return self._row_to_memory(row)

    def list_all(
        self,
        limit: Optional[int] = None,
        type: Optional[str] = None,
        category: Optional[str] = None,
        concepts: Optional[list[str]] = None,
        project: Optional[str] = None,
        session_id: Optional[str] = None,
        min_importance: Optional[float] = None,
        since_epoch: Optional[int] = None,
    ) -> list[Memory]:
        """
        List memories with optional filtering.

        Args:
            limit: Maximum number to return
            type: Filter by observation type
            category: Filter by category
            concepts: Filter by concepts (any match)
            project: Filter by project
            session_id: Filter by session
            min_importance: Filter by minimum importance
            since_epoch: Filter by creation time (epoch ms)

        Returns:
            List of memories
        """
        query = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []
        
        if type:
            query += " AND type = ?"
            params.append(type)
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if project:
            query += " AND project = ?"
            params.append(project)
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        
        if min_importance is not None:
            query += " AND importance >= ?"
            params.append(min_importance)
        
        if since_epoch is not None:
            query += " AND created_at_epoch >= ?"
            params.append(since_epoch)
        
        if concepts:
            # Match any of the provided concepts
            concept_conditions = []
            for concept in concepts:
                concept_conditions.append("concepts_json LIKE ?")
                params.append(f'%"{concept}"%')
            query += f" AND ({' OR '.join(concept_conditions)})"
        
        query += " ORDER BY importance DESC, created_at_epoch DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_memory(row) for row in rows]

    def list_index(
        self,
        limit: int = 50,
        project: Optional[str] = None,
        since_epoch: Optional[int] = None,
    ) -> list[dict]:
        """
        Get index view of memories (progressive disclosure layer 1).
        Returns minimal info with token estimates for cost-aware retrieval.
        """
        memories = self.list_all(limit=limit, project=project, since_epoch=since_epoch)
        return [m.to_index() for m in memories]

    def search(
        self, 
        query: str, 
        limit: int = 10,
        type: Optional[str] = None,
        project: Optional[str] = None,
    ) -> list[Memory]:
        """
        Full-text search using FTS5.

        Args:
            query: Search query
            limit: Maximum results
            type: Optional type filter
            project: Optional project filter

        Returns:
            List of matching memories sorted by relevance
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Use FTS5 for search
            fts_query = f"""
                SELECT m.*, fts.rank
                FROM memories m
                JOIN memories_fts fts ON m.rowid = fts.rowid
                WHERE memories_fts MATCH ?
            """
            params: list[Any] = [query]
            
            if type:
                fts_query += " AND m.type = ?"
                params.append(type)
            
            if project:
                fts_query += " AND m.project = ?"
                params.append(project)
            
            fts_query += " ORDER BY fts.rank LIMIT ?"
            params.append(limit)
            
            try:
                rows = conn.execute(fts_query, params).fetchall()
                return [self._row_to_memory(row) for row in rows]
            except sqlite3.OperationalError as e:
                # Fallback to LIKE search if FTS fails
                logger.warning(f"FTS5 search failed, falling back to LIKE: {e}")
                return self._search_fallback(query, limit, type, project)

    def _search_fallback(
        self, 
        query: str, 
        limit: int,
        type: Optional[str] = None,
        project: Optional[str] = None,
    ) -> list[Memory]:
        """Fallback search using LIKE (for when FTS5 isn't available)."""
        search_terms = query.lower().split()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            base_query = "SELECT * FROM memories WHERE 1=1"
            params: list[Any] = []
            
            if type:
                base_query += " AND type = ?"
                params.append(type)
            
            if project:
                base_query += " AND project = ?"
                params.append(project)
            
            base_query += " ORDER BY importance DESC, created_at_epoch DESC"
            
            rows = conn.execute(base_query, params).fetchall()
            
            results = []
            for row in rows:
                searchable = (
                    (row["title"] or "").lower() + " " +
                    (row["subtitle"] or "").lower() + " " +
                    (row["content"] or "").lower() + " " +
                    (row["facts_json"] or "").lower() + " " +
                    (row["tags_json"] or "").lower()
                )
                
                matches = sum(1 for term in search_terms if term in searchable)
                if matches > 0:
                    memory = self._row_to_memory(row)
                    score = matches * memory.importance
                    results.append((score, memory))
            
            results.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in results[:limit]]

    def search_by_file(self, file_path: str, limit: int = 10) -> list[Memory]:
        """Search memories by file path (read or modified)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM memories 
                WHERE files_read_json LIKE ? OR files_modified_json LIKE ?
                ORDER BY created_at_epoch DESC
                LIMIT ?
            """, (f'%"{file_path}"%', f'%"{file_path}"%', limit)).fetchall()
            return [self._row_to_memory(row) for row in rows]

    def search_by_concept(self, concept: str, limit: int = 10) -> list[Memory]:
        """Search memories by concept tag."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM memories 
                WHERE concepts_json LIKE ?
                ORDER BY importance DESC, created_at_epoch DESC
                LIMIT ?
            """, (f'%"{concept}"%', limit)).fetchall()
            return [self._row_to_memory(row) for row in rows]

    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        type: Optional[str] = None,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        facts: Optional[list[str]] = None,
        concepts: Optional[list[str]] = None,
        category: Optional[str] = None,
        importance: Optional[float] = None,
        tags: Optional[list[str]] = None,
    ) -> Optional[Memory]:
        """Update a memory."""
        existing = self.get(memory_id)
        if not existing:
            return None
        
        updates = []
        params: list[Any] = []
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if type is not None and type in OBSERVATION_TYPES:
            updates.append("type = ?")
            params.append(type)
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if subtitle is not None:
            updates.append("subtitle = ?")
            params.append(subtitle)
        if facts is not None:
            updates.append("facts_json = ?")
            params.append(json.dumps(facts))
        if concepts is not None:
            updates.append("concepts_json = ?")
            params.append(json.dumps(concepts))
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

    # -------------------------------------------------------------------------
    # Session Operations
    # -------------------------------------------------------------------------
    
    def create_session(
        self,
        session_id: str,
        project: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> Session:
        """Create or get a session."""
        now = datetime.now()
        internal_id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Check if session exists
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            
            if row:
                # Update existing session
                conn.execute("""
                    UPDATE sessions SET prompt_count = prompt_count + 1, user_prompt = ?
                    WHERE session_id = ?
                """, (user_prompt, session_id))
                conn.commit()
                
                row = conn.execute(
                    "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
                ).fetchone()
                return self._row_to_session(row)
            
            # Create new session
            conn.execute("""
                INSERT INTO sessions (id, session_id, project, user_prompt, started_at, started_at_epoch, status, prompt_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                internal_id, session_id, project, user_prompt,
                now.isoformat(), int(now.timestamp() * 1000), "active", 1
            ))
            conn.commit()
        
        return Session(
            id=internal_id,
            session_id=session_id,
            project=project,
            user_prompt=user_prompt,
            started_at=now,
            completed_at=None,
            status="active",
            prompt_count=1,
        )

    def complete_session(self, session_id: str, status: str = "completed") -> bool:
        """Mark a session as completed."""
        now = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE sessions 
                SET status = ?, completed_at = ?, completed_at_epoch = ?
                WHERE session_id = ?
            """, (status, now.isoformat(), int(now.timestamp() * 1000), session_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return self._row_to_session(row) if row else None

    def get_recent_sessions(self, limit: int = 10, project: Optional[str] = None) -> list[Session]:
        """Get recent sessions."""
        query = "SELECT * FROM sessions WHERE 1=1"
        params: list[Any] = []
        
        if project:
            query += " AND project = ?"
            params.append(project)
        
        query += " ORDER BY started_at_epoch DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_session(row) for row in rows]

    # -------------------------------------------------------------------------
    # User Prompt Operations  
    # -------------------------------------------------------------------------
    
    def add_user_prompt(
        self,
        session_id: str,
        prompt_text: str,
        prompt_number: int,
    ) -> dict:
        """Record a user prompt."""
        prompt_id = str(uuid.uuid4())
        now = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO user_prompts (id, session_id, prompt_number, prompt_text, created_at, created_at_epoch)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                prompt_id, session_id, prompt_number, prompt_text,
                now.isoformat(), int(now.timestamp() * 1000)
            ))
            conn.commit()
        
        return {"id": prompt_id, "session_id": session_id, "prompt_number": prompt_number}

    def search_prompts(self, query: str, limit: int = 10) -> list[dict]:
        """Search user prompts using FTS5."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            try:
                rows = conn.execute("""
                    SELECT p.*, fts.rank
                    FROM user_prompts p
                    JOIN prompts_fts fts ON p.rowid = fts.rowid
                    WHERE prompts_fts MATCH ?
                    ORDER BY fts.rank
                    LIMIT ?
                """, (query, limit)).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute("""
                    SELECT * FROM user_prompts
                    WHERE prompt_text LIKE ?
                    ORDER BY created_at_epoch DESC
                    LIMIT ?
                """, (f"%{query}%", limit)).fetchall()
            
            return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # Session Summary Operations
    # -------------------------------------------------------------------------
    
    def add_summary(
        self,
        session_id: str,
        request: str = "",
        investigated: str = "",
        learned: str = "",
        completed: str = "",
        next_steps: str = "",
        notes: str = "",
        files_read: Optional[list[str]] = None,
        files_edited: Optional[list[str]] = None,
        project: Optional[str] = None,
        discovery_tokens: int = 0,
    ) -> SessionSummary:
        """Add a session summary."""
        summary_id = str(uuid.uuid4())
        now = datetime.now()
        
        files_read = files_read or []
        files_edited = files_edited or []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO session_summaries (
                    id, session_id, project, request, investigated, learned,
                    completed, next_steps, notes, files_read_json, files_edited_json,
                    discovery_tokens, created_at, created_at_epoch
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                summary_id, session_id, project, request, investigated, learned,
                completed, next_steps, notes, json.dumps(files_read), json.dumps(files_edited),
                discovery_tokens, now.isoformat(), int(now.timestamp() * 1000)
            ))
            conn.commit()
        
        return SessionSummary(
            id=summary_id,
            session_id=session_id,
            project=project,
            request=request,
            investigated=investigated,
            learned=learned,
            completed=completed,
            next_steps=next_steps,
            notes=notes,
            files_read=files_read,
            files_edited=files_edited,
            discovery_tokens=discovery_tokens,
            created_at=now,
        )

    def get_summaries(
        self,
        session_id: Optional[str] = None,
        project: Optional[str] = None,
        limit: int = 10,
    ) -> list[SessionSummary]:
        """Get session summaries."""
        query = "SELECT * FROM session_summaries WHERE 1=1"
        params: list[Any] = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        
        if project:
            query += " AND project = ?"
            params.append(project)
        
        query += " ORDER BY created_at_epoch DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_summary(row) for row in rows]

    def search_summaries(self, query: str, limit: int = 10) -> list[SessionSummary]:
        """Search session summaries using FTS5."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            try:
                rows = conn.execute("""
                    SELECT s.*, fts.rank
                    FROM session_summaries s
                    JOIN summaries_fts fts ON s.rowid = fts.rowid
                    WHERE summaries_fts MATCH ?
                    ORDER BY fts.rank
                    LIMIT ?
                """, (query, limit)).fetchall()
                return [self._row_to_summary(row) for row in rows]
            except sqlite3.OperationalError:
                # Fallback to LIKE search
                rows = conn.execute("""
                    SELECT * FROM session_summaries
                    WHERE request LIKE ? OR investigated LIKE ? OR learned LIKE ? 
                          OR completed LIKE ? OR next_steps LIKE ?
                    ORDER BY created_at_epoch DESC
                    LIMIT ?
                """, (f"%{query}%",) * 5 + (limit,)).fetchall()
                return [self._row_to_summary(row) for row in rows]

    # -------------------------------------------------------------------------
    # Context Generation (for injection at session start)
    # -------------------------------------------------------------------------
    
    def get_context_for_session(
        self,
        project: Optional[str] = None,
        limit: int = 50,
        include_summaries: bool = True,
        days: int = 90,
    ) -> dict:
        """
        Get context for injection at session start (progressive disclosure).
        
        Returns:
            Dict with 'observations' (index view) and optionally 'last_summary'
        """
        since_epoch = int((datetime.now().timestamp() - days * 86400) * 1000)
        
        # Get observation index
        observations = self.list_index(limit=limit, project=project, since_epoch=since_epoch)
        
        result = {
            "observations": observations,
            "observation_count": len(observations),
        }
        
        # Get last summary
        if include_summaries:
            summaries = self.get_summaries(project=project, limit=1)
            if summaries:
                result["last_summary"] = summaries[0].to_dict()
        
        return result

    def get_timeline(
        self,
        center_epoch: Optional[int] = None,
        window_hours: int = 24,
        project: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """
        Get a timeline of context around a specific point in time.
        
        Args:
            center_epoch: Center point in epoch ms (default: now)
            window_hours: Hours before and after center
            project: Optional project filter
            limit: Max items to return
            
        Returns:
            Dict with observations and summaries in timeline order
        """
        if center_epoch is None:
            center_epoch = int(datetime.now().timestamp() * 1000)
        
        window_ms = window_hours * 3600 * 1000
        start_epoch = center_epoch - window_ms
        end_epoch = center_epoch + window_ms
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get observations in window
            obs_query = """
                SELECT * FROM memories 
                WHERE created_at_epoch BETWEEN ? AND ?
            """
            obs_params: list[Any] = [start_epoch, end_epoch]
            
            if project:
                obs_query += " AND project = ?"
                obs_params.append(project)
            
            obs_query += " ORDER BY created_at_epoch DESC LIMIT ?"
            obs_params.append(limit)
            
            obs_rows = conn.execute(obs_query, obs_params).fetchall()
            
            # Get summaries in window
            sum_query = """
                SELECT * FROM session_summaries
                WHERE created_at_epoch BETWEEN ? AND ?
            """
            sum_params: list[Any] = [start_epoch, end_epoch]
            
            if project:
                sum_query += " AND project = ?"
                sum_params.append(project)
            
            sum_query += " ORDER BY created_at_epoch DESC LIMIT ?"
            sum_params.append(limit)
            
            sum_rows = conn.execute(sum_query, sum_params).fetchall()
        
        return {
            "center_epoch": center_epoch,
            "window_hours": window_hours,
            "observations": [self._row_to_memory(r).to_dict() for r in obs_rows],
            "summaries": [self._row_to_summary(r).to_dict() for r in sum_rows],
        }

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------
    
    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert database row to Memory."""
        return Memory(
            id=row["id"],
            type=row["type"] if "type" in row.keys() else "change",
            title=row["title"] if "title" in row.keys() else "",
            subtitle=row["subtitle"] if "subtitle" in row.keys() else "",
            content=row["content"],
            facts=json.loads(row["facts_json"]) if "facts_json" in row.keys() and row["facts_json"] else [],
            concepts=json.loads(row["concepts_json"]) if "concepts_json" in row.keys() and row["concepts_json"] else [],
            files_read=json.loads(row["files_read_json"]) if "files_read_json" in row.keys() and row["files_read_json"] else [],
            files_modified=json.loads(row["files_modified_json"]) if "files_modified_json" in row.keys() and row["files_modified_json"] else [],
            session_id=row["session_id"] if "session_id" in row.keys() else None,
            project=row["project"] if "project" in row.keys() else None,
            category=row["category"],
            importance=row["importance"],
            tags=json.loads(row["tags_json"]) if row["tags_json"] else [],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            accessed_count=row["accessed_count"],
            discovery_tokens=row["discovery_tokens"] if "discovery_tokens" in row.keys() else 0,
        )

    def _row_to_session(self, row: sqlite3.Row) -> Session:
        """Convert database row to Session."""
        return Session(
            id=row["id"],
            session_id=row["session_id"],
            project=row["project"],
            user_prompt=row["user_prompt"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            status=row["status"],
            prompt_count=row["prompt_count"],
        )

    def _row_to_summary(self, row: sqlite3.Row) -> SessionSummary:
        """Convert database row to SessionSummary."""
        return SessionSummary(
            id=row["id"],
            session_id=row["session_id"],
            project=row["project"],
            request=row["request"] or "",
            investigated=row["investigated"] or "",
            learned=row["learned"] or "",
            completed=row["completed"] or "",
            next_steps=row["next_steps"] or "",
            notes=row["notes"] or "",
            files_read=json.loads(row["files_read_json"]) if row["files_read_json"] else [],
            files_edited=json.loads(row["files_edited_json"]) if row["files_edited_json"] else [],
            discovery_tokens=row["discovery_tokens"] or 0,
            created_at=datetime.fromisoformat(row["created_at"]),
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
                    ORDER BY accessed_count ASC, created_at_epoch ASC
                    LIMIT {to_remove}
                )
            """)
            conn.commit()
            logger.info(f"Removed {to_remove} old memories to stay under limit")
