#!/usr/bin/env python3
"""
Comprehensive Test Suite for Day 6 Entity Extraction

Tests everything we built today:
1. Database migrations
2. Entity extraction
3. Entity storage
4. Checkpointing
5. Integration
"""

import sys
import sqlite3
import tempfile
import os
from pathlib import Path

# Add mnemonic directory to path
sys.path.insert(0, str(Path(__file__).parent / "mnemonic"))

from entity_extractor import EntityExtractor, Entity, CORE_LABELS
from entity_storage import EntityStorage
from checkpointing import CheckpointManager


def print_header(text):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"{text}")
    print(f"{'='*60}\n")


def print_step(step_num, text):
    """Print a test step"""
    print(f"[{step_num}] {text}")


def print_success(text):
    """Print success message"""
    print(f"    ✓ {text}")


def print_error(text):
    """Print error message"""
    print(f"    ✗ {text}")


def test_migrations():
    """Test database migrations"""
    print_header("TEST 1: Database Migrations")
    
    # Create temp database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    try:
        print_step(1, "Running migration 001 (initial schema)...")
        from migrations import M001_initial_schema as m001
        m001.upgrade(db_path)
        print_success("Migration 001 applied")
        
        print_step(2, "Running migration 002 (entity tables)...")
        from migrations import M002_add_entity_tables as m002
        m002.upgrade(db_path)
        print_success("Migration 002 applied")
        
        print_step(3, "Verifying tables exist...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table'
            ORDER BY name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        expected_tables = [
            'memories',
            'memory_tags',
            'tentative_entities',
            'entities',
            'entity_extraction_checkpoints',
            'user_entity_types',
            'schema_version'
        ]
        
        for table in expected_tables:
            if table in tables:
                print_success(f"Table '{table}' exists")
            else:
                print_error(f"Table '{table}' missing")
                return False
        
        conn.close()
        print_success("All tables created successfully")
        
        return True
        
    except Exception as e:
        print_error(f"Migration failed: {e}")
        return False
    finally:
        os.unlink(db_path)


def test_entity_extraction():
    """Test entity extraction"""
    print_header("TEST 2: Entity Extraction")
    
    # Create temp database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    try:
        # Run migrations
        from migrations import M001_initial_schema as m001
        from migrations import M002_add_entity_tables as m002
        m001.upgrade(db_path)
        m002.upgrade(db_path)
        
        print_step(1, "Initializing EntityExtractor...")
        extractor = EntityExtractor(db_path)
        print_success("EntityExtractor initialized")
        
        print_step(2, "Testing tag extraction...")
        text = "Test memory about AI and machine learning"
        tags = ["ai", "ml", "technology"]
        
        entities = extractor.extract(text, tags)
        tag_entities = [e for e in entities if e.type_source == "tag"]
        
        if len(tag_entities) == 3:
            print_success(f"Extracted {len(tag_entities)} tag entities")
            for entity in tag_entities:
                print(f"        - {entity.text} (confidence: {entity.confidence})")
        else:
            print_error(f"Expected 3 tag entities, got {len(tag_entities)}")
            return False
        
        print_step(3, "Testing GLiNER extraction (if available)...")
        if extractor.gliner_model:
            text = "Met Sarah Chen at Google headquarters in San Francisco on 2024-10-26"
            entities = extractor.extract(text, [])
            
            core_entities = [e for e in entities if e.type_source == "core"]
            print_success(f"GLiNER extracted {len(core_entities)} core entities:")
            for entity in core_entities:
                print(f"        - {entity.text} ({entity.type}) [confidence: {entity.confidence:.2f}]")
        else:
            print_success("GLiNER not available (skipping)")
        
        print_step(4, "Testing noun phrase extraction (if available)...")
        if extractor.nlp:
            text = "The transformer paper discusses attention mechanisms"
            entities = extractor.extract(text, [])
            
            noun_phrases = [e for e in entities if e.type_source == "noun_phrase"]
            print_success(f"spaCy extracted {len(noun_phrases)} noun phrases:")
            for entity in noun_phrases:
                print(f"        - {entity.text}")
        else:
            print_success("spaCy not available (skipping)")
        
        return True
        
    except Exception as e:
        print_error(f"Entity extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        os.unlink(db_path)


def test_entity_storage():
    """Test entity storage and promotion"""
    print_header("TEST 3: Entity Storage")
    
    # Create temp database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    try:
        # Run migrations
        from migrations import M001_initial_schema as m001
        from migrations import M002_add_entity_tables as m002
        m001.upgrade(db_path)
        m002.upgrade(db_path)
        
        print_step(1, "Initializing EntityStorage...")
        storage = EntityStorage(db_path)
        print_success("EntityStorage initialized")
        
        print_step(2, "Testing tentative entity storage...")
        entity = Entity("TestEntity", "test_type", "core", 0.9)
        stats = storage.store_entities(memory_id=1, entities=[entity])
        
        if stats['tentative_added'] == 1:
            print_success("Entity stored as tentative")
            print(f"        - Tentative: {stats['tentative_added']}")
            print(f"        - Promoted: {stats['promoted']}")
            print(f"        - Updated: {stats['frequency_updated']}")
        else:
            print_error("Failed to store tentative entity")
            return False
        
        print_step(3, "Testing promotion to confirmed...")
        stats = storage.store_entities(memory_id=2, entities=[entity])
        
        if stats['promoted'] == 1:
            print_success("Entity promoted to confirmed")
            print(f"        - Tentative: {stats['tentative_added']}")
            print(f"        - Promoted: {stats['promoted']}")
            print(f"        - Updated: {stats['frequency_updated']}")
        else:
            print_error("Failed to promote entity")
            return False
        
        print_step(4, "Testing frequency increment...")
        stats = storage.store_entities(memory_id=3, entities=[entity])
        
        if stats['frequency_updated'] == 1:
            print_success("Frequency incremented")
            
            # Verify frequency
            result = storage.get_entity_by_text("TestEntity", "test_type")
            print(f"        - Current frequency: {result['frequency']}")
        else:
            print_error("Failed to increment frequency")
            return False
        
        print_step(5, "Testing entity retrieval...")
        result = storage.get_entity_by_text("TestEntity", "test_type")
        
        if result and result['frequency'] == 3:
            print_success(f"Retrieved entity with frequency={result['frequency']}")
        else:
            print_error("Entity retrieval failed")
            return False
        
        print_step(6, "Testing storage statistics...")
        stats = storage.get_storage_stats()
        print_success("Storage stats:")
        print(f"        - Tentative: {stats['tentative_count']}")
        print(f"        - Confirmed: {stats['confirmed_count']}")
        print(f"        - Total occurrences: {stats['total_occurrences']}")
        
        return True
        
    except Exception as e:
        print_error(f"Entity storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        os.unlink(db_path)


def test_checkpointing():
    """Test checkpoint creation and loading"""
    print_header("TEST 4: Checkpointing System")
    
    # Create temp database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    try:
        # Run migrations
        from migrations import M001_initial_schema as m001
        from migrations import M002_add_entity_tables as m002
        m001.upgrade(db_path)
        m002.upgrade(db_path)
        
        print_step(1, "Initializing CheckpointManager...")
        manager = CheckpointManager(db_path)
        print_success("CheckpointManager initialized")
        
        if not manager.nlp:
            print_success("spaCy not available - skipping checkpoint tests")
            return True
        
        print_step(2, "Creating checkpoint...")
        text = "Met Sarah at the AI conference in Tokyo"
        entities = [
            Entity("ai", "tag", "tag", 1.0),
            Entity("conference", "tag", "tag", 1.0)
        ]
        
        success = manager.create_checkpoint(
            memory_id=1,
            text=text,
            entities=entities,
            user_labels=[]
        )
        
        if success:
            print_success("Checkpoint created")
        else:
            print_error("Failed to create checkpoint")
            return False
        
        print_step(3, "Loading checkpoint...")
        checkpoint = manager.load_checkpoint(1)
        
        if checkpoint:
            print_success("Checkpoint loaded")
            print(f"        - Version: {checkpoint['version']}")
            print(f"        - Noun phrases: {len(checkpoint['noun_phrases'])}")
            print(f"        - Tags: {len(checkpoint['tags'])}")
            
            # Show noun phrases
            for phrase in checkpoint['noun_phrases'][:3]:
                print(f"        - '{phrase['text']}'")
        else:
            print_error("Failed to load checkpoint")
            return False
        
        print_step(4, "Testing checkpoint statistics...")
        stats = manager.get_checkpoint_stats()
        print_success("Checkpoint stats:")
        print(f"        - Total: {stats['total_checkpoints']}")
        print(f"        - Current version: {stats['current_version_count']}")
        print(f"        - Outdated: {stats['outdated_count']}")
        
        return True
        
    except Exception as e:
        print_error(f"Checkpointing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        os.unlink(db_path)


def test_integration():
    """Test full integration pipeline"""
    print_header("TEST 5: Full Integration")
    
    # Create temp database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    try:
        # Run migrations
        from migrations import M001_initial_schema as m001
        from migrations import M002_add_entity_tables as m002
        m001.upgrade(db_path)
        m002.upgrade(db_path)
        
        print_step(1, "Setting up components...")
        extractor = EntityExtractor(db_path)
        storage = EntityStorage(db_path)
        checkpointer = CheckpointManager(db_path)
        print_success("All components initialized")
        
        print_step(2, "Running full pipeline...")
        text = "Met with Sarah Chen at Google to discuss AI research"
        tags = ["ai", "research", "meeting"]
        
        # Extract
        entities = extractor.extract(text, tags)
        print_success(f"Extracted {len(entities)} entities")
        
        # Store
        stats = storage.store_entities(memory_id=1, entities=entities)
        print_success(f"Stored entities (tentative: {stats['tentative_added']})")
        
        # Checkpoint
        if checkpointer.nlp:
            success = checkpointer.create_checkpoint(1, text, entities, [])
            if success:
                print_success("Checkpoint created")
        
        print_step(3, "Testing second memory with same entities...")
        text2 = "Sarah Chen from Google sent me the research paper"
        entities2 = extractor.extract(text2, tags)
        
        stats2 = storage.store_entities(memory_id=2, entities=entities2)
        print_success(f"Stored entities (promoted: {stats2['promoted']})")
        
        print_step(4, "Verifying final state...")
        final_stats = storage.get_storage_stats()
        print_success("Final statistics:")
        print(f"        - Tentative entities: {final_stats['tentative_count']}")
        print(f"        - Confirmed entities: {final_stats['confirmed_count']}")
        print(f"        - Total occurrences: {final_stats['total_occurrences']}")
        
        return True
        
    except Exception as e:
        print_error(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        os.unlink(db_path)


def main():
    """Run all tests"""
    print_header("DAY 6 COMPREHENSIVE TEST SUITE")
    print("Testing: Migrations, Extraction, Storage, Checkpointing, Integration\n")
    
    results = []
    
    # Test 1: Migrations
    results.append(("Migrations", test_migrations()))
    
    # Test 2: Entity Extraction
    results.append(("Entity Extraction", test_entity_extraction()))
    
    # Test 3: Entity Storage
    results.append(("Entity Storage", test_entity_storage()))
    
    # Test 4: Checkpointing
    results.append(("Checkpointing", test_checkpointing()))
    
    # Test 5: Integration
    results.append(("Integration", test_integration()))
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Day 6 is complete!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())