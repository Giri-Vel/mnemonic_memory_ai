"""
Migration 005: Add Sessions

Creates tables for conversation sessions with LLM-generated summaries:
- sessions (session metadata and summaries)
- session_memories (links memories to sessions with sequence)
"""

import sqlite3


def get_migration_version():
    """Return the version number of this migration"""
    return 5


def upgrade(db_path: str):
    """Apply the migration"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Table 1: Sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,              -- UUID
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,               -- NULL if active
                topic TEXT,
                summary TEXT,                     -- LLM-generated summary
                memory_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,      -- 1 = active, 0 = finalized
                metadata TEXT,                    -- JSON for extensibility
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table 2: Session-Memory junction
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_memories (
                session_id TEXT NOT NULL,
                memory_id INTEGER NOT NULL,       -- References memories.id (SQLite rowid)
                sequence_number INTEGER NOT NULL, -- Order within session
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, memory_id),
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
            )
        """)
        
        # Indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_active
            ON sessions(is_active, updated_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_topic
            ON sessions(topic)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_memories_session
            ON session_memories(session_id, sequence_number)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_memories_memory
            ON session_memories(memory_id)
        """)
        
        # Create schema_version table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Update schema version
        cursor.execute("""
            INSERT OR IGNORE INTO schema_version (version) VALUES (?)
        """, (get_migration_version(),))
        
        conn.commit()
        print(f"✓ Migration {get_migration_version()} applied successfully")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Migration {get_migration_version()} failed: {e}")
        raise
    finally:
        conn.close()


def downgrade(db_path: str):
    """Rollback the migration"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DROP TABLE IF EXISTS session_memories")
        cursor.execute("DROP TABLE IF EXISTS sessions")
        cursor.execute("DELETE FROM schema_version WHERE version = ?", 
                      (get_migration_version(),))
        
        conn.commit()
        print(f"✓ Migration {get_migration_version()} rolled back")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Rollback failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python M005_add_sessions.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    upgrade(db_path)