#!/usr/bin/env python3
"""
Test Entity Search System (Week 4, Day 1)

This demonstrates:
1. Entity-based search
2. Entity co-occurrence detection
3. Foundation for relationship graphs
"""

import sys
import sqlite3
import tempfile
import os
from pathlib import Path

# Add to path
sys.path.insert(0, '/home/claude')

from mnemonic.entity_search import EntitySearchEngine, EntityMention, EntitySearchResult


def create_test_database():
    """Create a test database with sample data"""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            type TEXT,
            type_source TEXT NOT NULL,
            confidence REAL NOT NULL,
            frequency INTEGER DEFAULT 1,
            memory_id INTEGER NOT NULL,
            FOREIGN KEY (memory_id) REFERENCES memories(id)
        )
    """)
    
    # Add test memories with entities
    test_data = [
        {
            "content": "Watched Steins Gate last night. Amazing time travel anime with Okabe Rintarou as protagonist.",
            "entities": [
                ("Steins Gate", "anime", 0.95),
                ("Okabe Rintarou", "person", 0.90),
                ("time travel", "concept", 0.85)
            ]
        },
        {
            "content": "Steins Gate has incredible plot twists. Okabe Rintarou is one of the best anime characters.",
            "entities": [
                ("Steins Gate", "anime", 0.95),
                ("Okabe Rintarou", "person", 0.92),
                ("anime", "category", 0.80)
            ]
        },
        {
            "content": "Started watching Code Geass. Lelouch Lamperouge reminds me of Okabe Rintarou from Steins Gate.",
            "entities": [
                ("Code Geass", "anime", 0.93),
                ("Lelouch Lamperouge", "person", 0.91),
                ("Okabe Rintarou", "person", 0.89),
                ("Steins Gate", "anime", 0.88)
            ]
        },
        {
            "content": "Death Note is a psychological thriller anime. Light Yagami is a fascinating character.",
            "entities": [
                ("Death Note", "anime", 0.94),
                ("Light Yagami", "person", 0.92),
                ("psychological thriller", "genre", 0.83)
            ]
        },
        {
            "content": "Comparing Death Note and Code Geass - both have brilliant protagonists who use strategy.",
            "entities": [
                ("Death Note", "anime", 0.92),
                ("Code Geass", "anime", 0.91),
                ("strategy", "concept", 0.75)
            ]
        },
        {
            "content": "Working on Python machine learning project using scikit-learn and pandas.",
            "entities": [
                ("Python", "language", 0.90),
                ("machine learning", "concept", 0.88),
                ("scikit-learn", "library", 0.85),
                ("pandas", "library", 0.85)
            ]
        },
        {
            "content": "Python is great for data science. Using pandas for data manipulation.",
            "entities": [
                ("Python", "language", 0.92),
                ("data science", "concept", 0.87),
                ("pandas", "library", 0.86)
            ]
        }
    ]
    
    for data in test_data:
        # Insert memory
        cursor.execute("INSERT INTO memories (content) VALUES (?)", (data["content"],))
        memory_id = cursor.lastrowid
        
        # Insert entities
        for text, entity_type, confidence in data["entities"]:
            # Calculate frequency (how many times this entity appears total)
            cursor.execute("""
                SELECT COUNT(*) FROM entities WHERE LOWER(text) = LOWER(?)
            """, (text,))
            frequency = cursor.fetchone()[0] + 1
            
            cursor.execute("""
                INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id)
                VALUES (?, ?, 'user_defined', ?, ?, ?)
            """, (text, entity_type, confidence, frequency, memory_id))
    
    conn.commit()
    conn.close()
    
    return db_path


def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*70}")
    print(text)
    print(f"{'='*70}\n")


def test_entity_search():
    """Test entity search functionality"""
    print_header("ENTITY SEARCH SYSTEM TEST (Week 4, Day 1)")
    
    # Create test database
    print("Setting up test database...")
    db_path = create_test_database()
    print(f"✓ Test database created: {db_path}\n")
    
    try:
        engine = EntitySearchEngine(db_path)
        
        # TEST 1: Entity Statistics
        print_header("TEST 1: Entity Statistics")
        
        stats = engine.get_entity_statistics()
        
        print(f"Total entities: {stats['total_entities']}")
        print(f"\nEntities by type:")
        for entity_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
            print(f"  • {entity_type}: {count}")
        
        print(f"\nTop entities:")
        for i, entity in enumerate(stats['top_entities'][:10], 1):
            print(f"  {i}. {entity['text']} ({entity['type']}): {entity['frequency']} mentions")
        
        print(f"\nEntity pairs with co-occurrence: {stats['entity_pairs_with_co_occurrence']}")
        
        # TEST 2: Search by Entity
        print_header("TEST 2: Search by Entity (with Co-occurrences)")
        
        search_entity = "Steins Gate"
        print(f"Searching for: {search_entity}\n")
        
        result = engine.search_by_entity(search_entity, include_co_occurrences=True)
        
        if result:
            print(f"✓ Found entity: {result.entity_text}")
            print(f"  Type: {result.entity_type}")
            print(f"  Frequency: {result.frequency} mentions")
            print(f"  Appears in: {result.memory_count} memories")
            
            if result.co_occurring_entities:
                print(f"\n  Co-occurring entities:")
                sorted_co_occ = sorted(
                    result.co_occurring_entities.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                for entity, count in sorted_co_occ[:8]:
                    if entity.lower() != search_entity.lower():
                        print(f"    • {entity}: {count} times")
            
            print(f"\n  Mentions:")
            for i, mention in enumerate(result.mentions[:3], 1):
                content_preview = mention.memory_content[:70]
                print(f"    {i}. {content_preview}...")
        
        # TEST 3: Search by Type
        print_header("TEST 3: Search by Type")
        
        entity_type = "anime"
        print(f"Searching for all entities of type: {entity_type}\n")
        
        results = engine.search_by_type(entity_type, min_frequency=2, limit=10)
        
        if results:
            print(f"✓ Found {len(results)} anime entities:\n")
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result.entity_text}")
                print(f"     Frequency: {result.frequency}, Memories: {result.memory_count}")
        
        # TEST 4: Co-occurrence Analysis (Foundation for Graphs!)
        print_header("TEST 4: Entity Co-occurrences (Graph Foundation)")
        
        co_occurrences = engine.find_co_occurrences(min_co_occurrence=2, limit=15)
        
        if co_occurrences:
            print(f"✓ Found {len(co_occurrences)} entity pairs that co-occur:\n")
            
            for i, co_occ in enumerate(co_occurrences, 1):
                print(f"  {i}. {co_occ.entity1} ↔ {co_occ.entity2}")
                print(f"     Co-occurred {co_occ.co_occurrence_count} times")
                print(f"     In memories: {co_occ.memories}\n")
            
            print("💡 These pairs form the edges in our relationship graph!")
        else:
            print("No co-occurrences found")
        
        # TEST 5: Find Memories with Multiple Entities
        print_header("TEST 5: Find Memories with Multiple Entities")
        
        entities = ["Steins Gate", "Okabe Rintarou"]
        print(f"Finding memories containing ALL of: {', '.join(entities)}\n")
        
        memories = engine.find_memories_with_entities(entities, match_all=True)
        
        if memories:
            print(f"✓ Found {len(memories)} memories:\n")
            for i, memory in enumerate(memories, 1):
                content_preview = memory['content'][:80]
                print(f"  {i}. {content_preview}...")
        
        # TEST 6: Entity Context
        print_header("TEST 6: Entity Context Extraction")
        
        entity = "Okabe Rintarou"
        print(f"Getting context for: {entity}\n")
        
        contexts = engine.get_entity_context(entity, context_chars=50)
        
        if contexts:
            print(f"✓ Found {len(contexts)} mentions with context:\n")
            for i, ctx in enumerate(contexts[:3], 1):
                print(f"  {i}. {ctx['context']}")
                print(f"     [{ctx['timestamp']}]\n")
        
        # Summary
        print_header("SUMMARY")
        
        print("✅ Entity Search System Working!")
        print("\nKey Features Demonstrated:")
        print("  1. ✓ Search by entity name")
        print("  2. ✓ Search by entity type")
        print("  3. ✓ Co-occurrence detection (graph foundation)")
        print("  4. ✓ Multi-entity queries")
        print("  5. ✓ Context extraction")
        print("  6. ✓ Entity statistics")
        
        print("\n🎯 Next Steps:")
        print("  • Day 2: Build relationship graph visualization")
        print("  • Day 3: Add entity timeline analysis")
        print("  • Day 4: Create interactive graph explorer")
        
        print()
        
    finally:
        # Cleanup
        os.unlink(db_path)
        print(f"🧹 Cleaned up test database\n")


if __name__ == "__main__":
    test_entity_search()