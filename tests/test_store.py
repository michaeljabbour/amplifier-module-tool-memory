"""Tests for the memory store."""

import pytest
from amplifier_module_tool_memory.store import MemoryStore


class TestMemoryStore:
    """Tests for MemoryStore."""
    
    def test_add_memory(self, temp_db):
        """Test adding a memory."""
        store = MemoryStore(db_path=temp_db)
        
        memory = store.add(
            content="Test memory content",
            category="learning",
            importance=0.8,
            tags=["test", "example"]
        )
        
        assert memory.id is not None
        assert memory.content == "Test memory content"
        assert memory.category == "learning"
        assert memory.importance == 0.8
        assert memory.tags == ["test", "example"]
    
    def test_get_memory(self, temp_db):
        """Test retrieving a memory by ID."""
        store = MemoryStore(db_path=temp_db)
        
        created = store.add(content="Retrievable memory")
        retrieved = store.get(created.id)
        
        assert retrieved is not None
        assert retrieved.content == "Retrievable memory"
        assert retrieved.accessed_count == 1  # Incremented on get
    
    def test_get_nonexistent_memory(self, temp_db):
        """Test retrieving a non-existent memory."""
        store = MemoryStore(db_path=temp_db)
        
        result = store.get("nonexistent-id")
        assert result is None
    
    def test_list_all(self, temp_db):
        """Test listing all memories."""
        store = MemoryStore(db_path=temp_db)
        
        store.add(content="Memory 1", category="learning")
        store.add(content="Memory 2", category="decision")
        store.add(content="Memory 3", category="learning")
        
        all_memories = store.list_all()
        assert len(all_memories) == 3
    
    def test_list_by_category(self, temp_db):
        """Test filtering by category."""
        store = MemoryStore(db_path=temp_db)
        
        store.add(content="Learning 1", category="learning")
        store.add(content="Decision 1", category="decision")
        store.add(content="Learning 2", category="learning")
        
        learning = store.list_all(category="learning")
        assert len(learning) == 2
        assert all(m.category == "learning" for m in learning)
    
    def test_search(self, temp_db):
        """Test keyword search."""
        store = MemoryStore(db_path=temp_db)
        
        store.add(content="Python is a programming language")
        store.add(content="JavaScript is also a language")
        store.add(content="The weather is nice today")
        
        results = store.search("programming language")
        assert len(results) >= 1
        assert "programming" in results[0].content.lower()
    
    def test_update_memory(self, temp_db):
        """Test updating a memory."""
        store = MemoryStore(db_path=temp_db)
        
        created = store.add(content="Original content", importance=0.5)
        updated = store.update(created.id, content="Updated content", importance=0.9)
        
        assert updated is not None
        assert updated.content == "Updated content"
        assert updated.importance == 0.9
    
    def test_delete_memory(self, temp_db):
        """Test deleting a memory."""
        store = MemoryStore(db_path=temp_db)
        
        created = store.add(content="To be deleted")
        assert store.count() == 1
        
        deleted = store.delete(created.id)
        assert deleted is True
        assert store.count() == 0
    
    def test_enforce_limit(self, temp_db):
        """Test that max_memories limit is enforced."""
        store = MemoryStore(db_path=temp_db, max_memories=3)
        
        store.add(content="Memory 1")
        store.add(content="Memory 2")
        store.add(content="Memory 3")
        store.add(content="Memory 4")  # Should trigger cleanup
        
        assert store.count() == 3
    
    def test_invalid_category_defaults_to_general(self, temp_db):
        """Test that invalid category defaults to general."""
        store = MemoryStore(db_path=temp_db)
        
        memory = store.add(content="Test", category="invalid_category")
        assert memory.category == "general"
    
    def test_importance_clamped(self, temp_db):
        """Test that importance is clamped to 0.0-1.0."""
        store = MemoryStore(db_path=temp_db)
        
        high = store.add(content="High", importance=2.0)
        low = store.add(content="Low", importance=-1.0)
        
        assert high.importance == 1.0
        assert low.importance == 0.0
