"""
Vector store implementation using ChromaDB for semantic search.
Now with custom embedding service integration.
"""
import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import json

from mnemonic.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages vector embeddings and semantic search using ChromaDB with custom embeddings."""
    
    def __init__(
        self,
        persist_directory: str = ".mnemonic/chroma",
        embedding_model: Optional[str] = None,
        embedding_cache_dir: Optional[str] = None
    ):
        """
        Initialize ChromaDB vector store with custom embedding service.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
            embedding_model: Name of embedding model (default: all-MiniLM-L6-v2)
            embedding_cache_dir: Directory for embedding cache
        """
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize embedding service
        cache_dir = embedding_cache_dir or str(self.persist_dir.parent / "embeddings_cache")
        self.embedding_service = EmbeddingService(
            model_name=embedding_model,
            cache_dir=cache_dir
        )
        logger.info(f"Initialized embedding service: {self.embedding_service.model_name}")
        
        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection (without default embedding function)
        self.collection_name = "memories"
        try:
            self.collection = self.client.get_collection(self.collection_name)
            logger.info(f"Loaded existing collection: {self.collection_name}")
        except Exception:
            # Create collection without embedding function (we'll provide embeddings manually)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
            logger.info(f"Created new collection: {self.collection_name}")
    
    def add_memory(
        self,
        memory_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a memory to the vector store with custom embedding.
        
        Args:
            memory_id: Unique identifier for the memory
            content: Text content to embed
            metadata: Additional metadata to store
        """
        try:
            # Generate embedding using our custom service
            embedding = self.embedding_service.embed(content)
            
            # Prepare metadata
            meta = metadata or {}
            meta["timestamp"] = meta.get("timestamp", datetime.now().isoformat())
            
            # Serialize metadata for ChromaDB (lists → JSON strings)
            meta = self._serialize_metadata(meta)
            
            # Add to collection with our custom embedding
            self.collection.add(
                documents=[content],
                metadatas=[meta],
                embeddings=[embedding],  # Provide custom embedding
                ids=[memory_id]
            )
            logger.debug(f"Added memory {memory_id} to vector store")
        except Exception as e:
            logger.error(f"Error adding memory to vector store: {e}")
            raise
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar memories using semantic search with custom embeddings.
        
        Args:
            query: Search query
            n_results: Number of results to return
            where: Metadata filters (optional)
        
        Returns:
            List of matching memories with scores
        """
        try:
            # Generate query embedding using our custom service
            query_embedding = self.embedding_service.embed(query)
            
            # Query with custom embedding
            results = self.collection.query(
                query_embeddings=[query_embedding],  # Use custom embedding
                n_results=n_results,
                where=where
            )
            
            # Format results
            formatted_results = []
            if results and results["ids"]:
                for i in range(len(results["ids"][0])):
                    # Deserialize metadata (JSON strings → lists)
                    metadata = self._deserialize_metadata(results["metadatas"][0][i])
                    
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": metadata,
                        "distance": results["distances"][0][i] if "distances" in results else None,
                        "relevance_score": 1 - results["distances"][0][i] if "distances" in results else None
                    })
            
            logger.debug(f"Found {len(formatted_results)} results for query: {query}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    def update_memory(
        self,
        memory_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update an existing memory in the vector store with custom embedding.
        
        Args:
            memory_id: Memory identifier
            content: Updated content
            metadata: Updated metadata
        """
        try:
            # Generate new embedding for updated content
            embedding = self.embedding_service.embed(content)
            
            meta = metadata or {}
            meta["updated_at"] = datetime.now().isoformat()
            
            # Serialize metadata for ChromaDB
            meta = self._serialize_metadata(meta)
            
            self.collection.update(
                ids=[memory_id],
                documents=[content],
                embeddings=[embedding],  # Provide custom embedding
                metadatas=[meta]
            )
            logger.debug(f"Updated memory {memory_id} in vector store")
        except Exception as e:
            logger.error(f"Error updating memory in vector store: {e}")
            raise
    
    def delete_memory(self, memory_id: str) -> None:
        """
        Delete a memory from the vector store.
        
        Args:
            memory_id: Memory identifier
        """
        try:
            self.collection.delete(ids=[memory_id])
            logger.debug(f"Deleted memory {memory_id} from vector store")
        except Exception as e:
            logger.error(f"Error deleting memory from vector store: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store and embedding service.
        
        Returns:
            Dictionary with store statistics
        """
        try:
            count = self.collection.count()
            embedding_stats = self.embedding_service.get_stats()
            
            return {
                "total_memories": count,
                "collection_name": self.collection_name,
                "persist_directory": str(self.persist_dir),
                "embedding_service": embedding_stats
            }
        except Exception as e:
            logger.error(f"Error getting vector store stats: {e}")
            return {}
    
    def reset(self) -> None:
        """Reset the vector store (delete all data)."""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Vector store reset successfully")
        except Exception as e:
            logger.error(f"Error resetting vector store: {e}")
    
    def get_all_memories(self) -> List[Dict[str, Any]]:
        """
        Get all memories from the vector store.
        Used for migration and debugging.
        
        Returns:
            List of all memories with metadata (deserialized)
        """
        try:
            # Get all documents
            count = self.collection.count()
            if count == 0:
                return []
            
            results = self.collection.get(
                include=["documents", "metadatas"]
            )
            
            memories = []
            for i in range(len(results["ids"])):
                # Deserialize metadata
                metadata = self._deserialize_metadata(results["metadatas"][i])
                
                memories.append({
                    "id": results["ids"][i],
                    "content": results["documents"][i],
                    "metadata": metadata
                })
            
            return memories
        except Exception as e:
            logger.error(f"Error getting all memories: {e}")
            return []
    
    def _serialize_metadata(self, meta_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize metadata for ChromaDB storage.
        Converts lists and complex types to JSON strings.
        
        ChromaDB only supports: str, int, float, bool, None
        
        Args:
            meta_dict: Metadata dictionary with native Python types
            
        Returns:
            Serialized metadata dictionary (ChromaDB-compatible)
        """
        serialized = {}
        for key, value in meta_dict.items():
            if value is None:
                # Skip None values
                continue
            elif isinstance(value, (str, int, float, bool)):
                # Primitive types - keep as-is
                serialized[key] = value
            elif isinstance(value, list):
                # Lists → JSON string
                # Special handling for tags to make them searchable
                if key == "tags" and len(value) == 0:
                    # Skip empty tags list
                    continue
                serialized[key] = json.dumps(value)
            elif isinstance(value, dict):
                # Dicts → JSON string
                serialized[key] = json.dumps(value)
            else:
                # Other types → string
                serialized[key] = str(value)
        
        return serialized
    
    def _deserialize_metadata(self, meta_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deserialize metadata from ChromaDB storage.
        Converts JSON strings back to native Python types.
        
        Args:
            meta_dict: Serialized metadata from ChromaDB
            
        Returns:
            Deserialized metadata dictionary with native types
        """
        deserialized = {}
        for key, value in meta_dict.items():
            if isinstance(value, str):
                # Try to parse as JSON
                try:
                    # Check if it looks like JSON (starts with [ or {)
                    if value.startswith('[') or value.startswith('{'):
                        deserialized[key] = json.loads(value)
                    else:
                        # Regular string
                        deserialized[key] = value
                except json.JSONDecodeError:
                    # Not valid JSON, keep as string
                    deserialized[key] = value
            else:
                # Primitive types (int, float, bool)
                deserialized[key] = value
        
        return deserialized