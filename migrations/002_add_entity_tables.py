"""
Migration 002: Add Entity Extraction Tables

Creates tables for:
- tentative_entities (frequency = 1)
- entities (frequency >= 2, confirmed)
- entity_extraction_checkpoints (for fast re-extraction)
- user_entity_types (dynamic entity type management)
"""

import sqlite3
from pathlib import Path


def get_migration_version():
    """Return the version number of this migration"""
    return 2


def upgrade(db_path: str):
    """Apply the migration"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Table 1: Tentative Entities (frequency = 1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tentative_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                type TEXT,
                type_source TEXT NOT NULL,
                confidence REAL NOT NULL,
                memory_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
            )
        """)
        
        # Table 2: Confirmed Entities (frequency >= 2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
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
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
            )
        """)
        
        # Table 3: Entity Extraction Checkpoints
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_extraction_checkpoints (
                memory_id INTEGER PRIMARY KEY,
                noun_phrases TEXT NOT NULL,
                tags TEXT,
                checkpoint_version INTEGER NOT NULL DEFAULT 1,
                extraction_config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
            )
        """)
        
        # Table 4: User-Defined Entity Types
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_entity_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_name TEXT UNIQUE NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                example_entities TEXT,
                memory_count INTEGER DEFAULT 0
            )
        """)
        
        # Indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tentative_text_type 
            ON tentative_entities(text, type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tentative_memory 
            ON tentative_entities(memory_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_text_type 
            ON entities(text, type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_frequency 
            ON entities(frequency)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_cluster 
            ON entities(cluster_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entities_memory 
            ON entities(memory_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoint_version 
            ON entity_extraction_checkpoints(checkpoint_version)
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
        cursor.execute("DROP TABLE IF EXISTS user_entity_types")
        cursor.execute("DROP TABLE IF EXISTS entity_extraction_checkpoints")
        cursor.execute("DROP TABLE IF EXISTS entities")
        cursor.execute("DROP TABLE IF EXISTS tentative_entities")
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
        print("Usage: python 002_add_entity_tables.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    upgrade(db_path)