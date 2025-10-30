"""
Embedding service using sentence-transformers with caching.
"""
from typing import List, Union, Optional
from pathlib import Path
import logging
import hashlib
import numpy as np
from sentence_transformers import SentenceTransformer
from diskcache import Cache

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Handles text embeddings with caching for performance.
    
    Features:
    - Uses sentence-transformers for high-quality embeddings
    - Disk-based caching to avoid recomputing embeddings
    - Support for batch operations
    - Easy model swapping
    """
    
    # Default model: Fast, good quality, 384 dimensions
    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        cache_dir: str = ".mnemonic/embeddings_cache",
        device: Optional[str] = None
    ):
        """
        Initialize the embedding service.
        
        Args:
            model_name: Name of the sentence-transformers model
            cache_dir: Directory for embedding cache
            device: Device to use ('cuda', 'mps', 'cpu', or None for auto)
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize cache
        self.cache = Cache(str(self.cache_dir))
        logger.info(f"Initialized embedding cache at: {self.cache_dir}")
        
        # Load model
        logger.info(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name, device=device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")
    
    def embed(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            use_cache: Whether to use cache (default: True)
        
        Returns:
            Embedding vector as list of floats
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")
        
        # Generate cache key
        cache_key = self._get_cache_key(text)
        
        # Check cache first
        if use_cache:
            cached_embedding = self.cache.get(cache_key)
            if cached_embedding is not None:
                logger.debug(f"Cache HIT for text: {text[:50]}...")
                return cached_embedding
        
        # Generate embedding
        logger.debug(f"Cache MISS for text: {text[:50]}...")
        embedding = self.model.encode(text, convert_to_numpy=True)
        embedding_list = embedding.tolist()
        
        # Store in cache
        if use_cache:
            self.cache.set(cache_key, embedding_list)
        
        return embedding_list
    
    def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
        batch_size: int = 32
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch operation).
        
        This is more efficient than calling embed() multiple times.
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache (default: True)
            batch_size: Batch size for model inference
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = []
        texts_to_compute = []
        cache_keys = []
        indices_to_compute = []
        
        # Check cache for each text
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Cannot embed empty text at index {i}")
            
            cache_key = self._get_cache_key(text)
            cache_keys.append(cache_key)
            
            if use_cache:
                cached_embedding = self.cache.get(cache_key)
                if cached_embedding is not None:
                    embeddings.append(cached_embedding)
                    logger.debug(f"Cache HIT [{i}]: {text[:30]}...")
                else:
                    embeddings.append(None)
                    texts_to_compute.append(text)
                    indices_to_compute.append(i)
            else:
                embeddings.append(None)
                texts_to_compute.append(text)
                indices_to_compute.append(i)
        
        # Compute embeddings for cache misses
        if texts_to_compute:
            logger.info(f"Computing embeddings for {len(texts_to_compute)}/{len(texts)} texts")
            computed_embeddings = self.model.encode(
                texts_to_compute,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(texts_to_compute) > 10
            )
            
            # Insert computed embeddings and cache them
            for idx, embedding in zip(indices_to_compute, computed_embeddings):
                embedding_list = embedding.tolist()
                embeddings[idx] = embedding_list
                
                if use_cache:
                    self.cache.set(cache_keys[idx], embedding_list)
        
        return embeddings
    
    def get_stats(self) -> dict:
        """
        Get statistics about the embedding service.
        
        Returns:
            Dictionary with cache and model stats
        """
        cache_size = len(self.cache)
        # cache_bytes = sum(len(str(v)) for v in self.cache.values())
        # cache_mb = cache_bytes / (1024 * 1024)
        cache_size = len(self.cache)

        # Estimate cache size using directory size
        try:
            import os
            cache_mb = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(self.cache_dir)
                for filename in filenames
            ) / (1024 * 1024)
        except Exception:
            cache_mb = 0.0
        
        return {
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dim,
            "cache_directory": str(self.cache_dir),
            "cached_embeddings": cache_size,
            "cache_size_mb": round(cache_mb, 2),
            "device": str(self.model.device)
        }
    
    
    def clear_cache(self) -> int:
        """
        Clear the embedding cache.
        
        Returns:
            Number of entries cleared
        """
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared {count} cached embeddings")
        return count
    
    def _get_cache_key(self, text: str) -> str:
        """
        Generate a cache key for a text.
        
        Uses model name + text hash to ensure different models
        don't share cached embeddings.
        
        Args:
            text: Text to generate key for
        
        Returns:
            Cache key string
        """
        # Include model name in key to avoid collisions between models
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return f"{self.model_name}:{text_hash}"
    
    def __del__(self):
        """Cleanup: close cache on deletion."""
        if hasattr(self, 'cache'):
            self.cache.close()