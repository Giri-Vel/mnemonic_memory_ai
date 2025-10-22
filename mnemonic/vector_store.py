"""
Vector store implementation using ChromaDB for semantic search.
"""
import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages vector embeddings and semantic search using ChromaDB."""
    
    def __init__(self, persist_directory: str = ".mnemonic/chroma"):
        """
        Initialize ChromaDB vector store.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection_name = "memories"
        try:
            self.collection = self.client.get_collection(self.collection_name)
            logger.info(f"Loaded existing collection: {self.collection_name}")
        except Exception:
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
        Add a memory to the vector store.
        
        Args:
            memory_id: Unique identifier for the memory
            content: Text content to embed
            metadata: Additional metadata to store
        """

        try:
            # Prepare metadata
            meta = metadata or {}
            meta["timestamp"] = meta.get("timestamp", datetime.now().isoformat())
            meta = self._sanitize_metadata(meta)
            
            for key, value in meta.items():
                if isinstance(value, list):
                    meta[key] = ", ".join(value)
            
            # Add to collection (ChromaDB handles embedding automatically)
            self.collection.add(
                documents=[content],
                metadatas=[meta],
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
        Search for similar memories using semantic search.
        
        Args:
            query: Search query
            n_results: Number of results to return
            where: Metadata filters (optional)
        
        Returns:
            List of matching memories with scores
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where
            )
            
            # Format results
            formatted_results = []
            if results and results["ids"]:
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
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
        Update an existing memory in the vector store.
        
        Args:
            memory_id: Memory identifier
            content: Updated content
            metadata: Updated metadata
        """
        try:
            meta = metadata or {}
            meta["updated_at"] = datetime.now().isoformat()
            meta = self._sanitize_metadata(meta)
            
            for key, value in meta.items():
                if isinstance(value, list):
                    meta[key] = ", ".join(value)
            
            self.collection.update(
                ids=[memory_id],
                documents=[content],
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
        Get statistics about the vector store.
        
        Returns:
            Dictionary with store statistics
        """
        try:
            count = self.collection.count()
            return {
                "total_memories": count,
                "collection_name": self.collection_name,
                "persist_directory": str(self.persist_dir)
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
            
    def _sanitize_metadata(self, meta_dict):
        """Recursively convert list metadata values into strings."""
        for key, value in list(meta_dict.items()):
            if isinstance(value, list):
                meta_dict[key] = ", ".join(map(str, value))
            elif isinstance(value, dict):
                self._sanitize_metadata(value)
        return meta_dict