"""
Entity-Based Search System (Week 4, Day 1)

Provides intelligent search and filtering based on extracted entities:
- Search memories by entity
- Filter by entity type
- Find entity co-occurrences
- Get entity context and mentions

This is the foundation for relationship graphs and timeline analysis.
"""

import sqlite3
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict, Counter


@dataclass
class EntityMention:
    """Represents a single mention of an entity in a memory"""
    entity_text: str
    entity_type: Optional[str]
    memory_id: int
    memory_content: str
    memory_timestamp: str
    context: Optional[str] = None
    confidence: float = 0.0


@dataclass
class EntitySearchResult:
    """Result from entity-based search"""
    entity_text: str
    entity_type: Optional[str]
    frequency: int
    memory_count: int
    mentions: List[EntityMention]
    co_occurring_entities: Optional[Dict[str, int]] = None


@dataclass
class CoOccurrence:
    """Represents two entities appearing together"""
    entity1: str
    entity2: str
    co_occurrence_count: int
    memories: List[int]  # Memory IDs where they co-occur


class EntitySearchEngine:
    """
    Advanced search engine for entity-based queries
    
    Features:
    - Search memories containing specific entities
    - Filter by entity type
    - Find entity co-occurrences (foundation for graphs)
    - Get contextual mentions
    - Calculate entity statistics
    """
    
    def __init__(self, db_path: str):
        """
        Initialize entity search engine
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def search_by_entity(
        self,
        entity_text: str,
        entity_type: Optional[str] = None,
        min_confidence: float = 0.0,
        include_co_occurrences: bool = False
    ) -> Optional[EntitySearchResult]:
        """
        Search for all memories containing a specific entity
        
        Args:
            entity_text: Entity to search for
            entity_type: Filter by entity type (optional)
            min_confidence: Minimum confidence threshold
            include_co_occurrences: Include entities that co-occur with this one
        
        Returns:
            EntitySearchResult or None if entity not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT 
                e.text as entity_text,
                e.type as entity_type,
                e.frequency,
                e.confidence,
                m.id as memory_id,
                m.content as memory_content,
                m.created_at as memory_timestamp
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE LOWER(e.text) = LOWER(?)
                AND e.confidence >= ?
        """
        
        params = [entity_text, min_confidence]
        
        if entity_type:
            query += " AND e.type = ?"
            params.append(entity_type)
        
        query += " ORDER BY m.created_at DESC"
        
        cursor.execute(query, params)
        
        rows = cursor.fetchall()
        
        if not rows:
            conn.close()
            return None
        
        # Build mentions list
        mentions = []
        memory_ids = set()
        
        for row in rows:
            mention = EntityMention(
                entity_text=row['entity_text'],
                entity_type=row['entity_type'],
                memory_id=row['memory_id'],
                memory_content=row['memory_content'],
                memory_timestamp=row['memory_timestamp'],
                confidence=row['confidence']
            )
            mentions.append(mention)
            memory_ids.add(row['memory_id'])
        
        # Get entity stats
        first_row = rows[0]
        
        result = EntitySearchResult(
            entity_text=first_row['entity_text'],
            entity_type=first_row['entity_type'],
            frequency=first_row['frequency'],
            memory_count=len(memory_ids),
            mentions=mentions
        )
        
        # Optionally find co-occurring entities
        if include_co_occurrences:
            result.co_occurring_entities = self._find_co_occurrences_for_entity(
                cursor, 
                list(memory_ids)
            )
        
        conn.close()
        
        return result
    
    def _find_co_occurrences_for_entity(
        self,
        cursor: sqlite3.Cursor,
        memory_ids: List[int]
    ) -> Dict[str, int]:
        """
        Find entities that co-occur with the searched entity
        
        Args:
            cursor: Database cursor
            memory_ids: Memory IDs where the entity appears
        
        Returns:
            Dictionary mapping entity text to co-occurrence count
        """
        if not memory_ids:
            return {}
        
        placeholders = ','.join('?' * len(memory_ids))
        
        cursor.execute(f"""
            SELECT 
                text,
                COUNT(DISTINCT memory_id) as co_occurrence_count
            FROM entities
            WHERE memory_id IN ({placeholders})
            GROUP BY LOWER(text)
            ORDER BY co_occurrence_count DESC
            LIMIT 20
        """, memory_ids)
        
        co_occurrences = {}
        for row in cursor.fetchall():
            co_occurrences[row['text']] = row['co_occurrence_count']
        
        return co_occurrences
    
    def search_by_type(
        self,
        entity_type: str,
        min_frequency: int = 1,
        limit: int = 50
    ) -> List[EntitySearchResult]:
        """
        Search for all entities of a specific type
        
        Args:
            entity_type: Entity type to search for
            min_frequency: Minimum frequency threshold
            limit: Maximum number of results
        
        Returns:
            List of EntitySearchResult objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                text,
                type,
                frequency,
                COUNT(DISTINCT memory_id) as memory_count
            FROM entities
            WHERE type = ?
                AND frequency >= ?
            GROUP BY LOWER(text), type
            ORDER BY frequency DESC
            LIMIT ?
        """, (entity_type, min_frequency, limit))
        
        results = []
        
        for row in cursor.fetchall():
            # Get mentions for this entity
            cursor.execute("""
                SELECT 
                    e.text as entity_text,
                    e.type as entity_type,
                    e.confidence,
                    m.id as memory_id,
                    m.content as memory_content,
                    m.created_at as memory_timestamp
                FROM entities e
                JOIN memories m ON e.memory_id = m.id
                WHERE LOWER(e.text) = LOWER(?)
                    AND e.type = ?
                ORDER BY m.created_at DESC
            """, (row['text'], entity_type))
            
            mentions = []
            for mention_row in cursor.fetchall():
                mention = EntityMention(
                    entity_text=mention_row['entity_text'],
                    entity_type=mention_row['entity_type'],
                    memory_id=mention_row['memory_id'],
                    memory_content=mention_row['memory_content'],
                    memory_timestamp=mention_row['memory_timestamp'],
                    confidence=mention_row['confidence']
                )
                mentions.append(mention)
            
            result = EntitySearchResult(
                entity_text=row['text'],
                entity_type=row['type'],
                frequency=row['frequency'],
                memory_count=row['memory_count'],
                mentions=mentions
            )
            
            results.append(result)
        
        conn.close()
        
        return results
    
    def find_co_occurrences(
        self,
        min_co_occurrence: int = 2,
        entity_type: Optional[str] = None,
        limit: int = 100
    ) -> List[CoOccurrence]:
        """
        Find pairs of entities that frequently appear together
        
        This is the foundation for relationship graphs!
        
        Args:
            min_co_occurrence: Minimum number of times entities must co-occur
            entity_type: Filter by entity type (optional)
            limit: Maximum number of co-occurrence pairs
        
        Returns:
            List of CoOccurrence objects sorted by frequency
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build query to find entity pairs in same memories
        type_filter = ""
        params = []
        
        if entity_type:
            type_filter = "AND e1.type = ? AND e2.type = ?"
            params = [entity_type, entity_type]
        
        query = f"""
            SELECT 
                e1.text as entity1,
                e2.text as entity2,
                COUNT(DISTINCT e1.memory_id) as co_occurrence_count,
                GROUP_CONCAT(DISTINCT e1.memory_id) as memory_ids
            FROM entities e1
            JOIN entities e2 ON e1.memory_id = e2.memory_id
            WHERE e1.id < e2.id  -- Avoid duplicates (A,B) vs (B,A)
                AND LOWER(e1.text) != LOWER(e2.text)  -- Different entities
                {type_filter}
            GROUP BY LOWER(e1.text), LOWER(e2.text)
            HAVING co_occurrence_count >= ?
            ORDER BY co_occurrence_count DESC
            LIMIT ?
        """
        
        params.extend([min_co_occurrence, limit])
        
        cursor.execute(query, params)
        
        co_occurrences = []
        
        for row in cursor.fetchall():
            memory_ids = [int(x) for x in row['memory_ids'].split(',')]
            
            co_occurrence = CoOccurrence(
                entity1=row['entity1'],
                entity2=row['entity2'],
                co_occurrence_count=row['co_occurrence_count'],
                memories=memory_ids
            )
            
            co_occurrences.append(co_occurrence)
        
        conn.close()
        
        return co_occurrences
    
    def get_entity_statistics(self) -> Dict:
        """
        Get overall entity statistics
        
        Returns:
            Dictionary with entity stats
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Total entities
        cursor.execute("SELECT COUNT(*) FROM entities")
        stats['total_entities'] = cursor.fetchone()[0]
        
        # Entities by type
        cursor.execute("""
            SELECT type, COUNT(*) as count
            FROM entities
            GROUP BY type
            ORDER BY count DESC
        """)
        
        stats['by_type'] = {}
        for row in cursor.fetchall():
            entity_type = row['type'] or 'untyped'
            stats['by_type'][entity_type] = row['count']
        
        # Top entities by frequency
        cursor.execute("""
            SELECT text, type, frequency
            FROM entities
            ORDER BY frequency DESC
            LIMIT 10
        """)
        
        stats['top_entities'] = []
        for row in cursor.fetchall():
            stats['top_entities'].append({
                'text': row['text'],
                'type': row['type'],
                'frequency': row['frequency']
            })
        
        # Co-occurrence statistics
        cursor.execute("""
            SELECT COUNT(*) as pair_count
            FROM (
                SELECT e1.text, e2.text, COUNT(*) as cnt
                FROM entities e1
                JOIN entities e2 ON e1.memory_id = e2.memory_id
                WHERE e1.id < e2.id
                GROUP BY LOWER(e1.text), LOWER(e2.text)
                HAVING cnt >= 2
            )
        """)
        
        stats['entity_pairs_with_co_occurrence'] = cursor.fetchone()[0]
        
        conn.close()
        
        return stats
    
    def get_entity_context(
        self,
        entity_text: str,
        context_chars: int = 100
    ) -> List[Dict]:
        """
        Get contextual snippets around entity mentions
        
        Args:
            entity_text: Entity to get context for
            context_chars: Number of characters before/after mention
        
        Returns:
            List of context snippets with metadata
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                e.text,
                m.id as memory_id,
                m.content,
                m.created_at
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE LOWER(e.text) = LOWER(?)
            ORDER BY m.created_at DESC
        """, (entity_text,))
        
        contexts = []
        
        for row in cursor.fetchall():
            content = row['content']
            entity = row['text']
            
            # Find entity in content (case-insensitive)
            content_lower = content.lower()
            entity_lower = entity.lower()
            
            idx = content_lower.find(entity_lower)
            
            if idx != -1:
                # Extract context
                start = max(0, idx - context_chars)
                end = min(len(content), idx + len(entity) + context_chars)
                
                context_snippet = content[start:end]
                
                # Add ellipsis if truncated
                if start > 0:
                    context_snippet = "..." + context_snippet
                if end < len(content):
                    context_snippet = context_snippet + "..."
                
                contexts.append({
                    'memory_id': row['memory_id'],
                    'timestamp': row['created_at'],
                    'context': context_snippet,
                    'entity_position': idx - start
                })
        
        conn.close()
        
        return contexts
    
    def find_memories_with_entities(
        self,
        entity_texts: List[str],
        match_all: bool = True
    ) -> List[Dict]:
        """
        Find memories containing specific entities
        
        Args:
            entity_texts: List of entity texts to search for
            match_all: If True, memory must contain ALL entities
                      If False, memory must contain ANY entity
        
        Returns:
            List of memory dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if not entity_texts:
            conn.close()
            return []
        
        if match_all:
            # ALL entities must be present
            placeholders = ','.join('?' * len(entity_texts))
            
            cursor.execute(f"""
                SELECT 
                    m.id,
                    m.content,
                    m.created_at,
                    COUNT(DISTINCT LOWER(e.text)) as matching_entities
                FROM memories m
                JOIN entities e ON m.id = e.memory_id
                WHERE LOWER(e.text) IN ({placeholders})
                GROUP BY m.id
                HAVING matching_entities = ?
                ORDER BY m.created_at DESC
            """, [e.lower() for e in entity_texts] + [len(entity_texts)])
        else:
            # ANY entity can be present
            placeholders = ','.join('?' * len(entity_texts))
            
            cursor.execute(f"""
                SELECT DISTINCT
                    m.id,
                    m.content,
                    m.created_at
                FROM memories m
                JOIN entities e ON m.id = e.memory_id
                WHERE LOWER(e.text) IN ({placeholders})
                ORDER BY m.created_at DESC
            """, [e.lower() for e in entity_texts])
        
        memories = []
        
        for row in cursor.fetchall():
            memories.append({
                'id': row['id'],
                'content': row['content'],
                'timestamp': row['created_at']
            })
        
        conn.close()
        
        return memories


def main():
    """Test entity search system"""
    import sys
    from mnemonic.config import DB_PATH
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = DB_PATH
    
    print(f"\n{'='*70}")
    print("ENTITY SEARCH SYSTEM TEST")
    print(f"{'='*70}\n")
    
    engine = EntitySearchEngine(db_path)
    
    # Test 1: Entity statistics
    print("Test 1: Entity Statistics")
    print("-" * 70)
    stats = engine.get_entity_statistics()
    
    print(f"Total entities: {stats['total_entities']}")
    print(f"\nEntities by type:")
    for entity_type, count in stats['by_type'].items():
        print(f"  {entity_type}: {count}")
    
    print(f"\nTop entities:")
    for entity in stats['top_entities'][:5]:
        print(f"  {entity['text']} ({entity['type']}): {entity['frequency']} mentions")
    
    print(f"\nEntity pairs with co-occurrence: {stats['entity_pairs_with_co_occurrence']}")
    
    # Test 2: Search by entity
    if stats['top_entities']:
        print(f"\n{'='*70}")
        print("Test 2: Search by Entity")
        print("-" * 70)
        
        top_entity = stats['top_entities'][0]['text']
        print(f"Searching for: {top_entity}\n")
        
        result = engine.search_by_entity(top_entity, include_co_occurrences=True)
        
        if result:
            print(f"Entity: {result.entity_text}")
            print(f"Type: {result.entity_type}")
            print(f"Frequency: {result.frequency}")
            print(f"Memory count: {result.memory_count}")
            
            if result.co_occurring_entities:
                print(f"\nCo-occurring entities:")
                for entity, count in list(result.co_occurring_entities.items())[:5]:
                    print(f"  {entity}: {count} co-occurrences")
            
            print(f"\nFirst 3 mentions:")
            for i, mention in enumerate(result.mentions[:3], 1):
                content_preview = mention.memory_content[:60]
                print(f"  {i}. {content_preview}...")
    
    # Test 3: Co-occurrence analysis
    print(f"\n{'='*70}")
    print("Test 3: Entity Co-occurrences (Foundation for Graphs)")
    print("-" * 70)
    
    co_occurrences = engine.find_co_occurrences(min_co_occurrence=2, limit=10)
    
    if co_occurrences:
        print(f"Found {len(co_occurrences)} entity pairs:\n")
        
        for i, co_occ in enumerate(co_occurrences[:5], 1):
            print(f"{i}. {co_occ.entity1} ↔ {co_occ.entity2}")
            print(f"   Co-occurred {co_occ.co_occurrence_count} times")
            print(f"   In memories: {co_occ.memories[:3]}{'...' if len(co_occ.memories) > 3 else ''}\n")
    else:
        print("No co-occurrences found (need at least 2 entities per memory)")
    
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()