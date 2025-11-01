"""
Migration 003: Add Re-extraction Queue Table

Creates infrastructure for background re-extraction when new entity types are added.

Tables:
- reextraction_queue: Tracks pending/processing/completed re-extraction jobs
"""

import sqlite3
from pathlib import Path


def get_migration_version():
    """Return the version number of this migration"""
    return 3


def upgrade(db_path: str):
    """Apply the migration"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Table: Re-extraction Queue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reextraction_queue (
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
        
        # Indexes for queue management
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reextraction_status
            ON reextraction_queue(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reextraction_queued
            ON reextraction_queue(queued_at)
        """)
        
        # Update schema version
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            INSERT INTO schema_version (version) VALUES (?)
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
        cursor.execute("DROP TABLE IF EXISTS reextraction_queue")
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
        print("Usage: python M003_add_reextraction_queue.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    upgrade(db_path)