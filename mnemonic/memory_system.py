"""
Enhanced memory system with semantic search capabilities.
Integrates JSON storage with ChromaDB vector store AND SQLite database.
Now includes hybrid search (semantic + keyword fusion).

STORAGE COUPLING:
- JSON: Fast keyword search + data persistence
- ChromaDB: Semantic vector search
- SQLite: Entity extraction + structured queries
"""
import json
import uuid
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import os

from mnemonic.vector_store import VectorStore
from mnemonic.config import DB_PATH
from mnemonic.entity_extractor import EntityExtractor
from mnemonic.entity_storage import EntityStorage
from mnemonic.checkpointing import CheckpointManager
from mnemonic.sessions import SessionStore
from mnemonic.llm_providers import get_provider, DummyProvider


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
    Enhanced memory system with triple storage:
    - JSON for structured data and fast keyword search
    - ChromaDB for semantic vector search
    - SQLite for entity extraction and structured queries
    - Hybrid search combining semantic + keyword
    """
    
    # Hybrid search weights (semantic/keyword)
    # Based on industry research: semantic bias for conceptual queries
    SEMANTIC_WEIGHT = 0.85
    KEYWORD_WEIGHT = 0.15
    
    def __init__(
        self,
        json_path: str = ".mnemonic/memories.json",
        vector_path: str = ".mnemonic/chroma"
    ):
        """
        Initialize memory system with JSON, vector, and SQLite storage.
        
        Args:
            json_path: Path to JSON storage file
            vector_path: Path to ChromaDB storage directory
        """
        self.json_path = Path(json_path)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize vector store
        self.vector_store = VectorStore(persist_directory=vector_path)
        
        # SQLite database path (from config)
        self.db_path = DB_PATH
        
        # Load existing memories
        self.memories: Dict[str, Memory] = {}
        self._load_memories()

        try:
            self.entity_extractor = EntityExtractor(self.db_path)
            self.entity_storage = EntityStorage(self.db_path)
            self.checkpoint_manager = CheckpointManager(self.db_path)
            logger.info("Entity extraction system initialized")
        except Exception as e:
            logger.warning(f"Entity extraction not available: {e}")
            self.entity_extractor = None
            self.entity_storage = None
            self.checkpoint_manager = None

        # Session management
        self.session_store = SessionStore(self.db_path)
        
        # Use DummyProvider (no API needed) until Gemini quota available
        try:
            provider = os.getenv("LLM_PROVIDER", "dummy")
            self.llm_provider = get_provider(provider)
        except:
            self.llm_provider = DummyProvider(always_continue=False)
        
        self.session_time_gap = timedelta(hours=2)
    
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
    
    def _save_to_sqlite(
        self,
        memory: Memory
    ) -> int:
        """
        Save memory to SQLite database.
        
        Args:
            memory: Memory object to save
        
        Returns:
            SQLite row ID (INTEGER)
        
        Raises:
            Exception if save fails
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert into memories table
            cursor.execute("""
                INSERT INTO memories (content, uuid, created_at)
                VALUES (?, ?, ?)
            """, (
                memory.content,
                memory.id,  # Store UUID for cross-reference
                memory.timestamp
            ))
            
            sqlite_id = cursor.lastrowid
            
            # Insert tags into memory_tags table
            if memory.tags:
                for tag in memory.tags:
                    cursor.execute("""
                        INSERT INTO memory_tags (memory_id, tag)
                        VALUES (?, ?)
                    """, (sqlite_id, tag.strip()))
            
            conn.commit()
            logger.debug(f"Saved memory to SQLite (id={sqlite_id}, uuid={memory.id})")
            
            return sqlite_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving to SQLite: {e}")
            raise
        finally:
            conn.close()
    
    def _update_sqlite(
        self,
        memory: Memory
    ) -> bool:
        """
        Update memory in SQLite database.
        
        Args:
            memory: Memory object with updated data
        
        Returns:
            True if successful, False if memory not found
        
        Raises:
            Exception if update fails
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Update memories table
            cursor.execute("""
                UPDATE memories 
                SET content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE uuid = ?
            """, (memory.content, memory.id))
            
            if cursor.rowcount == 0:
                # Memory doesn't exist in SQLite
                logger.warning(f"Memory {memory.id} not found in SQLite for update")
                conn.close()
                return False
            
            # Get SQLite id for tag updates
            cursor.execute("SELECT id FROM memories WHERE uuid = ?", (memory.id,))
            sqlite_id = cursor.fetchone()[0]
            
            # Update tags: delete old, insert new
            cursor.execute("DELETE FROM memory_tags WHERE memory_id = ?", (sqlite_id,))
            
            if memory.tags:
                for tag in memory.tags:
                    cursor.execute("""
                        INSERT INTO memory_tags (memory_id, tag)
                        VALUES (?, ?)
                    """, (sqlite_id, tag.strip()))
            
            conn.commit()
            logger.debug(f"Updated memory in SQLite (uuid={memory.id})")
            
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating SQLite: {e}")
            raise
        finally:
            conn.close()
    
    def _delete_from_sqlite(
        self,
        memory_id: str
    ) -> bool:
        """
        Delete memory from SQLite database.
        
        Args:
            memory_id: UUID of memory to delete
        
        Returns:
            True if successful, False if memory not found
        
        Raises:
            Exception if delete fails
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Delete from memories (CASCADE will delete tags)
            cursor.execute("""
                DELETE FROM memories WHERE uuid = ?
            """, (memory_id,))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            
            if deleted:
                logger.debug(f"Deleted memory from SQLite (uuid={memory_id})")
            else:
                logger.warning(f"Memory {memory_id} not found in SQLite for deletion")
            
            return deleted
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error deleting from SQLite: {e}")
            raise
        finally:
            conn.close()
    
    def add(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Memory:
        """
        Add a new memory to ALL storage systems (JSON + ChromaDB + SQLite).
        
        Uses transactional approach: if ANY storage fails, the operation fails.
        This ensures data consistency across all systems.
        
        Args:
            content: Memory content
            tags: Optional tags for categorization
            metadata: Optional metadata
        
        Returns:
            Created Memory object
        
        Raises:
            Exception if any storage system fails
        """
        memory = Memory(content=content, tags=tags, metadata=metadata)
        
        # Track what we've saved for rollback
        json_saved = False
        vector_saved = False
        sqlite_saved = False
        
        try:
            # 1. Add to JSON storage (primary source of truth)
            self.memories[memory.id] = memory
            self._save_memories()
            json_saved = True
            logger.debug(f"✓ JSON storage: {memory.id}")
            
            # 2. Add to vector store (for semantic search)
            vector_metadata = {
                "timestamp": memory.timestamp,
                **(metadata or {})
            }
            
            # Only add tags if they're non-empty (ChromaDB doesn't like empty lists)
            if tags and len(tags) > 0:
                vector_metadata["tags"] = tags
            
            self.vector_store.add_memory(
                memory_id=memory.id,
                content=content,
                metadata=vector_metadata
            )
            vector_saved = True
            logger.debug(f"✓ Vector storage: {memory.id}")
            
            # 3. Add to SQLite (for entity extraction)
            sqlite_id = self._save_to_sqlite(memory)
            sqlite_saved = True
            logger.debug(f"✓ SQLite storage: {memory.id} (sqlite_id={sqlite_id})")

            # 4. Extract and store entities (if available)
            if self.entity_extractor and self.entity_storage:
                try:
                    entities = self.entity_extractor.extract(content, tags or [])
                    stats = self.entity_storage.store_entities(sqlite_id, entities)
                    logger.debug(f"✓ Entities: {len(entities)} extracted "
                                f"(T:{stats['tentative_added']}, "
                                f"P:{stats['promoted']}, "
                                f"U:{stats['frequency_updated']})")
                except Exception as e:
                    # Non-critical - log but don't fail
                    logger.warning(f"Entity extraction failed: {e}")

            # 5. Create checkpoint (if available)
            if self.checkpoint_manager:
                try:
                    self.checkpoint_manager.create_checkpoint(
                        memory_id=sqlite_id,
                        text=content,
                        entities=entities if 'entities' in locals() else [],
                        user_labels=self.entity_extractor.user_labels if self.entity_extractor else []
                    )
                    logger.debug(f"✓ Checkpoint created")
                except Exception as e:
                    # Non-critical - log but don't fail
                    logger.warning(f"Checkpoint creation failed: {e}")
            
            # 6. Determine session for this memory
            session_id = self._determine_session(content, sqlite_id)
            
            logger.info(f"Added memory {memory.id} to all storage systems")
            return memory
            
        except Exception as e:
            # ROLLBACK: Remove from successfully saved storages
            logger.error(f"Failed to add memory {memory.id}: {e}")
            
            if json_saved:
                try:
                    del self.memories[memory.id]
                    self._save_memories()
                    logger.debug("↩ Rolled back JSON storage")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback JSON: {rollback_error}")
            
            if vector_saved:
                try:
                    self.vector_store.delete_memory(memory.id)
                    logger.debug("↩ Rolled back vector storage")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback vector storage: {rollback_error}")
            
            if sqlite_saved:
                try:
                    self._delete_from_sqlite(memory.id)
                    logger.debug("↩ Rolled back SQLite storage")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback SQLite: {rollback_error}")
            
            # Re-raise the original exception
            raise

    
    def _determine_session(self, content: str, sqlite_id: int) -> Optional[str]:
        """
        Assign memory to session using 2-hour gap + LLM check.
        
        Args:
            content: Memory content
            sqlite_id: SQLite ID of the memory
            
        Returns:
            Session ID assigned to this memory
        """
        # Get active session
        active_session = self.session_store.get_active_session()
        
        if not active_session:
            # No active session - create new one
            session = self.session_store.create_session()
            self.session_store.add_memory_to_session(session.id, sqlite_id, sequence_number=1)
            logger.info(f"Created new session: {session.id}")
            return session.id
        
        # Check time gap
        last_memories = self.session_store.get_session_memories(active_session.id, limit=3)
        if not last_memories:
            # Empty session, add to it
            self.session_store.add_memory_to_session(active_session.id, sqlite_id, sequence_number=1)
            return active_session.id
        
        last_memory_time = datetime.fromisoformat(last_memories[-1]["created_at"])
        time_gap = datetime.now() - last_memory_time
        
        if time_gap < self.session_time_gap:
            # Within 2 hours - add to current session
            seq = len(last_memories) + 1
            self.session_store.add_memory_to_session(active_session.id, sqlite_id, sequence_number=seq)
            logger.debug(f"Added to existing session: {active_session.id}")
            return active_session.id
        
        # >2 hours - check continuity with LLM
        context = "\n".join([m["content"] for m in last_memories[-3:]])
        
        try:
            continues = self.llm_provider.check_continuity(context, content, timeout=5.0)
            
            if continues:
                # Same conversation - extend session
                seq = active_session.memory_count + 1
                self.session_store.add_memory_to_session(active_session.id, sqlite_id, sequence_number=seq)
                logger.info(f"Extended session after {time_gap}: {active_session.id}")
                return active_session.id
            else:
                # New topic - finalize old, create new
                summary = self.llm_provider.generate_summary(
                    [m["content"] for m in self.session_store.get_session_memories(active_session.id)],
                    topic=active_session.topic
                )
                self.session_store.finalize_session(active_session.id, summary)
                
                new_session = self.session_store.create_session()
                self.session_store.add_memory_to_session(new_session.id, sqlite_id, sequence_number=1)
                logger.info(f"Finalized {active_session.id}, created new: {new_session.id}")
                return new_session.id
                
        except Exception as e:
            logger.error(f"LLM check failed: {e}, creating new session")
            # Fallback: finalize old, create new
            self.session_store.finalize_session(active_session.id, summary="Session ended")
            new_session = self.session_store.create_session()
            self.session_store.add_memory_to_session(new_session.id, sqlite_id, sequence_number=1)
            return new_session.id
    
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
            # Use $contains for list filtering in ChromaDB
            # This checks if ANY of the provided tags exist in the memory's tags
            where_filter = {"tags": {"$contains": tags[0]}} if len(tags) == 1 else None
            # Note: Complex tag filtering (AND/OR) can be added later
        
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
    
    def keyword_search(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Search memories using keyword matching.
        
        Args:
            keyword: Keyword to search for
        
        Returns:
            List of matching memories with keyword match scores
        """
        keyword_lower = keyword.lower()
        results = []
        
        for memory in self.memories.values():
            score = 0.0
            
            # Check content (case-insensitive)
            if keyword_lower in memory.content.lower():
                # Calculate score based on term frequency
                count = memory.content.lower().count(keyword_lower)
                # Normalize by content length (favor shorter, focused memories)
                score += min(count / max(len(memory.content.split()), 1), 1.0) * 0.8
            
            # Check tags (exact match gets higher score)
            for tag in memory.tags:
                if keyword_lower == tag.lower():
                    score += 0.3  # Exact tag match
                elif keyword_lower in tag.lower():
                    score += 0.15  # Partial tag match
            
            if score > 0:
                results.append({
                    "memory": memory.to_dict(),
                    "keyword_score": min(score, 1.0)  # Cap at 1.0
                })
        
        # Sort by keyword score (highest first)
        results.sort(key=lambda x: x["keyword_score"], reverse=True)
        return results
    
    def hybrid_search(
        self,
        query: str,
        n_results: int = 5,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search memories using hybrid approach (semantic + keyword fusion).
        
        Uses normalized score fusion with learned weights:
        - Semantic search captures conceptual similarity
        - Keyword search captures exact term matches
        - Scores are normalized and combined with industry-standard weights
        
        Args:
            query: Search query
            n_results: Number of results to return
            tags: Filter by tags (optional)
        
        Returns:
            List of matching memories with combined relevance scores
        """
        # Get results from both search methods (fetch more for better fusion)
        fetch_count = min(n_results * 3, 20)  # Fetch 3x requested, max 20
        
        semantic_results = self.semantic_search(query, n_results=fetch_count, tags=tags)
        keyword_results = self.keyword_search(query)[:fetch_count]
        
        # Normalize scores within each result set
        semantic_normalized = self._normalize_scores(
            semantic_results,
            score_key="relevance_score"
        )
        keyword_normalized = self._normalize_scores(
            keyword_results,
            score_key="keyword_score"
        )
        
        # Merge results by memory ID
        merged_scores = {}
        
        # Add semantic results
        for result in semantic_normalized:
            memory_id = result["memory"]["id"]
            merged_scores[memory_id] = {
                "memory": result["memory"],
                "semantic_score": result.get("normalized_score", 0.0),
                "keyword_score": 0.0,  # Default if not in keyword results
                "sources": ["semantic"]
            }
        
        # Add/update with keyword results
        for result in keyword_normalized:
            memory_id = result["memory"]["id"]
            if memory_id in merged_scores:
                # Memory appears in both - update keyword score
                merged_scores[memory_id]["keyword_score"] = result.get("normalized_score", 0.0)
                merged_scores[memory_id]["sources"].append("keyword")
            else:
                # Memory only in keyword results
                merged_scores[memory_id] = {
                    "memory": result["memory"],
                    "semantic_score": 0.0,
                    "keyword_score": result.get("normalized_score", 0.0),
                    "sources": ["keyword"]
                }
        
        # Calculate final hybrid scores
        final_results = []
        for memory_id, data in merged_scores.items():
            # Weighted fusion of normalized scores
            hybrid_score = (
                data["semantic_score"] * self.SEMANTIC_WEIGHT +
                data["keyword_score"] * self.KEYWORD_WEIGHT
            )
            
            final_results.append({
                "memory": data["memory"],
                "hybrid_score": hybrid_score,
                "semantic_score": data["semantic_score"],
                "keyword_score": data["keyword_score"],
                "sources": data["sources"]
            })
        
        # Sort by hybrid score and return top N
        final_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        
        logger.info(f"Hybrid search: {len(semantic_results)} semantic + "
                   f"{len(keyword_results)} keyword → {len(final_results)} merged")
        
        return final_results[:n_results]
    
    def _normalize_scores(
        self,
        results: List[Dict[str, Any]],
        score_key: str
    ) -> List[Dict[str, Any]]:
        """
        Normalize scores to 0-1 range using min-max normalization.
        
        Args:
            results: List of search results
            score_key: Key containing the score to normalize
        
        Returns:
            Results with added 'normalized_score' field
        """
        if not results:
            return []
        
        # Extract scores
        scores = [r.get(score_key, 0.0) for r in results]
        
        # Handle edge cases
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score
        
        if score_range == 0:
            # All scores are identical - assign 1.0 to all
            for result in results:
                result["normalized_score"] = 1.0
        else:
            # Min-max normalization
            for i, result in enumerate(results):
                original_score = scores[i]
                normalized = (original_score - min_score) / score_range
                result["normalized_score"] = normalized
        
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
        Update an existing memory in ALL storage systems.
        
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
        
        # Track what we've updated for rollback
        json_updated = False
        vector_updated = False
        sqlite_updated = False
        
        # Store original state for rollback
        original_content = memory.content
        original_tags = memory.tags.copy()
        original_metadata = memory.metadata.copy()
        
        try:
            # Update fields
            if content is not None:
                memory.content = content
            if tags is not None:
                memory.tags = tags
            if metadata is not None:
                memory.metadata.update(metadata)
            
            memory.metadata["updated_at"] = datetime.now().isoformat()
            
            # 1. Save to JSON
            self._save_memories()
            json_updated = True
            logger.debug(f"✓ Updated JSON: {memory_id}")
            
            # 2. Update vector store
            vector_metadata = {
                "timestamp": memory.timestamp,
                **memory.metadata
            }
            
            if memory.tags and len(memory.tags) > 0:
                vector_metadata["tags"] = memory.tags
            
            self.vector_store.update_memory(
                memory_id=memory_id,
                content=memory.content,
                metadata=vector_metadata
            )
            vector_updated = True
            logger.debug(f"✓ Updated vector store: {memory_id}")
            
            # 3. Update SQLite
            self._update_sqlite(memory)
            sqlite_updated = True
            logger.debug(f"✓ Updated SQLite: {memory_id}")
            
            logger.info(f"Updated memory {memory_id} in all storage systems")
            return memory
            
        except Exception as e:
            # ROLLBACK: Restore original state
            logger.error(f"Failed to update memory {memory_id}: {e}")
            
            if json_updated:
                try:
                    memory.content = original_content
                    memory.tags = original_tags
                    memory.metadata = original_metadata
                    self._save_memories()
                    logger.debug("↩ Rolled back JSON storage")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback JSON: {rollback_error}")
            
            # Note: Vector and SQLite rollback would need original state too
            # For now, log the inconsistency
            if vector_updated or sqlite_updated:
                logger.error(f"Partial update detected - manual intervention may be needed")
            
            raise
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete a memory from ALL storage systems.
        
        Args:
            memory_id: Memory identifier
        
        Returns:
            True if deleted, False if not found
        """
        if memory_id not in self.memories:
            logger.warning(f"Memory {memory_id} not found")
            return False
        
        # Store memory for potential rollback
        deleted_memory = self.memories[memory_id]
        
        # Track what we've deleted
        json_deleted = False
        vector_deleted = False
        sqlite_deleted = False
        
        try:
            # 1. Delete from JSON
            del self.memories[memory_id]
            self._save_memories()
            json_deleted = True
            logger.debug(f"✓ Deleted from JSON: {memory_id}")
            
            # 2. Delete from vector store
            self.vector_store.delete_memory(memory_id)
            vector_deleted = True
            logger.debug(f"✓ Deleted from vector store: {memory_id}")
            
            # 3. Delete from SQLite
            self._delete_from_sqlite(memory_id)
            sqlite_deleted = True
            logger.debug(f"✓ Deleted from SQLite: {memory_id}")
            
            logger.info(f"Deleted memory {memory_id} from all storage systems")
            return True
            
        except Exception as e:
            # ROLLBACK: Restore deleted memory
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            
            if json_deleted:
                try:
                    self.memories[memory_id] = deleted_memory
                    self._save_memories()
                    logger.debug("↩ Rolled back JSON storage")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback JSON: {rollback_error}")
            
            # Note: Vector and SQLite rollback would need to re-add
            if vector_deleted or sqlite_deleted:
                logger.error(f"Partial deletion detected - manual intervention may be needed")
            
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory system."""
        total = len(self.memories)
        tags = set()
        for memory in self.memories.values():
            tags.update(memory.tags)
        
        vector_stats = self.vector_store.get_stats()
        
        # Get SQLite stats
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories")
            sqlite_count = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            logger.error(f"Error getting SQLite stats: {e}")
            sqlite_count = 0
        
        return {
            "total_memories": total,
            "unique_tags": len(tags),
            "json_path": str(self.json_path),
            "vector_store": vector_stats,
            "sqlite_memories": sqlite_count,
            "sqlite_db_path": str(self.db_path),
            "hybrid_search_weights": {
                "semantic": self.SEMANTIC_WEIGHT,
                "keyword": self.KEYWORD_WEIGHT
            }
        }

    def get_sessions(self, limit: int = 10) -> list[dict]:
        """
        Get recent conversation sessions with metadata.
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of session dictionaries with:
            - id: Session UUID
            - start_time: ISO timestamp of first memory
            - end_time: ISO timestamp of last memory
            - memory_count: Number of memories in session
            - summary: LLM-generated summary (or None)
        """
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            query = """
            SELECT 
                s.id,
                s.start_time,
                s.end_time,
                s.summary,
                COUNT(sm.memory_id) as memory_count
            FROM sessions s
            LEFT JOIN session_memories sm ON sm.session_id = s.id
            GROUP BY s.id
            ORDER BY s.end_time DESC
            LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            sessions = []
            for row in rows:
                sessions.append({
                    'id': row['id'],
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'summary': row['summary'],
                    'memory_count': row['memory_count']
                })
            
            return sessions
            
        finally:
            conn.close()


    def get_session_details(self, session_id: str) -> dict | None:
        """
        Get detailed information about a specific session.
        
        Args:
            session_id: Full or partial session UUID (will match prefix)
            
        Returns:
            Dictionary with session details including memories, or None if not found
        """
        import sqlite3
        import json
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Find session by ID prefix
            cursor.execute("""
                SELECT * FROM sessions 
                WHERE id LIKE ? 
                ORDER BY end_time DESC 
                LIMIT 1
            """, (f"{session_id}%",))
            
            session_row = cursor.fetchone()
            if not session_row:
                return None
            
            full_session_id = session_row['id']
            
            # Get memory IDs from session_memories join table
            cursor.execute("""
                SELECT m.uuid, sm.sequence_number
                FROM session_memories sm
                JOIN memories m ON m.id = sm.memory_id
                WHERE sm.session_id = ?
                ORDER BY sm.sequence_number ASC
            """, (full_session_id,))

            memory_rows = cursor.fetchall()

            # Load actual memory data using self.get() method
            memories = []
            if memory_rows:
                for row in memory_rows:
                    mem_uuid = row['uuid']  # ← Changed from memory_id to uuid
                    mem = self.get(mem_uuid)
                    if mem:
                        memories.append({
                            'id': mem.id,
                            'content': mem.content,
                            'timestamp': mem.timestamp
                        })
            
            # Parse metadata for entity highlights if available
            entity_highlights = None
            if session_row['metadata']:
                try:
                    metadata = json.loads(session_row['metadata'])
                    entity_highlights = metadata.get('entity_highlights')
                except (json.JSONDecodeError, TypeError):
                    entity_highlights = None
            
            return {
                'id': session_row['id'],
                'start_time': session_row['start_time'],
                'end_time': session_row['end_time'],
                'summary': session_row['summary'],
                'entity_highlights': entity_highlights,
                'memory_count': len(memories),
                'memories': memories
            }
            
        finally:
            conn.close()

    def get_context_for_timeframe(
        self,
        hours: Optional[int] = None,
        days: Optional[int] = None,
        include_summaries: bool = True
    ) -> Dict[str, Any]:
        """
        Get conversation context for a specific timeframe.
        
        Retrieves all memories from sessions within the specified time window,
        organized by session with optional summaries for context.
        
        Args:
            hours: Look back this many hours (default: None)
            days: Look back this many days (default: None)
            include_summaries: Include session summaries (default: True)
            
        Returns:
            Dictionary with:
            - timeframe: Description of the time window
            - sessions: List of sessions with their memories
            - total_memories: Total count of memories
            - total_sessions: Total count of sessions
            
        Examples:
            # Last 24 hours
            context = ms.get_context_for_timeframe(hours=24)
            
            # Last week
            context = ms.get_context_for_timeframe(days=7)
        """
        import sqlite3
        import json
        
        # Calculate time threshold
        if hours is None and days is None:
            hours = 24  # Default to last 24 hours
        
        if hours:
            time_threshold = datetime.now() - timedelta(hours=hours)
            timeframe_desc = f"last {hours} hour{'s' if hours != 1 else ''}"
        else:
            time_threshold = datetime.now() - timedelta(days=days)
            timeframe_desc = f"last {days} day{'s' if days != 1 else ''}"
        
        threshold_iso = time_threshold.isoformat()
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Find sessions that overlap with the timeframe
            # A session overlaps if: start_time <= now AND (end_time >= threshold OR end_time IS NULL)
            cursor.execute("""
                SELECT 
                    s.id,
                    s.start_time,
                    s.end_time,
                    s.summary,
                    s.is_active,
                    s.metadata
                FROM sessions s
                WHERE s.start_time <= datetime('now')
                  AND (s.end_time >= ? OR s.end_time IS NULL)
                ORDER BY s.start_time ASC
            """, (threshold_iso,))
            
            session_rows = cursor.fetchall()
            
            sessions = []
            total_memories = 0
            
            for session_row in session_rows:
                session_id = session_row['id']
                
                # Get memories for this session that fall within timeframe
                cursor.execute("""
                    SELECT m.uuid, m.content, m.created_at, sm.sequence_number
                    FROM session_memories sm
                    JOIN memories m ON m.id = sm.memory_id
                    WHERE sm.session_id = ?
                      AND m.created_at >= ?
                    ORDER BY sm.sequence_number ASC
                """, (session_id, threshold_iso))
                
                memory_rows = cursor.fetchall()
                
                if not memory_rows:
                    continue  # Skip sessions with no memories in timeframe
                
                memories = []
                for mem_row in memory_rows:
                    memories.append({
                        'id': mem_row['uuid'],
                        'content': mem_row['content'],
                        'timestamp': mem_row['created_at'],
                        'sequence': mem_row['sequence_number']
                    })
                
                total_memories += len(memories)
                
                session_data = {
                    'id': session_row['id'],
                    'start_time': session_row['start_time'],
                    'end_time': session_row['end_time'],
                    'is_active': bool(session_row['is_active']),
                    'memory_count': len(memories),
                    'memories': memories
                }
                
                # Add summary if requested
                if include_summaries and session_row['summary']:
                    session_data['summary'] = session_row['summary']
                
                # Add entity highlights if available
                if session_row['metadata']:
                    try:
                        metadata = json.loads(session_row['metadata'])
                        if 'entity_highlights' in metadata:
                            session_data['entity_highlights'] = metadata['entity_highlights']
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                sessions.append(session_data)
            
            return {
                'timeframe': timeframe_desc,
                'time_threshold': threshold_iso,
                'sessions': sessions,
                'total_sessions': len(sessions),
                'total_memories': total_memories
            }
            
        finally:
            conn.close()

    def reset(self) -> None:
        """Reset the entire memory system (all storages)."""
        self.memories = {}
        self._save_memories()
        self.vector_store.reset()
        
        # Reset SQLite
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_tags")
            cursor.execute("DELETE FROM memories")
            conn.commit()
            conn.close()
            logger.info("SQLite storage reset")
        except Exception as e:
            logger.error(f"Error resetting SQLite: {e}")
        
        logger.info("Memory system reset successfully (all storages cleared)")
    
