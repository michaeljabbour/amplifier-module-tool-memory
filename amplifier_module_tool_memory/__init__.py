"""
Persistent Memory Tool Module for Amplifier.

Enables AI agents to store and retrieve memories across sessions.
Memories are persisted in SQLite and can be searched by keyword.

Tools provided:
- add_memory: Store a new memory
- list_memories: List all memories with optional filtering
- search_memories: Search memories by keyword
- get_memory: Get a specific memory by ID
- update_memory: Update an existing memory
- delete_memory: Delete a memory
"""

import logging
from typing import Any

from amplifier_core import ModuleCoordinator

from .store import MemoryStore
from .tools import (
    AddMemoryTool,
    ListMemoriesTool,
    SearchMemoriesTool,
    GetMemoryTool,
    UpdateMemoryTool,
    DeleteMemoryTool,
)

__version__ = "0.1.0"
__all__ = ["mount", "MemoryStore"]

logger = logging.getLogger(__name__)


async def mount(coordinator: ModuleCoordinator, config: dict | None = None):
    """
    Mount the memory tool module.

    Args:
        coordinator: Amplifier coordinator instance
        config: Configuration dictionary with optional keys:
            - storage_path: Path to SQLite database (default: ~/.amplifier/memories.db)
            - max_memories: Maximum memories to store (default: 1000)

    Returns:
        Cleanup function
    """
    config = config or {}
    
    # Initialize the memory store
    storage_path = config.get("storage_path")
    max_memories = config.get("max_memories", 1000)
    
    store = MemoryStore(db_path=storage_path, max_memories=max_memories)
    
    # Create tool instances
    tools = [
        AddMemoryTool(store),
        ListMemoriesTool(store),
        SearchMemoriesTool(store),
        GetMemoryTool(store),
        UpdateMemoryTool(store),
        DeleteMemoryTool(store),
    ]
    
    # Mount each tool
    for tool in tools:
        await coordinator.mount("tools", tool, name=tool.name)
        logger.debug(f"Mounted memory tool: {tool.name}")

    # Expose the memory store via capabilities so hooks can access it
    coordinator.set_capability("memory.store", store)
    logger.debug("Exposed memory store via capabilities")

    logger.info(f"Memory module mounted with {len(tools)} tools (storage: {store.db_path})")

    # Return cleanup function
    async def cleanup():
        logger.info("Memory module cleanup complete")

    return cleanup
