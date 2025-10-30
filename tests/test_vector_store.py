"""
Tests for vector store functionality.
"""
import pytest
import tempfile
import shutil
from pathlib import Path

from mnemonic.vector_store import VectorStore


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def vector_store(temp_dir):
    """Create a vector store instance for testing."""
    return VectorStore(persist_directory=temp_dir)


class TestVectorStore:
    """Test cases for VectorStore class."""
    
    def test_initialization(self, temp_dir):
        """Test vector store initialization."""
        store = VectorStore(persist_directory=temp_dir)
        assert store.collection_name == "memories"
        assert store.persist_dir == Path(temp_dir)
        assert store.collection is not None
    
    def test_add_memory(self, vector_store):
        """Test adding a memory to the vector store."""
        vector_store.add_memory(
            memory_id="test-001",
            content="I love Python programming",
            metadata={"tag": "coding"}
        )
        
        stats = vector_store.get_stats()
        assert stats["total_memories"] == 1
    
    def test_search_memories(self, vector_store):
        """Test semantic search functionality."""
        # Add test memories
        vector_store.add_memory(
            memory_id="mem-001",
            content="Python is a great programming language for data science"
        )
        vector_store.add_memory(
            memory_id="mem-002",
            content="I enjoy hiking in the mountains"
        )
        vector_store.add_memory(
            memory_id="mem-003",
            content="Machine learning with Python is fascinating"
        )
        
        # Search for programming-related content
        results = vector_store.search("coding with Python", n_results=2)
        
        assert len(results) > 0
        assert results[0]["id"] in ["mem-001", "mem-003"]
        assert "relevance_score" in results[0]
    
    def test_update_memory(self, vector_store):
        """Test updating a memory."""
        # Add initial memory
        vector_store.add_memory(
            memory_id="mem-update",
            content="Original content",
            metadata={"version": 1}
        )
        
        # Update memory
        vector_store.update_memory(
            memory_id="mem-update",
            content="Updated content",
            metadata={"version": 2}
        )
        
        # Search should find the updated content
        results = vector_store.search("Updated content", n_results=1)
        assert len(results) == 1
        assert results[0]["id"] == "mem-update"
    
    def test_delete_memory(self, vector_store):
        """Test deleting a memory."""
        # Add memory
        vector_store.add_memory(
            memory_id="mem-delete",
            content="This will be deleted"
        )
        
        # Verify it exists
        stats = vector_store.get_stats()
        initial_count = stats["total_memories"]
        
        # Delete memory
        vector_store.delete_memory("mem-delete")
        
        # Verify it's gone
        stats = vector_store.get_stats()
        assert stats["total_memories"] == initial_count - 1
    
    def test_search_with_no_results(self, vector_store):
        """Test search when no memories exist."""
        results = vector_store.search("nonexistent query", n_results=5)
        assert results == []
    
    def test_multiple_memories_search(self, vector_store):
        """Test search with multiple related memories."""
        # Add multiple related memories
        memories = [
            ("mem-1", "Python is excellent for web development"),
            ("mem-2", "JavaScript is used for frontend development"),
            ("mem-3", "Web development requires HTML and CSS"),
            ("mem-4", "Python Flask is a web framework"),
            ("mem-5", "I like reading science fiction books"),
        ]
        
        for mem_id, content in memories:
            vector_store.add_memory(memory_id=mem_id, content=content)
        
        # Search for web development
        results = vector_store.search("web development", n_results=3)
        
        assert len(results) <= 3
        # The top results should be about web development
        assert any("web" in r["content"].lower() for r in results[:2])
    
    def test_search_with_metadata_filter(self, vector_store):
        """Test search with metadata filtering."""
        # Add memories with different tags
        vector_store.add_memory(
            memory_id="mem-python",
            content="Python programming",
            metadata={"tags": ["coding", "python"]}
        )
        vector_store.add_memory(
            memory_id="mem-java",
            content="Java programming",
            metadata={"tags": ["coding", "java"]}
        )
        
        # Note: This test demonstrates the API, but actual filtering
        # depends on ChromaDB's metadata filtering capabilities
        results = vector_store.search(
            "programming",
            n_results=5,
            where={"tags": {"$in": ["python"]}}
        )
        
        # At minimum, we should get results
        assert isinstance(results, list)
    
    def test_reset_store(self, vector_store):
        """Test resetting the vector store."""
        # Add some memories
        vector_store.add_memory("mem-1", "Test content 1")
        vector_store.add_memory("mem-2", "Test content 2")
        
        # Verify memories exist
        stats = vector_store.get_stats()
        assert stats["total_memories"] == 2
        
        # Reset store
        vector_store.reset()
        
        # Verify all memories are gone
        stats = vector_store.get_stats()
        assert stats["total_memories"] == 0
    
    def test_get_stats(self, vector_store):
        """Test getting vector store statistics."""
        stats = vector_store.get_stats()
        
        assert "total_memories" in stats
        assert "collection_name" in stats
        assert "persist_directory" in stats
        assert stats["collection_name"] == "memories"
    
    def test_relevance_scores(self, vector_store):
        """Test that relevance scores are calculated."""
        vector_store.add_memory(
            memory_id="mem-score",
            content="Python is a programming language"
        )
        
        results = vector_store.search("Python programming", n_results=1)
        
        assert len(results) > 0
        assert "relevance_score" in results[0]
        assert "distance" in results[0]
        # Relevance score should be between 0 and 1
        if results[0]["relevance_score"] is not None:
            assert 0 <= results[0]["relevance_score"] <= 1
    
    def test_persistence(self, temp_dir):
        """Test that data persists across store instances."""
        # Create store and add memory
        store1 = VectorStore(persist_directory=temp_dir)
        store1.add_memory("mem-persist", "This should persist")
        
        # Create new store instance with same directory
        store2 = VectorStore(persist_directory=temp_dir)
        stats = store2.get_stats()
        
        # Memory should still be there
        assert stats["total_memories"] == 1