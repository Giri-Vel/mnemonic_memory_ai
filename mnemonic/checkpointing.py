"""
Entity Extraction Checkpointing System - ENHANCED with Quality Scoring

NEW: Adds quality_score to noun phrases for efficient suggestion filtering

Stores pre-computed noun phrases and context to enable fast re-extraction
when new entity types are added.
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
CHECKPOINT_VERSION = 2  # ← BUMPED from 1 to 2 (includes quality_score)
CORE_LABELS = ["person", "organization", "location", "date"]


def calculate_quality_score(text: str, pos_tags: List[str]) -> int:
    """
    Calculate quality score for a noun phrase
    
    Fast heuristic-based scoring (no extra NLP processing needed)
    
    Scoring rules:
    - Proper noun (PROPN/NNP): +3 points
    - Multi-word phrase (2+ words): +2 points
    - Title case: +1 point
    - Contains short words (<3 chars): -1 point
    - Single character words: -2 points
    
    Args:
        text: Noun phrase text
        pos_tags: POS tags from spaCy
    
    Returns:
        Quality score (higher = better quality)
    """
    score = 0
    words = text.split()
    
    # Rule 1: Proper nouns are high value
    if any(tag in ['PROPN', 'NNP'] for tag in pos_tags):
        score += 3
    
    # Rule 2: Multi-word phrases are more specific
    if len(words) >= 2:
        score += 2
    
    # Rule 3: Title case indicates proper nouns
    if text.istitle():
        score += 1
    
    # Rule 4: Penalize very short words (likely generic)
    for word in words:
        if len(word) < 3:
            score -= 1
        if len(word) == 1:
            score -= 1  # Extra penalty for single chars
    
    # Rule 5: Common stopword phrases (future enhancement)
    # Could add a blacklist here
    
    return max(0, score)  # Never go below 0


class CheckpointManager:
    """
    Manages entity extraction checkpoints for fast re-extraction
    
    ENHANCED: Now stores quality scores for efficient suggestion filtering
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
        Create checkpoint for a memory with quality scoring
        
        ENHANCED: Now includes quality_score for each noun phrase
        
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
            # Extract noun phrases with context AND quality scores
            noun_phrases = self._extract_noun_phrases_with_quality(text)
            
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
                CHECKPOINT_VERSION,  # Version 2 with quality scores
                json.dumps(config)
            ))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to create checkpoint for memory {memory_id}: {e}")
            return False
    
    def _extract_noun_phrases_with_quality(self, text: str) -> List[Dict]:
        """
        Extract noun phrases with surrounding context AND quality scores
        
        ENHANCED: Now includes quality_score field
        
        Args:
            text: Text to extract from
        
        Returns:
            List of dictionaries with noun phrase data including quality_score
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
            
            # *** NEW: Calculate quality score ***
            quality_score = calculate_quality_score(chunk_text, pos_tags)
            
            noun_phrases.append({
                "text": chunk_text,
                "context": context,
                "pos_tags": pos_tags,
                "span": [chunk.start_char, chunk.end_char],
                "quality_score": quality_score  # ← NEW FIELD!
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
        
        # Handle version compatibility
        # Version 1: No quality scores
        # Version 2: Has quality scores
        
        noun_phrases = json.loads(noun_phrases_json)
        
        # Backfill quality scores for old checkpoints (version 1)
        if version == 1:
            for phrase in noun_phrases:
                if 'quality_score' not in phrase:
                    # Recalculate quality score from stored POS tags
                    phrase['quality_score'] = calculate_quality_score(
                        phrase['text'],
                        phrase.get('pos_tags', [])
                    )
        
        return {
            "memory_id": memory_id,
            "noun_phrases": noun_phrases,
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
        from mnemonic.entity_extractor import Entity
        
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
    """Test checkpointing system with quality scoring"""
    import sys
    from mnemonic.entity_extractor import Entity, EntityExtractor
    
    if len(sys.argv) < 2:
        print("Usage: python checkpointing_ENHANCED.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    print(f"\n{'='*60}")
    print("ENHANCED CHECKPOINTING SYSTEM TEST (with Quality Scoring)")
    print(f"{'='*60}\n")
    
    manager = CheckpointManager(db_path)
    
    # Test text
    test_text = "Met Sarah Chen at the AI conference in Tokyo. She sent me a paper about Steins Gate and transformer architectures."
    test_entities = [
        Entity("ai", "tag", "tag", 1.0),
        Entity("research", "tag", "tag", 1.0)
    ]
    
    print(f"Text: {test_text}\n")
    
    # Create checkpoint
    print("Creating checkpoint with quality scoring...")
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
            print(f"Checkpoint version: {checkpoint['version']}")
            print(f"Noun phrases stored: {len(checkpoint['noun_phrases'])}\n")
            
            # Show phrases with quality scores
            print("Noun Phrases with Quality Scores:")
            print("-" * 60)
            for phrase in sorted(checkpoint['noun_phrases'], key=lambda p: p.get('quality_score', 0), reverse=True):
                quality = phrase.get('quality_score', 0)
                text = phrase['text']
                pos = ', '.join(phrase['pos_tags'])
                
                # Visual quality indicator
                if quality >= 5:
                    indicator = "🔥"
                elif quality >= 3:
                    indicator = "✨"
                elif quality >= 1:
                    indicator = "💡"
                else:
                    indicator = "  "
                
                print(f"{indicator} [{quality:2d}] {text:30s} ({pos})")
            
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
    print(f"  Current version (v{CHECKPOINT_VERSION}): {stats['current_version_count']}")
    print(f"  Outdated: {stats['outdated_count']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()