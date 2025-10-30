"""
Tests for Entity Extraction System

Covers:
- Entity extraction (GLiNER + spaCy + tags)
- Entity storage (tentative → confirmed promotion)
- Checkpointing (creation and loading)
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "mnemonic"))

from entity_extractor import Entity, EntityExtractor, CORE_LABELS
from entity_storage import EntityStorage
from checkpointing import CheckpointManager


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Run migration to create tables
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Create minimal tables for testing
    cursor.execute("""
        CREATE TABLE tentative_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            type TEXT,
            type_source TEXT NOT NULL,
            confidence REAL NOT NULL,
            memory_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
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
            cluster_id INTEGER,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE entity_extraction_checkpoints (
            memory_id INTEGER PRIMARY KEY,
            noun_phrases TEXT NOT NULL,
            tags TEXT,
            checkpoint_version INTEGER NOT NULL DEFAULT 1,
            extraction_config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE user_entity_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT UNIQUE NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            example_entities TEXT,
            memory_count INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()
    
    yield path
    
    # Cleanup
    os.unlink(path)


class TestEntityExtractor:
    """Tests for EntityExtractor class"""
    
    def test_entity_creation(self):
        """Test Entity dataclass creation"""
        entity = Entity(
            text="Sarah",
            type="person",
            type_source="core",
            confidence=0.95
        )
        
        assert entity.text == "Sarah"
        assert entity.type == "person"
        assert entity.confidence == 0.95
    
    def test_entity_equality(self):
        """Test entity equality (case-insensitive text)"""
        e1 = Entity("Sarah", "person", "core", 0.9)
        e2 = Entity("sarah", "person", "core", 0.8)  # Different confidence
        e3 = Entity("Sarah", "organization", "core", 0.9)  # Different type
        
        assert e1 == e2  # Same text + type (case-insensitive)
        assert e1 != e3  # Different type
    
    def test_entity_hashing(self):
        """Test entity hashing for set operations"""
        e1 = Entity("Sarah", "person", "core", 0.9)
        e2 = Entity("sarah", "person", "core", 0.8)
        
        entity_set = {e1, e2}
        assert len(entity_set) == 1  # Should deduplicate
    
    def test_extractor_initialization(self, temp_db):
        """Test EntityExtractor initialization"""
        extractor = EntityExtractor(temp_db)
        
        assert extractor.db_path == temp_db
        assert CORE_LABELS == ["person", "organization", "location", "date"]
    
    def test_tags_to_entities(self, temp_db):
        """Test tag conversion to entities"""
        extractor = EntityExtractor(temp_db)
        
        tags = ["ai", "research", "machine-learning"]
        entities = extractor._tags_to_entities(tags)
        
        assert len(entities) == 3
        assert all(e.type == "tag" for e in entities)
        assert all(e.type_source == "tag" for e in entities)
        assert all(e.confidence == 1.0 for e in entities)
    
    def test_extract_with_tags_only(self, temp_db):
        """Test extraction with only tags (no NLP models)"""
        extractor = EntityExtractor(temp_db)
        
        # Disable models for this test
        extractor.gliner_model = None
        extractor.nlp = None
        
        text = "This is a test"
        tags = ["test", "demo"]
        
        entities = extractor.extract(text, tags)
        
        # Should only have tag entities
        assert len(entities) == 2
        assert all(e.type_source == "tag" for e in entities)


class TestEntityStorage:
    """Tests for EntityStorage class"""
    
    def test_storage_initialization(self, temp_db):
        """Test EntityStorage initialization"""
        storage = EntityStorage(temp_db)
        assert storage.db_path == temp_db
    
    def test_store_tentative_entity(self, temp_db):
        """Test storing first occurrence (tentative)"""
        storage = EntityStorage(temp_db)
        
        entities = [
            Entity("Sarah", "person", "core", 0.95)
        ]
        
        stats = storage.store_entities(memory_id=1, entities=entities)
        
        assert stats['tentative_added'] == 1
        assert stats['promoted'] == 0
        assert stats['frequency_updated'] == 0
    
    def test_promote_to_confirmed(self, temp_db):
        """Test promotion on second occurrence"""
        storage = EntityStorage(temp_db)
        
        entity = Entity("Sarah", "person", "core", 0.95)
        
        # First occurrence
        stats1 = storage.store_entities(memory_id=1, entities=[entity])
        assert stats1['tentative_added'] == 1
        
        # Second occurrence - should promote
        stats2 = storage.store_entities(memory_id=2, entities=[entity])
        assert stats2['promoted'] == 1
        assert stats2['tentative_added'] == 0
    
    def test_frequency_increment(self, temp_db):
        """Test frequency increment on third+ occurrence"""
        storage = EntityStorage(temp_db)
        
        entity = Entity("Sarah", "person", "core", 0.95)
        
        # First and second occurrence
        storage.store_entities(memory_id=1, entities=[entity])
        storage.store_entities(memory_id=2, entities=[entity])
        
        # Third occurrence - should increment frequency
        stats3 = storage.store_entities(memory_id=3, entities=[entity])
        assert stats3['frequency_updated'] == 1
        
        # Verify frequency
        result = storage.get_entity_by_text("Sarah", "person")
        assert result['frequency'] == 3
    
    def test_get_entity_by_text(self, temp_db):
        """Test entity retrieval by text"""
        storage = EntityStorage(temp_db)
        
        entity = Entity("Google", "organization", "core", 0.89)
        
        # Store twice to confirm
        storage.store_entities(memory_id=1, entities=[entity])
        storage.store_entities(memory_id=2, entities=[entity])
        
        # Retrieve
        result = storage.get_entity_by_text("Google", "organization")
        
        assert result is not None
        assert result['text'] == "Google"
        assert result['type'] == "organization"
        assert result['frequency'] == 2
    
    def test_case_insensitive_matching(self, temp_db):
        """Test case-insensitive entity matching"""
        storage = EntityStorage(temp_db)
        
        entity1 = Entity("Sarah", "person", "core", 0.95)
        entity2 = Entity("sarah", "person", "core", 0.90)
        
        storage.store_entities(memory_id=1, entities=[entity1])
        storage.store_entities(memory_id=2, entities=[entity2])
        
        # Should be treated as same entity
        result = storage.get_entity_by_text("SARAH", "person")
        assert result is not None
        assert result['frequency'] == 2
    
    def test_get_storage_stats(self, temp_db):
        """Test storage statistics"""
        storage = EntityStorage(temp_db)
        
        entities = [
            Entity("Sarah", "person", "core", 0.95),
            Entity("Google", "organization", "core", 0.89),
            Entity("Tokyo", "location", "core", 0.92)
        ]
        
        # Store once (all tentative)
        storage.store_entities(memory_id=1, entities=entities)
        
        stats = storage.get_storage_stats()
        assert stats['tentative_count'] == 3
        assert stats['confirmed_count'] == 0
        
        # Store again (all promoted)
        storage.store_entities(memory_id=2, entities=entities)
        
        stats = storage.get_storage_stats()
        assert stats['tentative_count'] == 0  # All promoted
        assert stats['confirmed_count'] == 3
        assert stats['total_occurrences'] == 6  # 3 entities × frequency 2


class TestCheckpointManager:
    """Tests for CheckpointManager class"""
    
    def test_checkpoint_initialization(self, temp_db):
        """Test CheckpointManager initialization"""
        manager = CheckpointManager(temp_db)
        assert manager.db_path == temp_db
    
    def test_create_checkpoint(self, temp_db):
        """Test checkpoint creation"""
        manager = CheckpointManager(temp_db)
        
        if not manager.nlp:
            pytest.skip("spaCy not available")
        
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
        
        assert success is True
    
    def test_load_checkpoint(self, temp_db):
        """Test checkpoint loading"""
        manager = CheckpointManager(temp_db)
        
        if not manager.nlp:
            pytest.skip("spaCy not available")
        
        text = "Met Sarah at the conference"
        entities = [Entity("conference", "tag", "tag", 1.0)]
        
        # Create checkpoint
        manager.create_checkpoint(1, text, entities, [])
        
        # Load checkpoint
        checkpoint = manager.load_checkpoint(1)
        
        assert checkpoint is not None
        assert checkpoint['memory_id'] == 1
        assert 'noun_phrases' in checkpoint
        assert len(checkpoint['noun_phrases']) > 0
    
    def test_checkpoint_stats(self, temp_db):
        """Test checkpoint statistics"""
        manager = CheckpointManager(temp_db)
        
        if not manager.nlp:
            pytest.skip("spaCy not available")
        
        # Create multiple checkpoints
        for i in range(1, 4):
            manager.create_checkpoint(
                memory_id=i,
                text=f"Test memory {i}",
                entities=[],
                user_labels=[]
            )
        
        stats = manager.get_checkpoint_stats()
        
        assert stats['total_checkpoints'] == 3
        assert stats['current_version_count'] == 3
        assert stats['outdated_count'] == 0


class TestIntegration:
    """Integration tests for the full entity system"""
    
    def test_full_pipeline(self, temp_db):
        """Test complete extraction → storage → checkpoint pipeline"""
        extractor = EntityExtractor(temp_db)
        storage = EntityStorage(temp_db)
        checkpointer = CheckpointManager(temp_db)
        
        # Disable NLP models for faster testing
        extractor.gliner_model = None
        extractor.nlp = None
        
        # Test with tags only
        text = "Test memory about AI and machine learning"
        tags = ["ai", "ml", "tech"]
        
        # Extract
        entities = extractor.extract(text, tags)
        assert len(entities) == 3  # 3 tag entities
        
        # Store
        stats = storage.store_entities(memory_id=1, entities=entities)
        assert stats['tentative_added'] == 3
        
        # Create checkpoint
        if checkpointer.nlp:
            success = checkpointer.create_checkpoint(1, text, entities, [])
            assert success is True
    
    def test_entity_lifecycle(self, temp_db):
        """Test entity lifecycle: tentative → confirmed → frequency updates"""
        storage = EntityStorage(temp_db)
        
        entity = Entity("TestEntity", "test_type", "core", 0.8)
        
        # Occurrence 1: Tentative
        storage.store_entities(1, [entity])
        stats = storage.get_storage_stats()
        assert stats['tentative_count'] == 1
        assert stats['confirmed_count'] == 0
        
        # Occurrence 2: Promoted
        storage.store_entities(2, [entity])
        stats = storage.get_storage_stats()
        assert stats['tentative_count'] == 0
        assert stats['confirmed_count'] == 1
        
        # Occurrence 3: Frequency increment
        storage.store_entities(3, [entity])
        result = storage.get_entity_by_text("TestEntity", "test_type")
        assert result['frequency'] == 3


def run_tests():
    """Run all tests"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()