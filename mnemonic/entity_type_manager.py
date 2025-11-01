"""
Entity Type Manager - Dynamic entity type management for Mnemonic

Handles:
- Suggesting new entity types based on patterns in memories
- CRUD operations for user-defined entity types
- Re-extraction queue management (Day 7)
- Background re-extraction coordination (Day 8)

Day 7 Focus: Suggestion logic + CRUD + queue infrastructure
"""

import sqlite3
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import Counter
import json


@dataclass
class EntityTypeSuggestion:
    """Represents a suggested entity type based on pattern analysis"""
    type_name: str
    occurrence_count: int
    memory_count: int
    examples: List[str]
    source: str  # 'tag' or 'noun_phrase'
    confidence: float  # 0.0 to 1.0


@dataclass
class EntityTypeStats:
    """Statistics for a user-defined entity type"""
    type_name: str
    entity_count: int
    memory_count: int
    examples: List[str]
    added_at: str


class EntityTypeManager:
    """Manages user-defined entity types and suggestions"""
    
    # Core entity types that are always active
    CORE_TYPES = {'person', 'organization', 'location', 'date'}
    
    # Thresholds for suggestions (agreed upon in planning)
    TAG_FREQUENCY_THRESHOLD = 5  # Suggest tag if appears on 5+ memories
    NOUN_PHRASE_THRESHOLD = 3     # Suggest noun phrase if appears 3+ times
    MAX_SUGGESTIONS = 10          # Return top N suggestions
    
    def __init__(self, db_path: str):
        """
        Initialize the entity type manager
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def suggest_entity_types(self) -> List[EntityTypeSuggestion]:
        """
        Suggest new entity types based on patterns in memories
        
        Analyzes:
        1. Tag frequency - frequent tags become entity types
        2. Noun phrase emergence - recurring untyped entities
        
        Returns:
            List of EntityTypeSuggestion objects, sorted by confidence
        """
        suggestions = []
        
        # Get tag-based suggestions
        tag_suggestions = self._suggest_from_tags()
        suggestions.extend(tag_suggestions)
        
        # Get noun phrase-based suggestions
        noun_phrase_suggestions = self._suggest_from_noun_phrases()
        suggestions.extend(noun_phrase_suggestions)
        
        # Sort by confidence (occurrence count weighted by source)
        suggestions.sort(key=lambda s: (s.confidence, s.occurrence_count), reverse=True)
        
        # Return top N
        return suggestions[:self.MAX_SUGGESTIONS]
    
    def _suggest_from_tags(self) -> List[EntityTypeSuggestion]:
        """
        Suggest entity types from frequent tags
        
        Strategy: Tags appearing on 5+ memories become entity type candidates
        
        Returns:
            List of tag-based suggestions
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get tag frequency across memories
        cursor.execute("""
            SELECT 
                tag,
                COUNT(DISTINCT memory_id) as memory_count,
                COUNT(*) as total_occurrences
            FROM memory_tags
            GROUP BY tag
            HAVING memory_count >= ?
            ORDER BY memory_count DESC
        """, (self.TAG_FREQUENCY_THRESHOLD,))
        
        suggestions = []
        
        for row in cursor.fetchall():
            tag = row['tag']
            memory_count = row['memory_count']
            
            # Skip if already a core type
            if tag.lower() in self.CORE_TYPES:
                continue
            
            # Skip if already a user-defined type
            if self._is_user_defined_type(tag):
                continue
            
            # Get example memories with this tag
            examples = self._get_tag_examples(cursor, tag, limit=3)
            
            # Calculate confidence (higher frequency = higher confidence)
            confidence = min(0.7 + (memory_count / 100), 1.0)
            
            suggestions.append(EntityTypeSuggestion(
                type_name=tag,
                occurrence_count=memory_count,
                memory_count=memory_count,
                examples=examples,
                source='tag',
                confidence=confidence
            ))
        
        conn.close()
        return suggestions
    
    def _suggest_from_noun_phrases(self) -> List[EntityTypeSuggestion]:
        """
        Suggest entity types from recurring untyped noun phrases
        
        Strategy: Untyped entities appearing 3+ times become candidates
        
        Returns:
            List of noun phrase-based suggestions
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get high-frequency untyped entities from tentative table
        cursor.execute("""
            SELECT 
                LOWER(text) as entity_text,
                COUNT(*) as occurrence_count,
                COUNT(DISTINCT memory_id) as memory_count
            FROM tentative_entities
            WHERE type IS NULL AND type_source = 'noun_phrase'
            GROUP BY LOWER(text)
            HAVING occurrence_count >= ?
            ORDER BY occurrence_count DESC
        """, (self.NOUN_PHRASE_THRESHOLD,))
        
        suggestions = []
        
        for row in cursor.fetchall():
            entity_text = row['entity_text']
            occurrence_count = row['occurrence_count']
            memory_count = row['memory_count']
            
            # Try to infer a good type name from the entity text
            # For now, just use the entity text as the type name
            # Future: Could use GPT/Claude to infer better type names
            type_name = entity_text.replace(' ', '_')
            
            # Skip if already exists
            if self._is_user_defined_type(type_name):
                continue
            
            # Get examples
            examples = self._get_noun_phrase_examples(cursor, entity_text, limit=3)
            
            # Calculate confidence (3+ occurrences = decent confidence)
            confidence = min(0.6 + (occurrence_count / 20), 0.95)
            
            suggestions.append(EntityTypeSuggestion(
                type_name=type_name,
                occurrence_count=occurrence_count,
                memory_count=memory_count,
                examples=examples,
                source='noun_phrase',
                confidence=confidence
            ))
        
        conn.close()
        return suggestions
    
    def _get_tag_examples(self, cursor: sqlite3.Cursor, tag: str, limit: int = 3) -> List[str]:
        """Get example entity texts for a tag"""
        cursor.execute("""
            SELECT DISTINCT m.content
            FROM memories m
            JOIN memory_tags mt ON m.id = mt.memory_id
            WHERE mt.tag = ?
            LIMIT ?
        """, (tag, limit))
        
        return [row[0][:50] for row in cursor.fetchall()]
    
    def _get_noun_phrase_examples(self, cursor: sqlite3.Cursor, entity_text: str, limit: int = 3) -> List[str]:
        """Get example contexts for a noun phrase"""
        cursor.execute("""
            SELECT DISTINCT text
            FROM tentative_entities
            WHERE LOWER(text) = LOWER(?)
            LIMIT ?
        """, (entity_text, limit))
        
        return [row[0] for row in cursor.fetchall()]
    
    def _is_user_defined_type(self, type_name: str) -> bool:
        """Check if a type already exists as user-defined"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM user_entity_types
            WHERE LOWER(type_name) = LOWER(?)
        """, (type_name,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    # CRUD Operations
    
    def add_entity_type(self, type_name: str) -> bool:
        """
        Add a new user-defined entity type
        
        Args:
            type_name: Name of the entity type
        
        Returns:
            True if added successfully, False if already exists
        """
        # Validate type name
        if not type_name or not type_name.strip():
            raise ValueError("Entity type name cannot be empty")
        
        type_name = type_name.strip().lower()
        
        # Check if already exists
        if self._is_user_defined_type(type_name):
            return False
        
        # Check if it's a core type
        if type_name in self.CORE_TYPES:
            raise ValueError(f"'{type_name}' is a core entity type and cannot be added")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO user_entity_types (type_name, memory_count)
                VALUES (?, 0)
            """, (type_name,))
            
            conn.commit()
            
            # Queue re-extraction (will be processed by Day 8's background worker)
            self._queue_reextraction(type_name)
            
            return True
            
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def remove_entity_type(self, type_name: str, force: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Remove a user-defined entity type
        
        Args:
            type_name: Name of the entity type to remove
            force: If True, remove even if used in memories
        
        Returns:
            Tuple of (success, warning_message)
        """
        type_name = type_name.strip().lower()
        
        # Check if it exists
        if not self._is_user_defined_type(type_name):
            return False, "Entity type does not exist"
        
        # Check if it's being used
        usage_count = self._get_type_usage_count(type_name)
        
        if usage_count > 0 and not force:
            return False, f"Entity type is used in {usage_count} memories. Use force=True to remove anyway."
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Remove from user_entity_types
            cursor.execute("""
                DELETE FROM user_entity_types
                WHERE LOWER(type_name) = LOWER(?)
            """, (type_name,))
            
            conn.commit()
            
            warning = None
            if usage_count > 0:
                warning = f"Removed entity type. {usage_count} entities with this type are now orphaned."
            
            return True, warning
            
        except Exception as e:
            conn.rollback()
            return False, f"Error removing entity type: {e}"
        finally:
            conn.close()
    
    def list_entity_types(self) -> Dict[str, List[EntityTypeStats]]:
        """
        List all entity types (core + user-defined) with statistics
        
        Returns:
            Dictionary with 'core' and 'user_defined' lists
        """
        result = {
            'core': [],
            'user_defined': []
        }
        
        # Core types (no stats needed, they're always there)
        for core_type in sorted(self.CORE_TYPES):
            result['core'].append(EntityTypeStats(
                type_name=core_type,
                entity_count=self._count_entities_by_type(core_type),
                memory_count=0,  # Not tracked for core types
                examples=[],
                added_at=""
            ))
        
        # User-defined types
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT type_name, memory_count, added_at
            FROM user_entity_types
            ORDER BY type_name
        """)
        
        for row in cursor.fetchall():
            type_name = row['type_name']
            
            result['user_defined'].append(EntityTypeStats(
                type_name=type_name,
                entity_count=self._count_entities_by_type(type_name),
                memory_count=row['memory_count'],
                examples=self._get_type_examples(type_name, limit=3),
                added_at=row['added_at']
            ))
        
        conn.close()
        return result
    
    def get_entity_type_stats(self, type_name: str) -> Optional[EntityTypeStats]:
        """
        Get detailed statistics for a specific entity type
        
        Args:
            type_name: Name of the entity type
        
        Returns:
            EntityTypeStats object or None if not found
        """
        type_name = type_name.strip().lower()
        
        # Check if it's a core type
        if type_name in self.CORE_TYPES:
            return EntityTypeStats(
                type_name=type_name,
                entity_count=self._count_entities_by_type(type_name),
                memory_count=0,
                examples=self._get_type_examples(type_name, limit=5),
                added_at="core"
            )
        
        # Check user-defined types
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT type_name, memory_count, added_at
            FROM user_entity_types
            WHERE LOWER(type_name) = LOWER(?)
        """, (type_name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return EntityTypeStats(
            type_name=row['type_name'],
            entity_count=self._count_entities_by_type(type_name),
            memory_count=row['memory_count'],
            examples=self._get_type_examples(type_name, limit=5),
            added_at=row['added_at']
        )
    
    # Helper methods
    
    def _get_type_usage_count(self, type_name: str) -> int:
        """Count how many entities use this type"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM entities
            WHERE LOWER(type) = LOWER(?)
        """, (type_name,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def _count_entities_by_type(self, type_name: str) -> int:
        """Count confirmed entities of this type"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM entities
            WHERE LOWER(type) = LOWER(?)
        """, (type_name,))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def _get_type_examples(self, type_name: str, limit: int = 3) -> List[str]:
        """Get example entities of this type"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT text FROM entities
            WHERE LOWER(type) = LOWER(?)
            ORDER BY frequency DESC
            LIMIT ?
        """, (type_name, limit))
        
        examples = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return examples
    
    def _queue_reextraction(self, type_name: str) -> None:
        """
        Queue re-extraction for a new entity type
        
        This creates a job that will be processed by Day 8's background worker
        
        Args:
            type_name: Entity type to re-extract
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO reextraction_queue (type_name, status, queued_at)
                VALUES (?, 'pending', CURRENT_TIMESTAMP)
            """, (type_name,))
            
            conn.commit()
        except Exception as e:
            print(f"⚠ Failed to queue re-extraction for '{type_name}': {e}")
            conn.rollback()
        finally:
            conn.close()


def main():
    """Test entity type manager"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python entity_type_manager.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    print(f"\n{'='*60}")
    print("ENTITY TYPE MANAGER TEST")
    print(f"{'='*60}\n")
    
    manager = EntityTypeManager(db_path)
    
    # Test suggestions
    print("📊 ENTITY TYPE SUGGESTIONS:")
    print("-" * 60)
    suggestions = manager.suggest_entity_types()
    
    if not suggestions:
        print("No suggestions found. Add more memories with tags!")
    else:
        for i, suggestion in enumerate(suggestions, 1):
            print(f"\n{i}. {suggestion.type_name} ({suggestion.source})")
            print(f"   Occurrences: {suggestion.occurrence_count}")
            print(f"   Memories: {suggestion.memory_count}")
            print(f"   Confidence: {suggestion.confidence:.2f}")
            print(f"   Examples: {', '.join(suggestion.examples[:2])}")
    
    print(f"\n{'='*60}")
    
    # Test listing
    print("\n📋 CURRENT ENTITY TYPES:")
    print("-" * 60)
    types = manager.list_entity_types()
    
    print(f"\nCore types ({len(types['core'])}):")
    for et in types['core']:
        print(f"  - {et.type_name} ({et.entity_count} entities)")
    
    print(f"\nUser-defined types ({len(types['user_defined'])}):")
    if not types['user_defined']:
        print("  (none)")
    else:
        for et in types['user_defined']:
            print(f"  - {et.type_name} ({et.entity_count} entities, {et.memory_count} memories)")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()