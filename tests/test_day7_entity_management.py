"""
Tests for Entity Type Management System (Day 7)

Covers:
- Entity type suggestions (tag frequency + noun phrases)
- CRUD operations (add/remove/list types)
- Re-extraction queue management
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "mnemonic"))

from entity_type_manager import EntityTypeManager, EntityTypeSuggestion
from reextraction_queue import ReextractionQueue, ReextractionJob


@pytest.fixture
def temp_db():
    """Create a temporary database with all required tables"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Run all migrations to create tables
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # M001 tables
    cursor.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE memory_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            FOREIGN KEY (memory_id) REFERENCES memories(id)
        )
    """)
    
    # M002 tables
    cursor.execute("""
        CREATE TABLE tentative_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            type TEXT,
            type_source TEXT NOT NULL,
            confidence REAL NOT NULL,
            memory_id INTEGER NOT NULL,
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
            memory_id INTEGER NOT NULL
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
    
    # M003 table
    cursor.execute("""
        CREATE TABLE reextraction_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            memories_processed INTEGER DEFAULT 0,
            memories_total INTEGER DEFAULT 0,
            entities_found INTEGER DEFAULT 0,
            error_message TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    
    yield path
    
    # Cleanup
    os.unlink(path)


class TestEntityTypeManager:
    """Tests for EntityTypeManager"""
    
    def test_initialization(self, temp_db):
        """Test manager initialization"""
        manager = EntityTypeManager(temp_db)
        
        assert manager.db_path == temp_db
        assert manager.CORE_TYPES == {'person', 'organization', 'location', 'date'}
        assert manager.TAG_FREQUENCY_THRESHOLD == 5
        assert manager.NOUN_PHRASE_THRESHOLD == 3
    
    def test_suggest_from_tags_empty(self, temp_db):
        """Test tag suggestions with no data"""
        manager = EntityTypeManager(temp_db)
        
        suggestions = manager.suggest_entity_types()
        assert suggestions == []
    
    def test_suggest_from_tags_with_data(self, temp_db):
        """Test tag suggestions with frequent tags"""
        # Add test data: tag "anime" appears on 6 memories
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        for i in range(1, 7):
            cursor.execute("INSERT INTO memories (content) VALUES (?)", (f"Memory {i}",))
            memory_id = cursor.lastrowid
            cursor.execute("INSERT INTO memory_tags (memory_id, tag) VALUES (?, 'anime')", (memory_id,))
        
        conn.commit()
        conn.close()
        
        manager = EntityTypeManager(temp_db)
        suggestions = manager.suggest_entity_types()
        
        # Should suggest "anime" as entity type
        assert len(suggestions) > 0
        assert any(s.type_name == 'anime' for s in suggestions)
        
        anime_suggestion = next(s for s in suggestions if s.type_name == 'anime')
        assert anime_suggestion.source == 'tag'
        assert anime_suggestion.occurrence_count == 6
    
    def test_suggest_from_noun_phrases(self, temp_db):
        """Test noun phrase suggestions"""
        # Add test data: "transformer paper" appears 4 times
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        for i in range(1, 5):
            cursor.execute("INSERT INTO memories (content) VALUES (?)", (f"Memory {i}",))
            memory_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO tentative_entities (text, type, type_source, confidence, memory_id)
                VALUES ('transformer paper', NULL, 'noun_phrase', 0.5, ?)
            """, (memory_id,))
        
        conn.commit()
        conn.close()
        
        manager = EntityTypeManager(temp_db)
        suggestions = manager.suggest_entity_types()
        
        # Should suggest "transformer_paper" as entity type
        assert len(suggestions) > 0
        assert any('transformer' in s.type_name for s in suggestions)
    
    def test_add_entity_type_success(self, temp_db):
        """Test adding a new entity type"""
        manager = EntityTypeManager(temp_db)
        
        success = manager.add_entity_type("anime")
        assert success is True
        
        # Verify it was added
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_entity_types WHERE type_name = 'anime'")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 1
    
    def test_add_entity_type_duplicate(self, temp_db):
        """Test adding duplicate entity type"""
        manager = EntityTypeManager(temp_db)
        
        manager.add_entity_type("anime")
        success = manager.add_entity_type("anime")
        
        assert success is False
    
    def test_add_entity_type_core_type_rejected(self, temp_db):
        """Test that core types cannot be added"""
        manager = EntityTypeManager(temp_db)
        
        with pytest.raises(ValueError, match="core entity type"):
            manager.add_entity_type("person")
    
    def test_add_entity_type_empty_rejected(self, temp_db):
        """Test that empty type names are rejected"""
        manager = EntityTypeManager(temp_db)
        
        with pytest.raises(ValueError, match="cannot be empty"):
            manager.add_entity_type("")
        
        with pytest.raises(ValueError, match="cannot be empty"):
            manager.add_entity_type("   ")
    
    def test_remove_entity_type_success(self, temp_db):
        """Test removing an entity type"""
        manager = EntityTypeManager(temp_db)
        
        manager.add_entity_type("anime")
        success, message = manager.remove_entity_type("anime")
        
        assert success is True
        assert message is None or "orphaned" not in message.lower()
    
    def test_remove_entity_type_not_exists(self, temp_db):
        """Test removing non-existent type"""
        manager = EntityTypeManager(temp_db)
        
        success, message = manager.remove_entity_type("nonexistent")
        
        assert success is False
        assert "does not exist" in message
    
    def test_remove_entity_type_with_usage(self, temp_db):
        """Test removing type that's in use"""
        manager = EntityTypeManager(temp_db)
        
        # Add type and create entity with that type
        manager.add_entity_type("anime")
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO memories (content) VALUES ('Test')")
        memory_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO entities (text, type, type_source, confidence, memory_id)
            VALUES ('Steins Gate', 'anime', 'user_defined', 0.9, ?)
        """, (memory_id,))
        conn.commit()
        conn.close()
        
        # Try to remove without force
        success, message = manager.remove_entity_type("anime", force=False)
        
        assert success is False
        assert "used in" in message.lower()
        
        # Remove with force
        success, message = manager.remove_entity_type("anime", force=True)
        
        assert success is True
        assert "orphaned" in message.lower()
    
    def test_list_entity_types_empty(self, temp_db):
        """Test listing types with no user-defined types"""
        manager = EntityTypeManager(temp_db)
        
        types = manager.list_entity_types()
        
        assert 'core' in types
        assert 'user_defined' in types
        assert len(types['core']) == 4  # 4 core types
        assert len(types['user_defined']) == 0
    
    def test_list_entity_types_with_user_types(self, temp_db):
        """Test listing types with user-defined types"""
        manager = EntityTypeManager(temp_db)
        
        manager.add_entity_type("anime")
        manager.add_entity_type("car_model")
        
        types = manager.list_entity_types()
        
        assert len(types['user_defined']) == 2
        type_names = {t.type_name for t in types['user_defined']}
        assert 'anime' in type_names
        assert 'car_model' in type_names
    
    def test_get_entity_type_stats(self, temp_db):
        """Test getting stats for specific type"""
        manager = EntityTypeManager(temp_db)
        
        # Core type stats
        stats = manager.get_entity_type_stats("person")
        assert stats is not None
        assert stats.type_name == "person"
        assert stats.added_at == "core"
        
        # User-defined type stats
        manager.add_entity_type("anime")
        stats = manager.get_entity_type_stats("anime")
        assert stats is not None
        assert stats.type_name == "anime"
        assert stats.added_at != "core"
        
        # Non-existent type
        stats = manager.get_entity_type_stats("nonexistent")
        assert stats is None


class TestReextractionQueue:
    """Tests for ReextractionQueue"""
    
    def test_initialization(self, temp_db):
        """Test queue initialization"""
        queue = ReextractionQueue(temp_db)
        assert queue.db_path == temp_db
    
    def test_add_job(self, temp_db):
        """Test adding a job to the queue"""
        queue = ReextractionQueue(temp_db)
        
        job_id = queue.add_job("anime")
        assert job_id > 0
        
        # Verify job was added
        job = queue.get_job(job_id)
        assert job is not None
        assert job.type_name == "anime"
        assert job.status == "pending"
    
    def test_get_job_not_exists(self, temp_db):
        """Test getting non-existent job"""
        queue = ReextractionQueue(temp_db)
        
        job = queue.get_job(999)
        assert job is None
    
    def test_get_pending_jobs(self, temp_db):
        """Test getting pending jobs"""
        queue = ReextractionQueue(temp_db)
        
        # Add multiple jobs
        queue.add_job("anime")
        queue.add_job("car_model")
        queue.add_job("technology")
        
        pending = queue.get_pending_jobs()
        
        assert len(pending) == 3
        assert all(j.status == "pending" for j in pending)
    
    def test_get_queue_status_empty(self, temp_db):
        """Test queue status with no jobs"""
        queue = ReextractionQueue(temp_db)
        
        status = queue.get_queue_status()
        
        assert status['pending'] == 0
        assert status['processing'] == 0
        assert status['completed'] == 0
        assert status['failed'] == 0
    
    def test_get_queue_status_with_jobs(self, temp_db):
        """Test queue status with multiple jobs"""
        queue = ReextractionQueue(temp_db)
        
        queue.add_job("type1")
        queue.add_job("type2")
        
        status = queue.get_queue_status()
        
        assert status['pending'] == 2
    
    def test_get_recent_jobs(self, temp_db):
        """Test getting recent jobs"""
        queue = ReextractionQueue(temp_db)
        
        # Add jobs
        for i in range(15):
            queue.add_job(f"type{i}")
        
        # Get recent 10
        recent = queue.get_recent_jobs(limit=10)
        
        assert len(recent) == 10
        # Should be sorted by queued_at DESC
        assert recent[0].type_name == "type14"
    
    def test_start_job(self, temp_db):
        """Test starting a job"""
        queue = ReextractionQueue(temp_db)
        
        job_id = queue.add_job("anime")
        success = queue.start_job(job_id, memories_total=100)
        
        assert success is True
        
        job = queue.get_job(job_id)
        assert job.status == "processing"
        assert job.memories_total == 100
        assert job.started_at is not None
    
    def test_update_progress(self, temp_db):
        """Test updating job progress"""
        queue = ReextractionQueue(temp_db)
        
        job_id = queue.add_job("anime")
        queue.start_job(job_id, memories_total=100)
        
        success = queue.update_progress(job_id, memories_processed=50, entities_found=25)
        
        assert success is True
        
        job = queue.get_job(job_id)
        assert job.memories_processed == 50
        assert job.entities_found == 25
        assert job.progress_percent == 50.0
    
    def test_complete_job(self, temp_db):
        """Test completing a job"""
        queue = ReextractionQueue(temp_db)
        
        job_id = queue.add_job("anime")
        queue.start_job(job_id, memories_total=100)
        
        success = queue.complete_job(job_id, entities_found=42)
        
        assert success is True
        
        job = queue.get_job(job_id)
        assert job.status == "completed"
        assert job.entities_found == 42
        assert job.completed_at is not None
    
    def test_fail_job(self, temp_db):
        """Test failing a job"""
        queue = ReextractionQueue(temp_db)
        
        job_id = queue.add_job("anime")
        queue.start_job(job_id, memories_total=100)
        
        success = queue.fail_job(job_id, error_message="Test error")
        
        assert success is True
        
        job = queue.get_job(job_id)
        assert job.status == "failed"
        assert job.error_message == "Test error"
        assert job.completed_at is not None


class TestIntegration:
    """Integration tests for Day 7"""
    
    def test_full_workflow_add_type_and_queue(self, temp_db):
        """Test complete workflow: add type → queue re-extraction"""
        manager = EntityTypeManager(temp_db)
        queue = ReextractionQueue(temp_db)
        
        # Add entity type (should queue re-extraction)
        success = manager.add_entity_type("anime")
        assert success is True
        
        # Check queue
        pending = queue.get_pending_jobs()
        assert len(pending) == 1
        assert pending[0].type_name == "anime"
    
    def test_full_workflow_suggestions_to_addition(self, temp_db):
        """Test workflow: get suggestions → add suggested type"""
        # Setup: Add frequent tags
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        for i in range(1, 8):
            cursor.execute("INSERT INTO memories (content) VALUES (?)", (f"Memory {i}",))
            memory_id = cursor.lastrowid
            cursor.execute("INSERT INTO memory_tags (memory_id, tag) VALUES (?, 'anime')", (memory_id,))
        
        conn.commit()
        conn.close()
        
        # Get suggestions
        manager = EntityTypeManager(temp_db)
        suggestions = manager.suggest_entity_types()
        
        assert len(suggestions) > 0
        anime_suggestion = next(s for s in suggestions if s.type_name == 'anime')
        
        # Add suggested type
        success = manager.add_entity_type(anime_suggestion.type_name)
        assert success is True
        
        # Verify it's in user types
        types = manager.list_entity_types()
        assert any(t.type_name == 'anime' for t in types['user_defined'])


def run_tests():
    """Run all tests"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()