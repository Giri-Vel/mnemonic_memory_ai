"""
Entity Storage System

Handles:
- Storing entities in tentative_entities table (frequency = 1)
- Promoting to entities table (frequency >= 2)
- Frequency tracking and updates
- Entity querying and retrieval
"""

import sqlite3
import json
from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class Entity:
    """Entity data class (matches entity_extractor.py)"""
    text: str
    type: Optional[str]
    type_source: str
    confidence: float
    context: Optional[str] = None
    span: Optional[tuple] = None


class EntityStorage:
    """
    Manages entity storage with tentative → confirmed promotion logic
    
    Flow:
    1. First occurrence → tentative_entities (status='pending')
    2. Second occurrence → promote to entities (frequency=2)
    3. Subsequent occurrences → increment frequency
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Ensure all required tables exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('tentative_entities', 'entities')
        """)
        
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        if 'tentative_entities' not in existing_tables or 'entities' not in existing_tables:
            print("⚠ Entity tables not found. Run migration first:")
            print("  python migrations/M002_add_entity_tables.py <db_path>")
        
        conn.close()
    
    def store_entities(self, memory_id: int, entities: List[Entity]) -> Dict[str, int]:
        """
        Store entities and handle tentative → confirmed promotion
        
        Args:
            memory_id: ID of the memory these entities belong to
            entities: List of Entity objects to store
        
        Returns:
            Dictionary with counts: {
                'tentative_added': int,
                'promoted': int,
                'frequency_updated': int
            }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {
            'tentative_added': 0,
            'promoted': 0,
            'frequency_updated': 0
        }
        
        try:
            for entity in entities:
                # Find existing entity (tentative or confirmed)
                existing = self._find_existing(cursor, entity.text, entity.type)
                
                if existing and existing["status"] == "pending":
                    # Promote tentative → confirmed (frequency = 2)
                    self._promote_to_confirmed(cursor, existing["id"], entity, memory_id)
                    stats['promoted'] += 1
                    
                elif existing and existing["status"] == "confirmed":
                    # Update frequency
                    self._increment_frequency(cursor, existing["id"])
                    stats['frequency_updated'] += 1
                    
                else:
                    # First occurrence - store as tentative
                    self._store_tentative(cursor, entity, memory_id)
                    stats['tentative_added'] += 1
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"✗ Error storing entities: {e}")
            raise
        finally:
            conn.close()
        
        return stats
    
    def _find_existing(
        self, 
        cursor: sqlite3.Cursor, 
        text: str, 
        entity_type: Optional[str]
    ) -> Optional[Dict]:
        """
        Find existing entity (tentative or confirmed)
        
        Args:
            cursor: Database cursor
            text: Entity text
            entity_type: Entity type (can be None)
        
        Returns:
            Dictionary with {id, status} or None if not found
        """
        # Check confirmed entities first
        cursor.execute("""
            SELECT id, 'confirmed' as status 
            FROM entities 
            WHERE LOWER(text) = LOWER(?) AND type IS ?
        """, (text, entity_type))
        
        result = cursor.fetchone()
        if result:
            return {"id": result[0], "status": result[1]}
        
        # Check tentative entities
        cursor.execute("""
            SELECT id, status 
            FROM tentative_entities 
            WHERE LOWER(text) = LOWER(?) AND type IS ? AND status = 'pending'
        """, (text, entity_type))
        
        result = cursor.fetchone()
        if result:
            return {"id": result[0], "status": result[1]}
        
        return None
    
    def _store_tentative(
        self, 
        cursor: sqlite3.Cursor, 
        entity: Entity, 
        memory_id: int
    ) -> int:
        """
        Store entity as tentative (frequency = 1)
        
        Args:
            cursor: Database cursor
            entity: Entity to store
            memory_id: Associated memory ID
        
        Returns:
            ID of created tentative entity
        """
        cursor.execute("""
            INSERT INTO tentative_entities 
            (text, type, type_source, confidence, memory_id, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (
            entity.text,
            entity.type,
            entity.type_source,
            entity.confidence,
            memory_id
        ))
        
        return cursor.lastrowid
    
    def _promote_to_confirmed(
        self,
        cursor: sqlite3.Cursor,
        tentative_id: int,
        entity: Entity,
        memory_id: int
    ) -> int:
        """
        Promote tentative entity to confirmed (frequency >= 2)
        
        Args:
            cursor: Database cursor
            tentative_id: ID of tentative entity to promote
            entity: New entity occurrence
            memory_id: Memory ID of second occurrence
        
        Returns:
            ID of created confirmed entity
        """
        # Get original memory_id from tentative entity
        cursor.execute("""
            SELECT memory_id FROM tentative_entities WHERE id = ?
        """, (tentative_id,))
        original_memory_id = cursor.fetchone()[0]
        
        # Create confirmed entity with frequency = 2
        metadata = json.dumps({
            "promoted_from": tentative_id,
            "first_occurrence_memory_id": original_memory_id,
            "second_occurrence_memory_id": memory_id
        })
        
        # FIXED: Use correct number of placeholders (7 values)
        cursor.execute("""
            INSERT INTO entities 
            (text, type, type_source, confidence, frequency, memory_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entity.text,
            entity.type,
            entity.type_source,
            entity.confidence,
            2,  # frequency = 2 on promotion
            original_memory_id,  # Store first occurrence memory_id
            metadata
        ))
        
        confirmed_id = cursor.lastrowid
        
        # Mark tentative as confirmed (keep for audit trail)
        cursor.execute("""
            UPDATE tentative_entities 
            SET status = 'confirmed' 
            WHERE id = ?
        """, (tentative_id,))
        
        return confirmed_id
    
    def _increment_frequency(self, cursor: sqlite3.Cursor, entity_id: int) -> None:
        """
        Increment frequency for existing confirmed entity
        
        Args:
            cursor: Database cursor
            entity_id: ID of confirmed entity
        """
        cursor.execute("""
            UPDATE entities 
            SET frequency = frequency + 1,
                last_seen = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (entity_id,))
    
    def get_entities_for_memory(self, memory_id: int) -> List[Dict]:
        """
        Get all entities associated with a memory
        
        Args:
            memory_id: Memory ID
        
        Returns:
            List of entity dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get from both tentative and confirmed
        entities = []
        
        # Tentative entities
        cursor.execute("""
            SELECT text, type, type_source, confidence, 'tentative' as status
            FROM tentative_entities
            WHERE memory_id = ? AND status = 'pending'
        """, (memory_id,))
        
        for row in cursor.fetchall():
            entities.append({
                'text': row[0],
                'type': row[1],
                'type_source': row[2],
                'confidence': row[3],
                'status': row[4]
            })
        
        # Confirmed entities (check if this memory_id is in metadata)
        cursor.execute("""
            SELECT text, type, type_source, confidence, frequency, metadata
            FROM entities
            WHERE memory_id = ?
        """, (memory_id,))
        
        for row in cursor.fetchall():
            entities.append({
                'text': row[0],
                'type': row[1],
                'type_source': row[2],
                'confidence': row[3],
                'status': 'confirmed',
                'frequency': row[4]
            })
        
        conn.close()
        
        return entities
    
    def get_entity_by_text(self, text: str, entity_type: Optional[str] = None) -> Optional[Dict]:
        """
        Get entity by text (and optionally type)
        
        Args:
            text: Entity text
            entity_type: Entity type (optional)
        
        Returns:
            Entity dictionary or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT id, text, type, type_source, confidence, frequency, cluster_id, metadata
            FROM entities
            WHERE LOWER(text) = LOWER(?)
        """
        params = [text]
        
        if entity_type is not None:
            query += " AND type = ?"
            params.append(entity_type)
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'text': row[1],
                'type': row[2],
                'type_source': row[3],
                'confidence': row[4],
                'frequency': row[5],
                'cluster_id': row[6],
                'metadata': json.loads(row[7]) if row[7] else None
            }
        
        return None
    
    def get_all_confirmed_entities(self, min_frequency: int = 2) -> List[Dict]:
        """
        Get all confirmed entities
        
        Args:
            min_frequency: Minimum frequency threshold
        
        Returns:
            List of entity dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, text, type, type_source, frequency, cluster_id
            FROM entities
            WHERE frequency >= ?
            ORDER BY frequency DESC
        """, (min_frequency,))
        
        entities = []
        for row in cursor.fetchall():
            entities.append({
                'id': row[0],
                'text': row[1],
                'type': row[2],
                'type_source': row[3],
                'frequency': row[4],
                'cluster_id': row[5]
            })
        
        conn.close()
        
        return entities
    
    def get_entities_by_type(self, entity_type: str) -> List[Dict]:
        """
        Get all entities of a specific type
        
        Args:
            entity_type: Type to filter by
        
        Returns:
            List of entity dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, text, type_source, frequency, cluster_id
            FROM entities
            WHERE type = ?
            ORDER BY frequency DESC
        """, (entity_type,))
        
        entities = []
        for row in cursor.fetchall():
            entities.append({
                'id': row[0],
                'text': row[1],
                'type_source': row[2],
                'frequency': row[3],
                'cluster_id': row[4]
            })
        
        conn.close()
        
        return entities
    
    def get_storage_stats(self) -> Dict:
        """
        Get statistics about entity storage
        
        Returns:
            Dictionary with stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Tentative count
        cursor.execute("SELECT COUNT(*) FROM tentative_entities WHERE status = 'pending'")
        stats['tentative_count'] = cursor.fetchone()[0]
        
        # Confirmed count
        cursor.execute("SELECT COUNT(*) FROM entities")
        stats['confirmed_count'] = cursor.fetchone()[0]
        
        # Total frequency
        cursor.execute("SELECT SUM(frequency) FROM entities")
        stats['total_occurrences'] = cursor.fetchone()[0] or 0
        
        # By type
        cursor.execute("""
            SELECT type, COUNT(*) as count, SUM(frequency) as total_freq
            FROM entities
            GROUP BY type
            ORDER BY count DESC
        """)
        
        stats['by_type'] = []
        for row in cursor.fetchall():
            stats['by_type'].append({
                'type': row[0] or 'untyped',
                'count': row[1],
                'total_frequency': row[2]
            })
        
        conn.close()
        
        return stats


def main():
    """Test entity storage"""
    import sys
    from entity_extractor import Entity
    
    if len(sys.argv) < 2:
        print("Usage: python entity_storage.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    print(f"\n{'='*60}")
    print("ENTITY STORAGE TEST")
    print(f"{'='*60}\n")
    
    storage = EntityStorage(db_path)
    
    # Test entities
    test_entities = [
        Entity("Sarah", "person", "core", 0.95),
        Entity("Google", "organization", "core", 0.89),
        Entity("Tokyo", "location", "core", 0.92),
    ]
    
    print("Storing test entities (memory_id=1)...")
    stats = storage.store_entities(1, test_entities)
    print(f"  Tentative added: {stats['tentative_added']}")
    print(f"  Promoted: {stats['promoted']}")
    print(f"  Frequency updated: {stats['frequency_updated']}")
    print()
    
    print("Storing same entities again (memory_id=2)...")
    stats = storage.store_entities(2, test_entities)
    print(f"  Tentative added: {stats['tentative_added']}")
    print(f"  Promoted: {stats['promoted']}")
    print(f"  Frequency updated: {stats['frequency_updated']}")
    print()
    
    print(f"{'='*60}")
    stats = storage.get_storage_stats()
    print("STORAGE STATS:")
    print(f"  Tentative: {stats['tentative_count']}")
    print(f"  Confirmed: {stats['confirmed_count']}")
    print(f"  Total occurrences: {stats['total_occurrences']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()