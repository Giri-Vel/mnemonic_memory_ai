"""
Migration 001: Initial Schema

Creates base tables for Mnemonic memory system:
- memories (core memory storage)
- memory_tags (tag associations)
- schema_version (migration tracking)
"""

import sqlite3
from pathlib import Path


def get_migration_version():
    """Return the version number of this migration"""
    return 1


def upgrade(db_path: str):
    """Apply the migration"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Table 1: Memories (core storage)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table 2: Memory Tags
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE,
                UNIQUE(memory_id, tag)
            )
        """)
        
        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_tags_memory_id 
            ON memory_tags(memory_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_tags_tag 
            ON memory_tags(tag)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_created 
            ON memories(created_at)
        """)
        
        # Schema version tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
        cursor.execute("DROP TABLE IF EXISTS memory_tags")
        cursor.execute("DROP TABLE IF EXISTS memories")
        cursor.execute("DROP TABLE IF EXISTS schema_version")
        
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
        print("Usage: python 001_initial_schema.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    upgrade(db_path)