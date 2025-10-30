"""
Tests for the embedding service.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from mnemonic.embedding_service import EmbeddingService


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def embedding_service(temp_cache_dir):
    """Create an embedding service with temporary cache."""
    service = EmbeddingService(cache_dir=temp_cache_dir)
    yield service
    # Cleanup
    service.cache.close()


class TestEmbeddingService:
    """Test suite for EmbeddingService."""
    
    def test_initialization(self, embedding_service):
        """Test that service initializes correctly."""
        assert embedding_service.model_name == "all-MiniLM-L6-v2"
        assert embedding_service.embedding_dim == 384
        assert embedding_service.cache is not None
    
    def test_embed_single_text(self, embedding_service):
        """Test embedding a single text."""
        text = "This is a test sentence"
        embedding = embedding_service.embed(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 384  # Model dimension
        assert all(isinstance(x, float) for x in embedding)
    
    def test_embed_empty_text_raises_error(self, embedding_service):
        """Test that embedding empty text raises an error."""
        with pytest.raises(ValueError, match="Cannot embed empty text"):
            embedding_service.embed("")
        
        with pytest.raises(ValueError, match="Cannot embed empty text"):
            embedding_service.embed("   ")
    
    def test_cache_functionality(self, embedding_service):
        """Test that caching works correctly."""
        text = "This is a cached sentence"
        
        # First call - should compute
        embedding1 = embedding_service.embed(text)
        cache_stats1 = embedding_service.get_stats()
        
        # Second call - should use cache
        embedding2 = embedding_service.embed(text)
        cache_stats2 = embedding_service.get_stats()
        
        # Embeddings should be identical
        assert embedding1 == embedding2
        
        # Cache should have one entry
        assert cache_stats1["cached_embeddings"] == 1
        assert cache_stats2["cached_embeddings"] == 1
    
    def test_cache_disabled(self, embedding_service):
        """Test that cache can be disabled."""
        text = "This text won't be cached"
        
        # Embed without caching
        embedding1 = embedding_service.embed(text, use_cache=False)
        stats = embedding_service.get_stats()
        
        assert stats["cached_embeddings"] == 0
        assert len(embedding1) == 384
    
    def test_embed_batch(self, embedding_service):
        """Test batch embedding."""
        texts = [
            "First sentence",
            "Second sentence",
            "Third sentence"
        ]
        
        embeddings = embedding_service.embed_batch(texts)
        
        assert len(embeddings) == 3
        assert all(len(emb) == 384 for emb in embeddings)
        
        # Each embedding should be different
        assert embeddings[0] != embeddings[1]
        assert embeddings[1] != embeddings[2]
    
    def test_embed_batch_with_cache(self, embedding_service):
        """Test that batch embedding uses cache efficiently."""
        texts = [
            "Sentence A",
            "Sentence B",
            "Sentence A",  # Duplicate
        ]
        
        # First batch
        embeddings1 = embedding_service.embed_batch(texts)
        stats1 = embedding_service.get_stats()
        
        # Should have cached 2 unique texts
        assert stats1["cached_embeddings"] == 2
        
        # Embeddings at index 0 and 2 should be identical (same text)
        assert embeddings1[0] == embeddings1[2]
        
        # Second batch with same texts
        embeddings2 = embedding_service.embed_batch(texts)
        
        # Should return same embeddings
        assert embeddings1 == embeddings2
    
    def test_embed_batch_empty_list(self, embedding_service):
        """Test that embedding empty batch returns empty list."""
        embeddings = embedding_service.embed_batch([])
        assert embeddings == []
    
    def test_embed_batch_with_empty_text_raises_error(self, embedding_service):
        """Test that batch with empty text raises error."""
        texts = ["Valid text", "", "Another valid text"]
        
        with pytest.raises(ValueError, match="Cannot embed empty text"):
            embedding_service.embed_batch(texts)
    
    def test_different_texts_different_embeddings(self, embedding_service):
        """Test that different texts produce different embeddings."""
        text1 = "Machine learning is fascinating"
        text2 = "I love pizza"
        
        emb1 = embedding_service.embed(text1)
        emb2 = embedding_service.embed(text2)
        
        assert emb1 != emb2
    
    def test_similar_texts_similar_embeddings(self, embedding_service):
        """Test that similar texts have similar embeddings."""
        text1 = "I love machine learning"
        text2 = "Machine learning is great"
        text3 = "Pizza is delicious"
        
        emb1 = embedding_service.embed(text1)
        emb2 = embedding_service.embed(text2)
        emb3 = embedding_service.embed(text3)
        
        # Calculate cosine similarity
        def cosine_similarity(a, b):
            import numpy as np
            a = np.array(a)
            b = np.array(b)
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        
        # Similar texts should have higher similarity
        sim_12 = cosine_similarity(emb1, emb2)
        sim_13 = cosine_similarity(emb1, emb3)
        
        assert sim_12 > sim_13  # ML texts more similar than ML vs pizza
    
    def test_get_stats(self, embedding_service):
        """Test getting service statistics."""
        # Add some embeddings
        embedding_service.embed("Test 1")
        embedding_service.embed("Test 2")
        
        stats = embedding_service.get_stats()
        
        assert "model_name" in stats
        assert stats["model_name"] == "all-MiniLM-L6-v2"
        assert "embedding_dimension" in stats
        assert stats["embedding_dimension"] == 384
        assert "cached_embeddings" in stats
        assert stats["cached_embeddings"] == 2
        assert "cache_size_mb" in stats
        assert stats["cache_size_mb"] >= 0
    
    def test_clear_cache(self, embedding_service):
        """Test clearing the cache."""
        # Add some embeddings
        embedding_service.embed("Test 1")
        embedding_service.embed("Test 2")
        embedding_service.embed("Test 3")
        
        stats_before = embedding_service.get_stats()
        assert stats_before["cached_embeddings"] == 3
        
        # Clear cache
        cleared_count = embedding_service.clear_cache()
        assert cleared_count == 3
        
        stats_after = embedding_service.get_stats()
        assert stats_after["cached_embeddings"] == 0
    
    def test_custom_model(self, temp_cache_dir):
        """Test using a custom model."""
        # Note: This test uses the same model to avoid downloading
        # In production, you might test with a different model
        service = EmbeddingService(
            model_name="all-MiniLM-L6-v2",
            cache_dir=temp_cache_dir
        )
        
        assert service.model_name == "all-MiniLM-L6-v2"
        embedding = service.embed("Test")
        assert len(embedding) == 384
        
        service.cache.close()