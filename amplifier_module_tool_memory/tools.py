"""
Memory tools for AI agents.

Each tool follows the Amplifier Tool protocol:
- name: Tool identifier
- description: Human-readable description
- input_schema: JSON Schema for input validation
- execute(input): Async method that returns ToolResult
"""

from typing import Any
import logging

from amplifier_core import ToolResult

from .store import MemoryStore, MEMORY_CATEGORIES

logger = logging.getLogger(__name__)


class AddMemoryTool:
    """Tool to add a new memory."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "add_memory"
    
    @property
    def description(self) -> str:
        return (
            "Store a new memory for future reference. Use this when learning something important "
            "that should be remembered across sessions - facts, preferences, decisions, solutions, etc."
        )
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The memory content to store"
                },
                "category": {
                    "type": "string",
                    "enum": MEMORY_CATEGORIES,
                    "description": "Category for organization",
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
                category=input.get("category", "general"),
                importance=input.get("importance", 0.5),
                tags=input.get("tags"),
            )
            
            return ToolResult(
                success=True,
                output={
                    "id": memory.id,
                    "message": f"Memory stored successfully",
                    "category": memory.category,
                }
            )
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            return ToolResult(success=False, error={"message": str(e)})


class ListMemoriesTool:
    """Tool to list memories."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "list_memories"
    
    @property
    def description(self) -> str:
        return (
            "List stored memories with optional filtering by category or importance. "
            "Use this to see what memories are available."
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
                "category": {
                    "type": "string",
                    "enum": MEMORY_CATEGORIES,
                    "description": "Filter by category"
                },
                "min_importance": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Filter by minimum importance"
                }
            }
        }
    
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        try:
            memories = self.store.list_all(
                limit=input.get("limit", 20),
                category=input.get("category"),
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
    """Tool to search memories by keyword."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "search_memories"
    
    @property
    def description(self) -> str:
        return (
            "Search memories by keyword. Use this to find specific memories about a topic. "
            "Returns memories sorted by relevance."
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


class GetMemoryTool:
    """Tool to get a specific memory by ID."""
    
    def __init__(self, store: MemoryStore):
        self.store = store
    
    @property
    def name(self) -> str:
        return "get_memory"
    
    @property
    def description(self) -> str:
        return "Get a specific memory by its ID."
    
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
        return "Update an existing memory's content, category, importance, or tags."
    
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
