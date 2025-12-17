"""Tests for the memory tools."""

import pytest
from amplifier_module_tool_memory.store import MemoryStore
from amplifier_module_tool_memory.tools import (
    AddMemoryTool,
    ListMemoriesTool,
    SearchMemoriesTool,
    GetMemoryTool,
    UpdateMemoryTool,
    DeleteMemoryTool,
)


class TestAddMemoryTool:
    """Tests for AddMemoryTool."""
    
    @pytest.mark.asyncio
    async def test_add_memory_success(self, temp_db):
        """Test successful memory addition."""
        store = MemoryStore(db_path=temp_db)
        tool = AddMemoryTool(store)
        
        result = await tool.execute({
            "content": "Test memory",
            "category": "learning",
            "importance": 0.8
        })
        
        assert result.success is True
        assert "id" in result.output
    
    @pytest.mark.asyncio
    async def test_add_memory_missing_content(self, temp_db):
        """Test error when content is missing."""
        store = MemoryStore(db_path=temp_db)
        tool = AddMemoryTool(store)
        
        result = await tool.execute({})
        
        assert result.success is False
        assert "Content is required" in result.error["message"]


class TestSearchMemoriesTool:
    """Tests for SearchMemoriesTool."""
    
    @pytest.mark.asyncio
    async def test_search_finds_matches(self, temp_db):
        """Test that search finds matching memories."""
        store = MemoryStore(db_path=temp_db)
        store.add(content="Python programming tips")
        store.add(content="JavaScript tips")
        
        tool = SearchMemoriesTool(store)
        result = await tool.execute({"query": "Python"})
        
        assert result.success is True
        assert result.output["count"] >= 1
    
    @pytest.mark.asyncio
    async def test_search_missing_query(self, temp_db):
        """Test error when query is missing."""
        store = MemoryStore(db_path=temp_db)
        tool = SearchMemoriesTool(store)
        
        result = await tool.execute({})
        
        assert result.success is False


class TestDeleteMemoryTool:
    """Tests for DeleteMemoryTool."""
    
    @pytest.mark.asyncio
    async def test_delete_success(self, temp_db):
        """Test successful deletion."""
        store = MemoryStore(db_path=temp_db)
        memory = store.add(content="To delete")
        
        tool = DeleteMemoryTool(store)
        result = await tool.execute({"id": memory.id})
        
        assert result.success is True
        assert store.count() == 0
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, temp_db):
        """Test deleting non-existent memory."""
        store = MemoryStore(db_path=temp_db)
        tool = DeleteMemoryTool(store)
        
        result = await tool.execute({"id": "nonexistent"})
        
        assert result.success is False
