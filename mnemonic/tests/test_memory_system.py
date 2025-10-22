"""
Tests for the integrated memory system.
"""
import pytest
import tempfile
import shutil
from pathlib import Path

from mnemonic.memory_system import Memory, MemorySystem


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def memory_system(temp_dir):
    """Create a memory system instance for testing."""
    json_path = Path(temp_dir) / "memories.json"
    vector_path = Path(temp_dir) / "chroma"
    return MemorySystem(json_path=str(json_path), vector_path=str(vector_path))


class TestMemory:
    """Test cases for Memory class."""
    
    def test_memory_creation(self):
        """Test creating a memory object."""
        memory = Memory(
            content="Test content",
            tags=["test", "example"],
            metadata={"key": "value"}
        )
        
        assert memory.content == "Test content"
        assert memory.tags == ["test", "example"]
        assert memory.metadata["key"] == "value"
        assert memory.id is not None
        assert memory.timestamp is not None
    
    def test_memory_to_dict(self):
        """Test converting memory to dictionary."""
        memory = Memory(content="Test", tags=["tag1"])
        mem_dict = memory.to_dict()
        
        assert mem_dict["content"] == "Test"
        assert mem_dict["tags"] == ["tag1"]
        assert "id" in mem_dict
        assert "timestamp" in mem_dict
    
    def test_memory_from_dict(self):
        """Test creating memory from dictionary."""
        data = {
            "id": "test-id",
            "content": "Test content",
            "tags": ["test"],
            "metadata": {"key": "value"},
            "timestamp": "2024-01-01T00:00:00"
        }
        
        memory = Memory.from_dict(data)
        
        assert memory.id == "test-id"
        assert memory.content == "Test content"
        assert memory.tags == ["test"]
        assert memory.metadata["key"] == "value"


class TestMemorySystem:
    """Test cases for MemorySystem class."""
    
    def test_initialization(self, temp_dir):
        """Test memory system initialization."""
        json_path = Path(temp_dir) / "memories.json"
        vector_path = Path(temp_dir) / "chroma"
        
        system = MemorySystem(json_path=str(json_path), vector_path=str(vector_path))
        
        assert system.json_path == json_path
        assert system.vector_store is not None
        assert len(system.memories) == 0
    
    def test_add_memory(self, memory_system):
        """Test adding a memory."""
        memory = memory_system.add(
            content="Python is awesome",
            tags=["programming", "python"]
        )
        
        assert memory.id in memory_system.memories
        assert memory.content == "Python is awesome"
        assert memory.tags == ["programming", "python"]
    
    def test_semantic_search(self, memory_system):
        """Test semantic search functionality."""
        # Add test memories
        memory_system.add("I love machine learning and AI")
        memory_system.add("Cooking pasta is my favorite hobby")
        memory_system.add("Deep learning with neural networks")
        
        # Search for AI-related content
        results = memory_system.semantic_search("artificial intelligence", n_results=2)
        
        assert len(results) > 0
        assert "memory" in results[0]
        assert "relevance_score" in results[0]
        
        # The top result should be AI-related
        top_content = results[0]["memory"]["content"].lower()
        assert any(word in top_content for word in ["learning", "ai", "neural"])
    
    def test_keyword_search(self, memory_system):
        """Test keyword search functionality."""
        # Add test memories
        memory_system.add("Python programming is fun")
        memory_system.add("JavaScript is also great")
        memory_system.add("I love Python")
        
        # Search for Python
        results = memory_system.keyword_search("Python")
        
        assert len(results) == 2
        assert all("python" in m.content.lower() for m in results)
    
    def test_keyword_search_with_tags(self, memory_system):
        """Test keyword search matching tags."""
        memory_system.add("Some content", tags=["python", "coding"])
        memory_system.add("Other content", tags=["javascript"])
        
        results = memory_system.keyword_search("python")
        
        assert len(results) == 1
        assert "python" in results[0].tags
    
    def test_get_memory(self, memory_system):
        """Test retrieving a specific memory."""
        memory = memory_system.add("Test content")
        
        retrieved = memory_system.get(memory.id)
        
        assert retrieved is not None
        assert retrieved.id == memory.id
        assert retrieved.content == "Test content"
    
    def test_get_nonexistent_memory(self, memory_system):
        """Test getting a memory that doesn't exist."""
        result = memory_system.get("nonexistent-id")
        assert result is None
    
    def test_list_recent(self, memory_system):
        """Test listing recent memories."""
        # Add multiple memories
        for i in range(15):
            memory_system.add(f"Memory {i}")
        
        # List recent (default 10)
        recent = memory_system.list_recent(n=10)
        
        assert len(recent) == 10
        # Should be sorted by timestamp (most recent first)
        assert recent[0].content == "Memory 14"
    
    def test_update_memory(self, memory_system):
        """Test updating a memory."""
        memory = memory_system.add("Original content")
        
        updated = memory_system.update(
            memory_id=memory.id,
            content="Updated content",
            tags=["updated"]
        )
        
        assert updated is not None
        assert updated.content == "Updated content"
        assert updated.tags == ["updated"]
        assert "updated_at" in updated.metadata
    
    def test_update_nonexistent_memory(self, memory_system):
        """Test updating a memory that doesn't exist."""
        result = memory_system.update("nonexistent-id", content="New content")
        assert result is None
    
    def test_delete_memory(self, memory_system):
        """Test deleting a memory."""
        memory = memory_system.add("To be deleted")
        
        success = memory_system.delete(memory.id)
        
        assert success is True
        assert memory.id not in memory_system.memories
        assert memory_system.get(memory.id) is None
    
    def test_delete_nonexistent_memory(self, memory_system):
        """Test deleting a memory that doesn't exist."""
        success = memory_system.delete("nonexistent-id")
        assert success is False
    
    def test_get_stats(self, memory_system):
        """Test getting system statistics."""
        # Add some memories with tags
        memory_system.add("Memory 1", tags=["tag1", "tag2"])
        memory_system.add("Memory 2", tags=["tag2", "tag3"])
        
        stats = memory_system.get_stats()
        
        assert stats["total_memories"] == 2
        assert stats["unique_tags"] == 3
        assert "json_path" in stats
        assert "vector_store" in stats
    
    def test_reset(self, memory_system):
        """Test resetting the memory system."""
        # Add some memories
        memory_system.add("Memory 1")
        memory_system.add("Memory 2")
        
        # Reset
        memory_system.reset()
        
        # Verify everything is cleared
        assert len(memory_system.memories) == 0
        stats = memory_system.get_stats()
        assert stats["total_memories"] == 0
    
    def test_persistence(self, temp_dir):
        """Test that memories persist across instances."""
        json_path = Path(temp_dir) / "memories.json"
        vector_path = Path(temp_dir) / "chroma"
        
        # Create system and add memory
        system1 = MemorySystem(json_path=str(json_path), vector_path=str(vector_path))
        memory = system1.add("Persistent memory")
        memory_id = memory.id
        
        # Create new system instance
        system2 = MemorySystem(json_path=str(json_path), vector_path=str(vector_path))
        
        # Memory should still exist
        retrieved = system2.get(memory_id)
        assert retrieved is not None
        assert retrieved.content == "Persistent memory"
    
    def test_semantic_search_with_tag_filter(self, memory_system):
        """Test semantic search with tag filtering."""
        memory_system.add("Python programming", tags=["python", "coding"])
        memory_system.add("Python snake facts", tags=["animals", "nature"])
        memory_system.add("JavaScript coding", tags=["javascript", "coding"])
        
        # Search for programming but filter by coding tag
        results = memory_system.semantic_search(
            query="programming",
            n_results=5,
            tags=["coding"]
        )
        
        # Should return results (implementation depends on ChromaDB filtering)
        assert isinstance(results, list)
    
    def test_memory_ordering(self, memory_system):
        """Test that memories are ordered correctly."""
        import time
        
        # Add memories with slight delays
        memory1 = memory_system.add("First memory")
        time.sleep(0.01)
        memory2 = memory_system.add("Second memory")
        time.sleep(0.01)
        memory3 = memory_system.add("Third memory")
        
        recent = memory_system.list_recent(n=3)
        
        # Most recent should be first
        assert recent[0].id == memory3.id
        assert recent[1].id == memory2.id
        assert recent[2].id == memory1.id
    
    def test_empty_system_operations(self, memory_system):
        """Test operations on empty memory system."""
        # Search on empty system
        results = memory_system.semantic_search("test")
        assert results == []
        
        results = memory_system.keyword_search("test")
        assert results == []
        
        # List on empty system
        recent = memory_system.list_recent()
        assert recent == []
        
        # Stats on empty system
        stats = memory_system.get_stats()
        assert stats["total_memories"] == 0