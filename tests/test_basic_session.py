"""
Basic tests for session functionality.
Tests migration, LLM providers, and session storage.
"""

import sqlite3
import tempfile
import os
import sys
from pathlib import Path

# Ensure mnemonic package is importable
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
from mnemonic.llm_providers import DummyProvider, get_provider
from mnemonic.sessions import SessionStore, ConversationSession


# Import migration module
def get_migration():
    """Dynamically import the migration module."""
    import importlib.util
    migration_path = project_root / "migrations" / "M005_add_sessions.py"
    spec = importlib.util.spec_from_file_location("M005_add_sessions", migration_path)
    migration_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_module)
    return migration_module.upgrade


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def migrated_db(temp_db):
    """Database with migration applied."""
    apply_migration = get_migration()
    apply_migration(temp_db)
    return temp_db


@pytest.fixture
def full_db(migrated_db):
    """Database with migration and memories table."""
    conn = sqlite3.connect(migrated_db)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            uuid TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    return migrated_db


class TestMigration:
    """Test database migration."""
    
    def test_migration_creates_tables(self, temp_db):
        """Test that migration creates required tables."""
        apply_migration = get_migration()
        apply_migration(temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('sessions', 'session_memories')
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert 'sessions' in tables, "sessions table not created"
        assert 'session_memories' in tables, "session_memories table not created"
    
    def test_migration_creates_indexes(self, migrated_db):
        """Test that migration creates indexes."""
        conn = sqlite3.connect(migrated_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_session%'
        """)
        
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert len(indexes) >= 4, f"Expected at least 4 indexes, got {len(indexes)}"


class TestDummyProvider:
    """Test dummy LLM provider."""
    
    def test_continuity_check_always_true(self):
        """Test dummy provider configured to always continue."""
        provider = DummyProvider(always_continue=True)
        result = provider.check_continuity("Previous context", "New memory")
        assert result == True
    
    def test_continuity_check_always_false(self):
        """Test dummy provider configured to never continue."""
        provider = DummyProvider(always_continue=False)
        result = provider.check_continuity("Previous context", "New memory")
        assert result == False
    
    def test_generate_summary(self):
        """Test summary generation."""
        provider = DummyProvider()
        summary = provider.generate_summary(["Memory 1", "Memory 2"], topic="Test")
        
        assert "Test" in summary, "Summary should include topic"
        assert "2" in summary, "Summary should mention memory count"
    
    def test_suggest_topic(self):
        """Test topic suggestion."""
        provider = DummyProvider()
        topic = provider.suggest_topic(["Some memory"])
        
        assert len(topic) > 0, "Topic should be non-empty"
        assert isinstance(topic, str), "Topic should be a string"


class TestSessionStore:
    """Test session storage operations."""
    
    def test_create_session(self, full_db):
        """Test creating a new session."""
        store = SessionStore(full_db)
        session = store.create_session(topic="Test Session")
        
        assert session.id is not None, "Session should have ID"
        assert session.topic == "Test Session", "Session should have topic"
        assert session.is_active == True, "New session should be active"
    
    def test_add_memory_to_session(self, full_db):
        """Test adding memories to a session."""
        store = SessionStore(full_db)
        session = store.create_session(topic="Test")
        
        # Create test memories
        conn = sqlite3.connect(full_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO memories (content, uuid) VALUES (?, ?)", 
                      ("Memory 1", "uuid-1"))
        mem1_id = cursor.lastrowid
        cursor.execute("INSERT INTO memories (content, uuid) VALUES (?, ?)", 
                      ("Memory 2", "uuid-2"))
        mem2_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Add to session
        store.add_memory_to_session(session.id, mem1_id, sequence_number=1)
        store.add_memory_to_session(session.id, mem2_id, sequence_number=2)
        
        # Verify
        memories = store.get_session_memories(session.id)
        assert len(memories) == 2, "Should have 2 memories"
        assert memories[0]["content"] == "Memory 1"
        assert memories[1]["content"] == "Memory 2"
    
    def test_get_session_memories_in_order(self, full_db):
        """Test that memories are retrieved in sequence order."""
        store = SessionStore(full_db)
        session = store.create_session()
        
        # Create memories in specific order
        conn = sqlite3.connect(full_db)
        cursor = conn.cursor()
        mem_ids = []
        for i in range(5):
            cursor.execute("INSERT INTO memories (content, uuid) VALUES (?, ?)", 
                          (f"Memory {i}", f"uuid-{i}"))
            mem_ids.append(cursor.lastrowid)
        conn.commit()
        conn.close()
        
        # Add in specific sequence
        for seq, mem_id in enumerate(mem_ids, start=1):
            store.add_memory_to_session(session.id, mem_id, sequence_number=seq)
        
        # Verify order
        memories = store.get_session_memories(session.id)
        for i, mem in enumerate(memories):
            assert mem["content"] == f"Memory {i}", f"Memory {i} out of order"
            assert mem["sequence_number"] == i + 1
    
    def test_get_active_session(self, full_db):
        """Test getting the active session."""
        store = SessionStore(full_db)
        
        # No active session initially
        assert store.get_active_session() is None
        
        # Create active session
        session = store.create_session(topic="Active")
        active = store.get_active_session()
        
        assert active is not None
        assert active.id == session.id
        assert active.topic == "Active"
    
    def test_finalize_session(self, full_db):
        """Test finalizing a session."""
        store = SessionStore(full_db)
        session = store.create_session(topic="Test")
        
        # Finalize with summary
        store.finalize_session(session.id, summary="Test summary")
        
        # Verify
        finalized = store.get_session(session.id)
        assert finalized.is_active == False
        assert finalized.summary == "Test summary"
        assert finalized.end_time is not None
    
    def test_no_active_session_after_finalization(self, full_db):
        """Test that finalized session is not returned as active."""
        store = SessionStore(full_db)
        session = store.create_session()
        
        # Should have active session
        assert store.get_active_session() is not None
        
        # Finalize
        store.finalize_session(session.id, summary="Done")
        
        # Should have no active session
        assert store.get_active_session() is None
    
    def test_get_recent_sessions(self, full_db):
        """Test getting recent sessions."""
        store = SessionStore(full_db)
        
        # Create multiple sessions
        s1 = store.create_session(topic="Session 1")
        s2 = store.create_session(topic="Session 2")
        s3 = store.create_session(topic="Session 3")
        
        # Manually update timestamps to ensure ordering
        # (SQLite CURRENT_TIMESTAMP has low precision)
        conn = sqlite3.connect(full_db)
        cursor = conn.cursor()
        cursor.execute("UPDATE sessions SET updated_at = datetime('now', '-2 seconds') WHERE id = ?", (s1.id,))
        cursor.execute("UPDATE sessions SET updated_at = datetime('now', '-1 seconds') WHERE id = ?", (s2.id,))
        cursor.execute("UPDATE sessions SET updated_at = datetime('now') WHERE id = ?", (s3.id,))
        conn.commit()
        conn.close()
        
        # Get recent
        recent = store.get_recent_sessions(n=2)
        
        assert len(recent) == 2
        # Most recent should be first (s3)
        assert recent[0].topic == "Session 3"
        assert recent[1].topic == "Session 2"
    
    def test_find_sessions_by_topic(self, full_db):
        """Test finding sessions by topic."""
        store = SessionStore(full_db)
        
        # Create sessions with different topics
        store.create_session(topic="ChromaDB debugging")
        store.create_session(topic="Entity extraction")
        store.create_session(topic="ChromaDB optimization")
        
        # Search
        results = store.find_sessions_by_topic("ChromaDB")
        
        assert len(results) == 2
        for session in results:
            assert "ChromaDB" in session.topic


class TestProviderFactory:
    """Test LLM provider factory."""
    
    def test_get_dummy_provider(self):
        """Test getting dummy provider from factory."""
        provider = get_provider("dummy", always_continue=False)
        assert isinstance(provider, DummyProvider)
    
    def test_invalid_provider_raises_error(self):
        """Test that invalid provider name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("invalid_provider")


if __name__ == "__main__":
    # Allow running directly for quick checks
    pytest.main([__file__, "-v"])