"""
Enhanced memory system with semantic search capabilities.
Integrates JSON storage with ChromaDB vector store.
"""
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from mnemonic.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Memory:
    """Represents a single memory entry."""
    
    def __init__(
        self,
        content: str,
        memory_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ):
        self.id = memory_id or str(uuid.uuid4())
        self.content = content
        self.tags = tags or []
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now().isoformat()
        self.metadata["timestamp"] = self.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "tags": self.tags,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """Create memory from dictionary."""
        return cls(
            content=data["content"],
            memory_id=data["id"],
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp")
        )


class MemorySystem:
    """
    Enhanced memory system with dual storage:
    - JSON for structured data and fast keyword search
    - ChromaDB for semantic vector search
    """
    
    def __init__(
        self,
        json_path: str = ".mnemonic/memories.json",
        vector_path: str = ".mnemonic/chroma"
    ):
        """
        Initialize memory system with JSON and vector storage.
        
        Args:
            json_path: Path to JSON storage file
            vector_path: Path to ChromaDB storage directory
        """
        self.json_path = Path(json_path)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize vector store
        self.vector_store = VectorStore(persist_directory=vector_path)
        
        # Load existing memories
        self.memories: Dict[str, Memory] = {}
        self._load_memories()
    
    def _load_memories(self) -> None:
        """Load memories from JSON storage."""
        if self.json_path.exists():
            try:
                with open(self.json_path, 'r') as f:
                    data = json.load(f)
                    self.memories = {
                        mem_id: Memory.from_dict(mem_data)
                        for mem_id, mem_data in data.items()
                    }
                logger.info(f"Loaded {len(self.memories)} memories from JSON")
            except Exception as e:
                logger.error(f"Error loading memories: {e}")
                self.memories = {}
    
    def _save_memories(self) -> None:
        """Save memories to JSON storage."""
        try:
            data = {
                mem_id: memory.to_dict()
                for mem_id, memory in self.memories.items()
            }
            with open(self.json_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.memories)} memories to JSON")
        except Exception as e:
            logger.error(f"Error saving memories: {e}")
            raise
    
    def add(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Memory:
        """
        Add a new memory to both JSON and vector storage.
        
        Args:
            content: Memory content
            tags: Optional tags for categorization
            metadata: Optional metadata
        
        Returns:
            Created Memory object
        """
        print("MEMORY_SYSTEM DEBUG 1: Start of add()")
        print(f"MEMORY_SYSTEM DEBUG 2: content={content}, tags={tags}")
        memory = Memory(content=content, tags=tags, metadata=metadata)
        print(f"MEMORY_SYSTEM DEBUG 3: Memory object created, id={memory.id}")
        
        # Add to JSON storage
        self.memories[memory.id] = memory
        print("MEMORY_SYSTEM DEBUG 4: Added to self.memories dict")
        self._save_memories()
        print("MEMORY_SYSTEM DEBUG 5: _save_memories() completed")
        
        # Add to vector store
        print("MEMORY_SYSTEM DEBUG 6: About to call vector_store.add_memory()")
        self.vector_store.add_memory(
            memory_id=memory.id,
            content=content,
            metadata={
                "tags": ", ".join(tags) if tags else "",
                "timestamp": memory.timestamp,
                **(metadata or {})
            }
        )
        print("MEMORY_SYSTEM DEBUG 7: vector_store.add_memory() completed")
        
        logger.info(f"Added memory {memory.id}")
        return memory
    
    def semantic_search(
        self,
        query: str,
        n_results: int = 5,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search memories using semantic similarity.
        
        Args:
            query: Search query
            n_results: Number of results to return
            tags: Filter by tags (optional)
        
        Returns:
            List of matching memories with relevance scores
        """
        # Build where filter for tags if provided
        where_filter = None
        if tags:
            where_filter = {"tags": {"$in": tags}}
        
        results = self.vector_store.search(
            query=query,
            n_results=n_results,
            where=where_filter
        )
        
        # Enrich results with full memory data from JSON
        enriched_results = []
        for result in results:
            memory_id = result["id"]
            if memory_id in self.memories:
                memory = self.memories[memory_id]
                enriched_results.append({
                    "memory": memory.to_dict(),
                    "relevance_score": result.get("relevance_score"),
                    "distance": result.get("distance")
                })
        
        return enriched_results
    
    def keyword_search(self, keyword: str) -> List[Memory]:
        """
        Search memories using keyword matching (legacy search).
        
        Args:
            keyword: Keyword to search for
        
        Returns:
            List of matching Memory objects
        """
        keyword_lower = keyword.lower()
        results = []
        
        for memory in self.memories.values():
            if keyword_lower in memory.content.lower():
                results.append(memory)
            elif any(keyword_lower in tag.lower() for tag in memory.tags):
                results.append(memory)
        
        # Sort by timestamp (most recent first)
        results.sort(key=lambda m: m.timestamp, reverse=True)
        return results
    
    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        return self.memories.get(memory_id)
    
    def list_recent(self, n: int = 10) -> List[Memory]:
        """Get the most recent memories."""
        sorted_memories = sorted(
            self.memories.values(),
            key=lambda m: m.timestamp,
            reverse=True
        )
        return sorted_memories[:n]
    
    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Memory]:
        """
        Update an existing memory.
        
        Args:
            memory_id: Memory identifier
            content: New content (optional)
            tags: New tags (optional)
            metadata: New metadata (optional)
        
        Returns:
            Updated Memory object or None if not found
        """
        if memory_id not in self.memories:
            logger.warning(f"Memory {memory_id} not found")
            return None
        
        memory = self.memories[memory_id]
        
        # Update fields
        if content is not None:
            memory.content = content
        if tags is not None:
            memory.tags = tags
        if metadata is not None:
            memory.metadata.update(metadata)
        
        memory.metadata["updated_at"] = datetime.now().isoformat()
        
        # Save to JSON
        self._save_memories()
        
        # Update vector store
        self.vector_store.update_memory(
            memory_id=memory_id,
            content=memory.content,
            metadata={
                "tags": memory.tags,
                "timestamp": memory.timestamp,
                **memory.metadata
            }
        )
        
        logger.info(f"Updated memory {memory_id}")
        return memory
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete a memory from both storages.
        
        Args:
            memory_id: Memory identifier
        
        Returns:
            True if deleted, False if not found
        """
        if memory_id not in self.memories:
            logger.warning(f"Memory {memory_id} not found")
            return False
        
        # Delete from JSON
        del self.memories[memory_id]
        self._save_memories()
        
        # Delete from vector store
        self.vector_store.delete_memory(memory_id)
        
        logger.info(f"Deleted memory {memory_id}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory system."""
        total = len(self.memories)
        tags = set()
        for memory in self.memories.values():
            tags.update(memory.tags)
        
        vector_stats = self.vector_store.get_stats()
        
        return {
            "total_memories": total,
            "unique_tags": len(tags),
            "json_path": str(self.json_path),
            "vector_store": vector_stats
        }
    
    def reset(self) -> None:
        """Reset the entire memory system."""
        self.memories = {}
        self._save_memories()
        self.vector_store.reset()
        logger.info("Memory system reset successfully")