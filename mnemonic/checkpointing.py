"""
Entity Extraction Checkpointing System

Stores pre-computed noun phrases and context to enable fast re-extraction
when new entity types are added.

Instead of re-processing full text (100ms), we can classify stored 
noun phrases (~1-2ms per memory).
"""

import sqlite3
import json
from typing import List, Dict, Optional

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False


# Constants
CHECKPOINT_VERSION = 1
CORE_LABELS = ["person", "organization", "location", "date"]


class CheckpointManager:
    """
    Manages entity extraction checkpoints for fast re-extraction
    
    Checkpoints store:
    - Noun phrases with surrounding context
    - Tags (for context)
    - Extraction configuration (model versions, labels used)
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.nlp = None
        self._init_spacy()
    
    def _init_spacy(self):
        """Initialize spaCy for noun phrase extraction"""
        if not SPACY_AVAILABLE:
            print("⚠ spaCy not available - checkpointing disabled")
            return
        
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("⚠ spaCy model not found - checkpointing will be limited")
            self.nlp = None
    
    def create_checkpoint(
        self,
        memory_id: int,
        text: str,
        entities: List,  # List of Entity objects
        user_labels: List[str]
    ) -> bool:
        """
        Create checkpoint for a memory
        
        Args:
            memory_id: Memory ID
            text: Original memory text
            entities: Extracted entities
            user_labels: Current user-defined entity types
        
        Returns:
            True if successful, False otherwise
        """
        if not self.nlp:
            return False
        
        try:
            # Extract noun phrases with context
            noun_phrases = self._extract_noun_phrases_with_context(text)
            
            # Extract tags from entities
            tags = [e.text for e in entities if e.type_source == "tag"]
            
            # Build extraction config
            config = {
                "gliner_model": "small-v2.1",
                "confidence_threshold": 0.7,
                "core_labels": CORE_LABELS,
                "user_labels": user_labels.copy()
            }
            
            # Store checkpoint
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO entity_extraction_checkpoints
                (memory_id, noun_phrases, tags, checkpoint_version, extraction_config)
                VALUES (?, ?, ?, ?, ?)
            """, (
                memory_id,
                json.dumps(noun_phrases),
                json.dumps(tags),
                CHECKPOINT_VERSION,
                json.dumps(config)
            ))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to create checkpoint for memory {memory_id}: {e}")
            return False
    
    def _extract_noun_phrases_with_context(self, text: str) -> List[Dict]:
        """
        Extract noun phrases with surrounding context
        
        Args:
            text: Text to extract from
        
        Returns:
            List of dictionaries with noun phrase data
        """
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        noun_phrases = []
        
        for chunk in doc.noun_chunks:
            chunk_text = chunk.text.strip()
            
            # Skip very short phrases
            if len(chunk_text) <= 2:
                continue
            
            # Get context (10 chars before/after)
            start_idx = max(0, chunk.start_char - 10)
            end_idx = min(len(text), chunk.end_char + 10)
            context = text[start_idx:end_idx]
            
            # Get POS tags
            pos_tags = [token.pos_ for token in chunk]
            
            noun_phrases.append({
                "text": chunk_text,
                "context": context,
                "pos_tags": pos_tags,
                "span": [chunk.start_char, chunk.end_char]
            })
        
        return noun_phrases
    
    def load_checkpoint(self, memory_id: int) -> Optional[Dict]:
        """
        Load checkpoint for a memory
        
        Args:
            memory_id: Memory ID
        
        Returns:
            Checkpoint data dictionary or None if not found/invalid
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT noun_phrases, tags, checkpoint_version, extraction_config
            FROM entity_extraction_checkpoints
            WHERE memory_id = ?
        """, (memory_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        noun_phrases_json, tags_json, version, config_json = result
        
        # Check version compatibility
        if version != CHECKPOINT_VERSION:
            return None
        
        return {
            "memory_id": memory_id,
            "noun_phrases": json.loads(noun_phrases_json),
            "tags": json.loads(tags_json) if tags_json else [],
            "version": version,
            "config": json.loads(config_json) if config_json else {}
        }
    
    def fast_extract(
        self,
        checkpoint: Dict,
        new_entity_type: str,
        gliner_model
    ) -> List:
        """
        Fast re-extraction using checkpoint data
        
        Args:
            checkpoint: Checkpoint data from load_checkpoint()
            new_entity_type: New entity type to extract
            gliner_model: GLiNER model instance
        
        Returns:
            List of Entity objects (import Entity from entity_extractor)
        """
        from entity_extractor import Entity
        
        entities = []
        
        # Classify each stored noun phrase
        for phrase_data in checkpoint["noun_phrases"]:
            try:
                # Use context for better classification
                results = gliner_model.predict_entities(
                    phrase_data["context"],
                    [new_entity_type]
                )
                
                for result in results:
                    # Match the noun phrase text
                    if result["text"] == phrase_data["text"] and result["score"] > 0.7:
                        entities.append(Entity(
                            text=result["text"],
                            type=new_entity_type,
                            type_source="user_defined",
                            confidence=result["score"],
                            context=phrase_data["context"]
                        ))
            
            except Exception as e:
                # Skip problematic phrases
                continue
        
        return entities
    
    def get_checkpoint_stats(self) -> Dict:
        """
        Get statistics about checkpoints
        
        Returns:
            Dictionary with stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total checkpoints
        cursor.execute("SELECT COUNT(*) FROM entity_extraction_checkpoints")
        stats['total_checkpoints'] = cursor.fetchone()[0]
        
        # By version
        cursor.execute("""
            SELECT checkpoint_version, COUNT(*) as count
            FROM entity_extraction_checkpoints
            GROUP BY checkpoint_version
        """)
        
        stats['by_version'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Current version count
        stats['current_version_count'] = stats['by_version'].get(CHECKPOINT_VERSION, 0)
        stats['outdated_count'] = stats['total_checkpoints'] - stats['current_version_count']
        
        conn.close()
        
        return stats
    
    def cleanup_outdated_checkpoints(self) -> int:
        """
        Remove checkpoints with outdated versions
        
        Returns:
            Number of checkpoints deleted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM entity_extraction_checkpoints
            WHERE checkpoint_version != ?
        """, (CHECKPOINT_VERSION,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count


def main():
    """Test checkpointing system"""
    import sys
    from entity_extractor import Entity, EntityExtractor
    
    if len(sys.argv) < 2:
        print("Usage: python checkpointing.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    print(f"\n{'='*60}")
    print("CHECKPOINTING SYSTEM TEST")
    print(f"{'='*60}\n")
    
    manager = CheckpointManager(db_path)
    
    # Test text
    test_text = "Met Sarah at the AI conference in Tokyo. She sent me a paper on transformers."
    test_entities = [
        Entity("ai", "tag", "tag", 1.0),
        Entity("research", "tag", "tag", 1.0)
    ]
    
    print(f"Text: {test_text}\n")
    
    # Create checkpoint
    print("Creating checkpoint...")
    success = manager.create_checkpoint(
        memory_id=999,
        text=test_text,
        entities=test_entities,
        user_labels=[]
    )
    
    if success:
        print("✓ Checkpoint created\n")
        
        # Load checkpoint
        print("Loading checkpoint...")
        checkpoint = manager.load_checkpoint(999)
        
        if checkpoint:
            print("✓ Checkpoint loaded\n")
            print(f"Noun phrases stored: {len(checkpoint['noun_phrases'])}")
            for phrase in checkpoint['noun_phrases']:
                print(f"  - {phrase['text']}")
            print()
        else:
            print("✗ Failed to load checkpoint\n")
    else:
        print("✗ Failed to create checkpoint\n")
    
    # Show stats
    print(f"{'='*60}")
    stats = manager.get_checkpoint_stats()
    print("CHECKPOINT STATS:")
    print(f"  Total checkpoints: {stats['total_checkpoints']}")
    print(f"  Current version: {stats['current_version_count']}")
    print(f"  Outdated: {stats['outdated_count']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()