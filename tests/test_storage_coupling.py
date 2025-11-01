#!/usr/bin/env python3
"""
Test script for verifying SQLite storage coupling

This script tests:
1. Memory storage to all three systems (JSON + ChromaDB + SQLite)
2. Verification that data exists in SQLite
3. Tag storage in memory_tags table
4. UUID cross-referencing
"""

import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

# You'll need to update these imports to match your actual project structure
# For testing, we'll use the local version
sys.path.insert(0, '/home/claude')

def test_storage_coupling():
    """Test the integrated storage system"""
    
    print("\n" + "="*70)
    print("STORAGE COUPLING TEST")
    print("="*70 + "\n")
    
    # Create temporary directory for test
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Test directory: {temp_dir}\n")
    
    try:
        # Setup paths
        json_path = Path(temp_dir) / "memories.json"
        vector_path = Path(temp_dir) / "chroma"
        db_path = Path(temp_dir) / "test.db"
        
        # Create database and run migrations
        print("⚙️  Setting up test database...")
        
        # Create tables (simplified for test)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                uuid TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE memory_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE INDEX idx_memories_uuid ON memories(uuid)
        """)
        
        conn.commit()
        conn.close()
        
        print("✓ Database tables created\n")
        
        # Now we need to patch the config to use our test database
        # This is a bit hacky but works for testing
        import mnemonic.config as config
        original_db_path = config.DB_PATH
        config.DB_PATH = str(db_path)
        
        # Import the memory system AFTER patching config
        from memory_system_integrated import MemorySystem
        
        print("🚀 Initializing MemorySystem...")
        system = MemorySystem(
            json_path=str(json_path),
            vector_path=str(vector_path)
        )
        print("✓ MemorySystem initialized\n")
        
        # TEST 1: Add a memory with tags
        print("TEST 1: Adding memory with tags")
        print("-" * 70)
        
        memory = system.add(
            content="Testing SQLite integration with anime and coding",
            tags=["anime", "coding", "test"]
        )
        
        print(f"✓ Memory added: {memory.id[:8]}...")
        print(f"  Content: {memory.content[:50]}...")
        print(f"  Tags: {', '.join(memory.tags)}\n")
        
        # Verify in SQLite
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check memories table
        cursor.execute("SELECT id, content, uuid FROM memories WHERE uuid = ?", (memory.id,))
        result = cursor.fetchone()
        
        if result:
            sqlite_id, content, uuid = result
            print(f"✓ Found in SQLite memories table:")
            print(f"  SQLite ID: {sqlite_id}")
            print(f"  UUID: {uuid}")
            print(f"  Content: {content[:50]}...\n")
        else:
            print("✗ NOT FOUND in SQLite memories table!\n")
            return False
        
        # Check memory_tags table
        cursor.execute("""
            SELECT tag FROM memory_tags WHERE memory_id = ?
        """, (sqlite_id,))
        
        tags_in_db = [row[0] for row in cursor.fetchall()]
        print(f"✓ Found {len(tags_in_db)} tags in memory_tags table:")
        for tag in tags_in_db:
            print(f"  - {tag}")
        print()
        
        if set(tags_in_db) != set(memory.tags):
            print(f"✗ Tag mismatch!")
            print(f"  Expected: {set(memory.tags)}")
            print(f"  Got: {set(tags_in_db)}\n")
            return False
        
        conn.close()
        
        # TEST 2: Add another memory
        print("TEST 2: Adding second memory")
        print("-" * 70)
        
        memory2 = system.add(
            content="Another test memory about machine learning",
            tags=["ml", "ai"]
        )
        
        print(f"✓ Memory added: {memory2.id[:8]}...")
        print(f"  Tags: {', '.join(memory2.tags)}\n")
        
        # Check total count
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memories")
        count = cursor.fetchone()[0]
        conn.close()
        
        print(f"✓ Total memories in SQLite: {count}\n")
        
        if count != 2:
            print(f"✗ Expected 2 memories, got {count}\n")
            return False
        
        # TEST 3: Verify stats
        print("TEST 3: System statistics")
        print("-" * 70)
        
        stats = system.get_stats()
        
        print(f"Total memories (JSON): {stats['total_memories']}")
        print(f"Total memories (SQLite): {stats['sqlite_memories']}")
        print(f"Unique tags: {stats['unique_tags']}")
        print(f"Vector store count: {stats['vector_store']['total_memories']}\n")
        
        if stats['total_memories'] != stats['sqlite_memories']:
            print(f"✗ Memory count mismatch between JSON and SQLite!\n")
            return False
        
        # TEST 4: Update a memory
        print("TEST 4: Updating memory")
        print("-" * 70)
        
        updated = system.update(
            memory_id=memory.id,
            content="Updated content about SQLite integration",
            tags=["anime", "database", "updated"]
        )
        
        print(f"✓ Memory updated: {updated.id[:8]}...")
        print(f"  New content: {updated.content[:50]}...")
        print(f"  New tags: {', '.join(updated.tags)}\n")
        
        # Verify update in SQLite
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT content FROM memories WHERE uuid = ?", (memory.id,))
        updated_content = cursor.fetchone()[0]
        
        if updated_content != updated.content:
            print(f"✗ Content not updated in SQLite!\n")
            return False
        
        print(f"✓ SQLite content updated correctly\n")
        
        # Check updated tags
        cursor.execute("""
            SELECT t.tag FROM memory_tags t
            JOIN memories m ON t.memory_id = m.id
            WHERE m.uuid = ?
        """, (memory.id,))
        
        updated_tags = {row[0] for row in cursor.fetchall()}
        
        if updated_tags != set(updated.tags):
            print(f"✗ Tags not updated correctly in SQLite!")
            print(f"  Expected: {set(updated.tags)}")
            print(f"  Got: {updated_tags}\n")
            return False
        
        print(f"✓ SQLite tags updated correctly\n")
        conn.close()
        
        # TEST 5: Delete a memory
        print("TEST 5: Deleting memory")
        print("-" * 70)
        
        success = system.delete(memory2.id)
        
        if not success:
            print(f"✗ Delete failed!\n")
            return False
        
        print(f"✓ Memory deleted: {memory2.id[:8]}...\n")
        
        # Verify deletion in SQLite
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM memories WHERE uuid = ?", (memory2.id,))
        count = cursor.fetchone()[0]
        
        if count != 0:
            print(f"✗ Memory still exists in SQLite!\n")
            return False
        
        print(f"✓ Memory deleted from SQLite\n")
        
        # Check final count
        cursor.execute("SELECT COUNT(*) FROM memories")
        final_count = cursor.fetchone()[0]
        
        print(f"✓ Final SQLite count: {final_count}\n")
        
        conn.close()
        
        # Restore original config
        config.DB_PATH = original_db_path
        
        print("="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"🧹 Cleaned up test directory\n")


if __name__ == "__main__":
    success = test_storage_coupling()
    sys.exit(0 if success else 1)