"""
Memory tools for AI agents.

Each tool follows the Amplifier Tool protocol:
- name: Tool identifier
- description: Human-readable description
- input_schema: JSON Schema for input validation
- execute(input): Async method that returns ToolResult

Enhanced with claude-mem inspired capabilities:
- Rich observation schema (type, title, facts, concepts)
- Session tracking and summaries
- File-based search
- Progressive disclosure (index vs full)
"""

from typing import Any
import logging

from amplifier_core import ToolResult

from .store import (
    MemoryStore, 
    MEMORY_CATEGORIES, 
    OBSERVATION_TYPES,
    CONCEPT_TYPES,
)

logger = logging.getLogger(__name__)


class AddMemoryTool:
    """Tool to add a new memory/observation with rich metadata."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "add_memory"
    
    @property
    def description(self) -> str:
        return (
            "Store a new memory/observation with rich metadata. Use this when learning something important "
            "that should be remembered across sessions. Supports structured observations with type, title, "
            "facts, concepts, and file tracking."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The full narrative/content of the memory"
                },
                "type": {
                    "type": "string",
                    "enum": OBSERVATION_TYPES,
                    "description": "Observation type: bugfix, feature, refactor, change, discovery, decision",
                    "default": "change"
                },
                "title": {
                    "type": "string",
                    "description": "Short title (auto-generated if not provided)"
                },
                "subtitle": {
                    "type": "string",
                    "description": "One sentence explanation"
                },
                "facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of concise, self-contained facts"
                },
                "concepts": {
                    "type": "array",
                    "items": {"type": "string", "enum": CONCEPT_TYPES},
                    "description": "Knowledge categories: how-it-works, why-it-exists, problem-solution, gotcha, pattern, trade-off"
                },
                "files_read": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files that were read during this observation"
                },
                "files_modified": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files that were modified"
                },
                "category": {
                    "type": "string",
                    "enum": MEMORY_CATEGORIES,
                    "description": "Legacy category for organization",
                    "default": "general"
                },
                "importance": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Importance score (0.0-1.0, higher = more important)",
                    "default": 0.5
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for filtering"
                },
                "session_id": {
                    "type": "string",
                    "description": "Session identifier for grouping"
                },
                "project": {
                    "type": "string",
                    "description": "Project name/path for filtering"
                }
            },
            "required": ["content"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            content = input.get("content", "")
            if not content:
                return ToolResult(success=False, error={"message": "Content is required"})
            
            memory = self.store.add(
                content=content,
                type=input.get("type", "change"),
                title=input.get("title", ""),
                subtitle=input.get("subtitle", ""),
                facts=input.get("facts"),
                concepts=input.get("concepts"),
                files_read=input.get("files_read"),
                files_modified=input.get("files_modified"),
                session_id=input.get("session_id"),
                project=input.get("project"),
                category=input.get("category", "general"),
                importance=input.get("importance", 0.5),
                tags=input.get("tags"),
            )
            
            return ToolResult(
                success=True,
                output={
                    "id": memory.id,
                    "message": "Memory stored successfully",
                    "type": memory.type,
                    "title": memory.title,
                }
            )
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class ListMemoriesTool:
    """Tool to list memories with filtering."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "list_memories"
    
    @property
    def description(self) -> str:
        return (
            "List stored memories with optional filtering by type, category, concepts, project, or importance. "
            "Use index_only=true for lightweight listing with token estimates."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum memories to return",
                    "default": 20
                },
                "type": {
                    "type": "string",
                    "enum": OBSERVATION_TYPES,
                    "description": "Filter by observation type"
                },
                "category": {
                    "type": "string",
                    "enum": MEMORY_CATEGORIES,
                    "description": "Filter by category"
                },
                "concepts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by concepts (any match)"
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project"
                },
                "session_id": {
                    "type": "string",
                    "description": "Filter by session"
                },
                "min_importance": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Filter by minimum importance"
                },
                "index_only": {
                    "type": "boolean",
                    "description": "Return lightweight index view (title, subtitle, token estimate)",
                    "default": False
                }
            }
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            index_only = input.get("index_only", False)
            
            if index_only:
                # Progressive disclosure: layer 1 (index)
                memories = self.store.list_index(
                    limit=input.get("limit", 20),
                    project=input.get("project"),
                )
                return ToolResult(
                    success=True,
                    output={
                        "count": len(memories),
                        "index_view": True,
                        "memories": memories
                    }
                )
            
            # Full details
            memories = self.store.list_all(
                limit=input.get("limit", 20),
                type=input.get("type"),
                category=input.get("category"),
                concepts=input.get("concepts"),
                project=input.get("project"),
                session_id=input.get("session_id"),
                min_importance=input.get("min_importance"),
            )
            
            return ToolResult(
                success=True,
                output={
                    "count": len(memories),
                    "memories": [m.to_dict() for m in memories]
                }
            )
        except Exception as e:
            logger.error(f"Failed to list memories: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class SearchMemoriesTool:
    """Tool to search memories using FTS5 full-text search."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "search_memories"
    
    @property
    def description(self) -> str:
        return (
            "Search memories using full-text search. Returns memories sorted by relevance. "
            "Searches title, subtitle, content, facts, and concepts."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (keywords)"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum results to return",
                    "default": 10
                },
                "type": {
                    "type": "string",
                    "enum": OBSERVATION_TYPES,
                    "description": "Filter by observation type"
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project"
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            query = input.get("query", "")
            if not query:
                return ToolResult(success=False, error={"message": "Query is required"})
            
            memories = self.store.search(
                query=query,
                limit=input.get("limit", 10),
                type=input.get("type"),
                project=input.get("project"),
            )
            
            return ToolResult(
                success=True,
                output={
                    "query": query,
                    "count": len(memories),
                    "memories": [m.to_dict() for m in memories]
                }
            )
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class SearchByFileTool:
    """Tool to search memories by file path."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "search_memories_by_file"
    
    @property
    def description(self) -> str:
        return (
            "Search memories by file path. Finds memories where the file was read or modified. "
            "Useful for finding context about a specific file."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "File path to search for"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum results to return",
                    "default": 10
                }
            },
            "required": ["file_path"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            file_path = input.get("file_path", "")
            if not file_path:
                return ToolResult(success=False, error={"message": "file_path is required"})
            
            memories = self.store.search_by_file(
                file_path=file_path,
                limit=input.get("limit", 10),
            )
            
            return ToolResult(
                success=True,
                output={
                    "file_path": file_path,
                    "count": len(memories),
                    "memories": [m.to_dict() for m in memories]
                }
            )
        except Exception as e:
            logger.error(f"Failed to search by file: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class SearchByConceptTool:
    """Tool to search memories by concept type."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "search_memories_by_concept"
    
    @property
    def description(self) -> str:
        return (
            "Search memories by concept type. Concepts include: how-it-works, why-it-exists, "
            "problem-solution, gotcha, pattern, trade-off."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "enum": CONCEPT_TYPES,
                    "description": "Concept type to search for"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum results to return",
                    "default": 10
                }
            },
            "required": ["concept"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            concept = input.get("concept", "")
            if not concept:
                return ToolResult(success=False, error={"message": "concept is required"})
            
            memories = self.store.search_by_concept(
                concept=concept,
                limit=input.get("limit", 10),
            )
            
            return ToolResult(
                success=True,
                output={
                    "concept": concept,
                    "count": len(memories),
                    "memories": [m.to_dict() for m in memories]
                }
            )
        except Exception as e:
            logger.error(f"Failed to search by concept: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class GetMemoryTool:
    """Tool to get a specific memory by ID."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "get_memory"
    
    @property
    def description(self) -> str:
        return "Get a specific memory by its ID with full details."
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Memory ID"
                }
            },
            "required": ["id"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            memory_id = input.get("id", "")
            if not memory_id:
                return ToolResult(success=False, error={"message": "ID is required"})
            
            memory = self.store.get(memory_id)
            
            if memory is None:
                return ToolResult(
                    success=False,
                    error={"message": f"Memory not found: {memory_id}"}
                )
            
            return ToolResult(
                success=True,
                output=memory.to_dict()
            )
        except Exception as e:
            logger.error(f"Failed to get memory: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class UpdateMemoryTool:
    """Tool to update an existing memory."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "update_memory"
    
    @property
    def description(self) -> str:
        return "Update an existing memory's content, type, title, facts, concepts, or importance."
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Memory ID to update"
                },
                "content": {
                    "type": "string",
                    "description": "New content"
                },
                "type": {
                    "type": "string",
                    "enum": OBSERVATION_TYPES,
                    "description": "New observation type"
                },
                "title": {
                    "type": "string",
                    "description": "New title"
                },
                "subtitle": {
                    "type": "string",
                    "description": "New subtitle"
                },
                "facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New facts list"
                },
                "concepts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New concepts list"
                },
                "category": {
                    "type": "string",
                    "enum": MEMORY_CATEGORIES,
                    "description": "New category"
                },
                "importance": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "New importance score"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New tags"
                }
            },
            "required": ["id"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            memory_id = input.get("id", "")
            if not memory_id:
                return ToolResult(success=False, error={"message": "ID is required"})
            
            memory = self.store.update(
                memory_id=memory_id,
                content=input.get("content"),
                type=input.get("type"),
                title=input.get("title"),
                subtitle=input.get("subtitle"),
                facts=input.get("facts"),
                concepts=input.get("concepts"),
                category=input.get("category"),
                importance=input.get("importance"),
                tags=input.get("tags"),
            )
            
            if memory is None:
                return ToolResult(
                    success=False,
                    error={"message": f"Memory not found: {memory_id}"}
                )
            
            return ToolResult(
                success=True,
                output={
                    "message": "Memory updated successfully",
                    "memory": memory.to_dict()
                }
            )
        except Exception as e:
            logger.error(f"Failed to update memory: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class DeleteMemoryTool:
    """Tool to delete a memory."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "delete_memory"
    
    @property
    def description(self) -> str:
        return "Delete a memory by its ID."
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Memory ID to delete"
                }
            },
            "required": ["id"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            memory_id = input.get("id", "")
            if not memory_id:
                return ToolResult(success=False, error={"message": "ID is required"})
            
            deleted = self.store.delete(memory_id)
            
            if not deleted:
                return ToolResult(
                    success=False,
                    error={"message": f"Memory not found: {memory_id}"}
                )
            
            return ToolResult(
                success=True,
                output={"message": f"Memory {memory_id} deleted successfully"}
            )
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return ToolResult(success=False, error={"message": str(e)})


# =============================================================================
# Session Tools
# =============================================================================

class CreateSessionTool:
    """Tool to create or continue a session."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "create_session"
    
    @property
    def description(self) -> str:
        return (
            "Create a new session or continue an existing one. Sessions group related memories "
            "and enable progress tracking."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session identifier (creates new or continues existing)"
                },
                "project": {
                    "type": "string",
                    "description": "Project name/path"
                },
                "user_prompt": {
                    "type": "string",
                    "description": "Initial user prompt for this session"
                }
            },
            "required": ["session_id"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            session_id = input.get("session_id", "")
            if not session_id:
                return ToolResult(success=False, error={"message": "session_id is required"})
            
            session = self.store.create_session(
                session_id=session_id,
                project=input.get("project"),
                user_prompt=input.get("user_prompt"),
            )
            
            return ToolResult(
                success=True,
                output={
                    "message": "Session created/continued",
                    "session": session.to_dict()
                }
            )
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class AddSessionSummaryTool:
    """Tool to add a session progress summary."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "add_session_summary"
    
    @property
    def description(self) -> str:
        return (
            "Add a progress summary for a session. Captures what was requested, investigated, "
            "learned, completed, and next steps. Use periodically to checkpoint progress."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session identifier"
                },
                "request": {
                    "type": "string",
                    "description": "What the user asked for"
                },
                "investigated": {
                    "type": "string",
                    "description": "What was explored/researched"
                },
                "learned": {
                    "type": "string",
                    "description": "Key insights gained"
                },
                "completed": {
                    "type": "string",
                    "description": "Work that was completed"
                },
                "next_steps": {
                    "type": "string",
                    "description": "Current trajectory/remaining work"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional observations"
                },
                "files_read": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files that were read"
                },
                "files_edited": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files that were edited"
                },
                "project": {
                    "type": "string",
                    "description": "Project name/path"
                }
            },
            "required": ["session_id"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            session_id = input.get("session_id", "")
            if not session_id:
                return ToolResult(success=False, error={"message": "session_id is required"})
            
            summary = self.store.add_summary(
                session_id=session_id,
                request=input.get("request", ""),
                investigated=input.get("investigated", ""),
                learned=input.get("learned", ""),
                completed=input.get("completed", ""),
                next_steps=input.get("next_steps", ""),
                notes=input.get("notes", ""),
                files_read=input.get("files_read"),
                files_edited=input.get("files_edited"),
                project=input.get("project"),
            )
            
            return ToolResult(
                success=True,
                output={
                    "message": "Session summary added",
                    "summary": summary.to_dict()
                }
            )
        except Exception as e:
            logger.error(f"Failed to add session summary: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class GetSessionContextTool:
    """Tool to get context for a session (progressive disclosure)."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "get_session_context"
    
    @property
    def description(self) -> str:
        return (
            "Get context for injection at session start. Returns observation index (lightweight) "
            "and last session summary. Use for progressive disclosure - get index first, then "
            "fetch full details for relevant memories."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Filter by project"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum observations in index",
                    "default": 50
                },
                "include_summaries": {
                    "type": "boolean",
                    "description": "Include last session summary",
                    "default": True
                },
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 365,
                    "description": "Look back period in days",
                    "default": 90
                }
            }
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            context = self.store.get_context_for_session(
                project=input.get("project"),
                limit=input.get("limit", 50),
                include_summaries=input.get("include_summaries", True),
                days=input.get("days", 90),
            )
            
            return ToolResult(
                success=True,
                output=context
            )
        except Exception as e:
            logger.error(f"Failed to get session context: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class SearchSummariesTool:
    """Tool to search session summaries."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "search_summaries"
    
    @property
    def description(self) -> str:
        return (
            "Search session summaries using full-text search. Finds summaries matching query "
            "across request, investigated, learned, completed, next_steps, and notes fields."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum results",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            query = input.get("query", "")
            if not query:
                return ToolResult(success=False, error={"message": "query is required"})
            
            summaries = self.store.search_summaries(
                query=query,
                limit=input.get("limit", 10),
            )
            
            return ToolResult(
                success=True,
                output={
                    "query": query,
                    "count": len(summaries),
                    "summaries": [s.to_dict() for s in summaries]
                }
            )
        except Exception as e:
            logger.error(f"Failed to search summaries: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class GetTimelineTool:
    """Tool to get a timeline of context around a point in time."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "get_timeline"
    
    @property
    def description(self) -> str:
        return (
            "Get a timeline of observations and summaries around a specific point in time. "
            "Useful for understanding what happened in a time window."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "center_epoch": {
                    "type": "integer",
                    "description": "Center point in epoch milliseconds (default: now)"
                },
                "window_hours": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 168,
                    "description": "Hours before and after center",
                    "default": 24
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum items per category",
                    "default": 50
                }
            }
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            timeline = self.store.get_timeline(
                center_epoch=input.get("center_epoch"),
                window_hours=input.get("window_hours", 24),
                project=input.get("project"),
                limit=input.get("limit", 50),
            )
            
            return ToolResult(
                success=True,
                output=timeline
            )
        except Exception as e:
            logger.error(f"Failed to get timeline: {e}")
            return ToolResult(success=False, error={"message": str(e)})
