"""
Entity Type Manager - ENHANCED with Quality-Based Suggestions

NEW: Uses pre-computed quality scores for efficient, intelligent suggestions
- Tiered thresholds based on quality
- Max 15 suggestions (configurable)
- Scales to 1000+ memories efficiently
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
    quality_score: Optional[float] = None  # ← NEW: Average quality


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
    
    # *** ENHANCED: Quality-based thresholds ***
    TAG_FREQUENCY_THRESHOLD = 5  # Tags still need 5+ memories
    MAX_SUGGESTIONS = 15  # ← Configurable max suggestions
    
    # Quality-based tiered thresholds for noun phrases
    QUALITY_THRESHOLDS = {
        'high': {'min_quality': 5, 'min_frequency': 1},    # "Steins Gate" at freq=1
        'medium': {'min_quality': 3, 'min_frequency': 2},  # "transformer paper" at freq=2
        'low': {'min_quality': 0, 'min_frequency': 3},     # Generic phrases at freq=3
    }
    
    def __init__(self, db_path: str):
        """Initialize the entity type manager"""
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def suggest_entity_types(self) -> List[EntityTypeSuggestion]:
        """
        ENHANCED: Suggest new entity types with quality-based filtering
        
        Now uses pre-computed quality scores for fast, intelligent suggestions
        
        Returns:
            Top N suggestions, limited to MAX_SUGGESTIONS
        """
        suggestions = []
        
        # Get tag-based suggestions (unchanged)
        tag_suggestions = self._suggest_from_tags()
        suggestions.extend(tag_suggestions)
        
        # Get noun phrase-based suggestions (ENHANCED with quality filtering)
        noun_phrase_suggestions = self._suggest_from_noun_phrases_ENHANCED()
        suggestions.extend(noun_phrase_suggestions)
        
        # Sort by quality and confidence
        suggestions.sort(
            key=lambda s: (
                s.quality_score if s.quality_score else 0,  # Primary: quality
                s.confidence,  # Secondary: confidence
                s.occurrence_count  # Tertiary: frequency
            ),
            reverse=True
        )
        
        # Limit to MAX_SUGGESTIONS
        return suggestions[:self.MAX_SUGGESTIONS]
    
    def _suggest_from_tags(self) -> List[EntityTypeSuggestion]:
        """Suggest entity types from frequent tags (unchanged)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
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
            
            # Skip if already a core type or user-defined type
            if tag.lower() in self.CORE_TYPES or self._is_user_defined_type(tag):
                continue
            
            examples = self._get_tag_examples(cursor, tag, limit=3)
            confidence = min(0.7 + (memory_count / 100), 1.0)
            
            suggestions.append(EntityTypeSuggestion(
                type_name=tag,
                occurrence_count=memory_count,
                memory_count=memory_count,
                examples=examples,
                source='tag',
                confidence=confidence,
                quality_score=None  # Tags don't have quality scores
            ))
        
        conn.close()
        return suggestions
    
    def _suggest_from_noun_phrases_ENHANCED(self) -> List[EntityTypeSuggestion]:
        """
        ENHANCED: Suggest entity types using quality-based filtering
        
        Uses pre-computed quality scores from checkpoints for fast,
        intelligent suggestions with tiered thresholds.
        
        Strategy:
        - High quality (5+): Suggest at frequency=1 (e.g., "Steins Gate")
        - Medium quality (3-4): Suggest at frequency=2 (e.g., "transformer paper")
        - Low quality (0-2): Suggest at frequency=3 (e.g., "the thing")
        
        Returns:
            List of noun phrase-based suggestions
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # *** ENHANCED QUERY: Uses quality scores from checkpoints ***
        cursor.execute("""
            WITH checkpoint_phrases AS (
                -- Extract noun phrases from checkpoints with quality scores
                SELECT 
                    memory_id,
                    json_extract(value, '$.text') as phrase_text,
                    json_extract(value, '$.quality_score') as quality_score
                FROM entity_extraction_checkpoints,
                     json_each(noun_phrases)
                WHERE checkpoint_version >= 2  -- Only v2+ has quality scores
                  AND json_extract(value, '$.quality_score') IS NOT NULL
            ),
            aggregated AS (
                SELECT 
                    LOWER(phrase_text) as entity_text,
                    COUNT(*) as occurrence_count,
                    COUNT(DISTINCT memory_id) as memory_count,
                    AVG(CAST(quality_score AS REAL)) as avg_quality,
                    MAX(phrase_text) as display_text
                FROM checkpoint_phrases
                GROUP BY LOWER(phrase_text)
            )
            SELECT 
                entity_text,
                occurrence_count,
                memory_count,
                avg_quality,
                display_text
            FROM aggregated
            WHERE 
                -- Tiered thresholds based on quality
                (avg_quality >= ? AND occurrence_count >= ?) OR  -- High quality
                (avg_quality >= ? AND occurrence_count >= ?) OR  -- Medium quality
                (occurrence_count >= ?)                          -- Low quality fallback
            ORDER BY 
                avg_quality DESC,
                occurrence_count DESC
            LIMIT ?
        """, (
            self.QUALITY_THRESHOLDS['high']['min_quality'],
            self.QUALITY_THRESHOLDS['high']['min_frequency'],
            self.QUALITY_THRESHOLDS['medium']['min_quality'],
            self.QUALITY_THRESHOLDS['medium']['min_frequency'],
            self.QUALITY_THRESHOLDS['low']['min_frequency'],
            self.MAX_SUGGESTIONS * 2  # Fetch 2x, we'll filter more
        ))
        
        suggestions = []
        
        for row in cursor.fetchall():
            entity_text = row['entity_text']
            occurrence_count = row['occurrence_count']
            memory_count = row['memory_count']
            avg_quality = row['avg_quality']
            display_text = row['display_text']
            
            # Infer type name from entity text
            type_name = display_text.replace(' ', '_').lower()
            
            # Skip if already exists
            if self._is_user_defined_type(type_name):
                continue
            
            # Skip if it's already a core type
            if entity_text in self.CORE_TYPES:
                continue
            
            # Get examples
            examples = self._get_noun_phrase_examples(cursor, entity_text, limit=3)
            
            # Calculate confidence based on quality + frequency
            base_confidence = 0.5
            quality_boost = min(avg_quality * 0.1, 0.3)  # Up to +0.3 for quality
            frequency_boost = min(occurrence_count * 0.02, 0.2)  # Up to +0.2 for freq
            confidence = min(base_confidence + quality_boost + frequency_boost, 1.0)
            
            suggestions.append(EntityTypeSuggestion(
                type_name=type_name,
                occurrence_count=occurrence_count,
                memory_count=memory_count,
                examples=examples,
                source='noun_phrase',
                confidence=confidence,
                quality_score=avg_quality
            ))
        
        conn.close()
        return suggestions
    
    def get_rediscovery_suggestions(self, days_ago: int = 90, limit: int = 5) -> List[Dict]:
        """
        NEW: "New to You" / Rediscovery suggestions
        
        Find entities you mentioned frequently in the past but haven't
        mentioned recently - YouTube-style discovery.
        
        Args:
            days_ago: Minimum days since last mention (default: 90)
            limit: Max suggestions to return
        
        Returns:
            List of rediscovery suggestions
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                text,
                type,
                frequency,
                DATE(last_seen) as last_mention,
                CAST((JULIANDAY('now') - JULIANDAY(last_seen)) AS INTEGER) as days_ago
            FROM entities
            WHERE 
                type IS NULL  -- Untyped (could be made into entity type)
                AND frequency >= 3  -- Proven pattern
                AND JULIANDAY('now') - JULIANDAY(last_seen) >= ?  -- Not recent
                AND LOWER(text) NOT IN (
                    SELECT LOWER(type_name) FROM user_entity_types
                )  -- Not already added
            ORDER BY frequency DESC, days_ago DESC
            LIMIT ?
        """, (days_ago, limit))
        
        suggestions = []
        for row in cursor.fetchall():
            suggestions.append({
                'text': row['text'],
                'type': row['type'],
                'frequency': row['frequency'],
                'last_mention': row['last_mention'],
                'days_ago': row['days_ago']
            })
        
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
    
    def _get_noun_phrase_examples(
        self, 
        cursor: sqlite3.Cursor, 
        entity_text: str, 
        limit: int = 3
    ) -> List[str]:
        """Get example occurrences of a noun phrase from checkpoints"""
        cursor.execute("""
            SELECT DISTINCT 
                json_extract(value, '$.text') as phrase,
                json_extract(value, '$.context') as context
            FROM entity_extraction_checkpoints,
                 json_each(noun_phrases)
            WHERE LOWER(json_extract(value, '$.text')) = LOWER(?)
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
    
    # ... [Keep all other methods unchanged: add_entity_type, remove_entity_type, 
    #      list_entity_types, get_entity_type_stats, etc.]
    
    def add_entity_type(self, type_name: str) -> bool:
        """Add a new user-defined entity type"""
        # [Keep existing implementation]
        pass
    
    def remove_entity_type(self, type_name: str, force: bool = False) -> Tuple[bool, Optional[str]]:
        """Remove a user-defined entity type"""
        # [Keep existing implementation]
        pass
    
    def list_entity_types(self) -> Dict[str, List[EntityTypeStats]]:
        """List all entity types (core + user-defined) with statistics"""
        # [Keep existing implementation]
        pass


def main():
    """Test enhanced entity type manager"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python entity_type_manager_ENHANCED.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    print(f"\n{'='*70}")
    print("ENHANCED ENTITY TYPE MANAGER TEST (Quality-Based Suggestions)")
    print(f"{'='*70}\n")
    
    manager = EntityTypeManager(db_path)
    
    # Test suggestions
    print("📊 ENTITY TYPE SUGGESTIONS (Quality-Filtered):")
    print("-" * 70)
    suggestions = manager.suggest_entity_types()
    
    if not suggestions:
        print("No suggestions found.")
        print("\n💡 Make sure you:")
        print("  1. Have checkpoints with version 2+ (with quality scores)")
        print("  2. Have memories with noun phrases")
        print("  3. Have tags appearing on 5+ memories")
    else:
        for i, suggestion in enumerate(suggestions, 1):
            quality_indicator = ""
            if suggestion.quality_score:
                if suggestion.quality_score >= 5:
                    quality_indicator = "🔥"
                elif suggestion.quality_score >= 3:
                    quality_indicator = "✨"
                else:
                    quality_indicator = "💡"
            
            quality_str = f" [Q:{suggestion.quality_score:.1f}]" if suggestion.quality_score else ""
            
            print(f"\n{i}. {quality_indicator} {suggestion.type_name} ({suggestion.source}){quality_str}")
            print(f"   Occurrences: {suggestion.occurrence_count} | Confidence: {suggestion.confidence:.2f}")
            print(f"   Examples: {', '.join(suggestion.examples[:2])}")
    
    print(f"\n{'='*70}")
    
    # Test rediscovery
    print("\n💭 REDISCOVERY SUGGESTIONS (\"New to You\"):")
    print("-" * 70)
    rediscovery = manager.get_rediscovery_suggestions(days_ago=90, limit=5)
    
    if not rediscovery:
        print("No rediscovery suggestions found.")
        print("(You need entities with frequency >= 3 not seen in 90+ days)")
    else:
        for i, item in enumerate(rediscovery, 1):
            print(f"{i}. {item['text']}")
            print(f"   Mentioned {item['frequency']} times")
            print(f"   Last seen: {item['last_mention']} ({item['days_ago']} days ago)")
            print()
    
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()