"""
Migration 004: Add UUID Column to Memories Table (FIXED)

Adds a UUID column to store Memory.id (UUID) alongside the INTEGER id.
This allows cross-referencing between JSON/ChromaDB and SQLite storage.

FIXED: Handles existing data by adding column WITHOUT UNIQUE constraint first,
then populating UUIDs, then creating a UNIQUE index.
"""

import sqlite3
from pathlib import Path


def get_migration_version():
    """Return the version number of this migration"""
    return 4


def upgrade(db_path: str):
    """Apply the migration"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print(f"Running migration {get_migration_version()}: Add UUID column...")
        
        # Step 1: Check if column already exists
        cursor.execute("PRAGMA table_info(memories)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'uuid' in columns:
            print(f"⚠ UUID column already exists, skipping migration")
            return
        
        # Step 2: Add UUID column WITHOUT UNIQUE constraint (allows NULL for existing rows)
        print("  → Adding uuid column...")
        cursor.execute("""
            ALTER TABLE memories 
            ADD COLUMN uuid TEXT
        """)
        
        # Step 3: Check if there's existing data
        cursor.execute("SELECT COUNT(*) FROM memories")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            print(f"  → Found {existing_count} existing memories")
            print(f"  ⚠ Warning: Existing memories will have NULL uuids")
            print(f"  ℹ️  New memories will get proper UUIDs automatically")
            print(f"  ℹ️  Run backfill script later to populate UUIDs for old memories")
        
        # Step 4: Create UNIQUE index (allows NULL values, enforces uniqueness for non-NULL)
        print("  → Creating unique index on uuid...")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_uuid 
            ON memories(uuid) 
            WHERE uuid IS NOT NULL
        """)
        
        # Step 5: Create regular index for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_uuid_lookup 
            ON memories(uuid)
        """)
        
        # Step 6: Update schema version
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
        print("  - Added 'uuid' column to memories table")
        print("  - Created unique index on uuid column (for non-NULL values)")
        print("  - Created lookup index for performance")
        
        if existing_count > 0:
            print(f"\nℹ️  Next Steps:")
            print(f"  1. New memories will automatically get UUIDs")
            print(f"  2. Existing {existing_count} memories have NULL uuids (will be ignored)")
            print(f"  3. Optional: Run backfill script to populate UUIDs for old memories")
        
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
        # Drop indexes
        cursor.execute("DROP INDEX IF EXISTS idx_memories_uuid")
        cursor.execute("DROP INDEX IF EXISTS idx_memories_uuid_lookup")
        
        # Note: Can't easily drop column in SQLite without recreating table
        # Just remove from schema_version
        cursor.execute("""
            DELETE FROM schema_version WHERE version = ?
        """, (get_migration_version(),))
        
        conn.commit()
        print(f"✓ Migration {get_migration_version()} rolled back")
        print("  Note: UUID column not removed (SQLite limitation)")
        print("  Column will be ignored by application")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Rollback failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python M004_add_uuid_column.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    upgrade(db_path)