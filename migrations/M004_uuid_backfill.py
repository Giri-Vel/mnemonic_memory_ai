#!/usr/bin/env python3
"""
Backfill UUIDs for Existing Memories (OPTIONAL)

This script populates the uuid column for memories that were created
before the M004 migration. It reads from JSON storage and updates SQLite.

Usage:
    python backfill_uuids.py

What it does:
    1. Reads all memories from JSON storage
    2. For each memory without a UUID in SQLite:
       - Updates the uuid column with the Memory.id from JSON
    3. Reports statistics

Safe to run multiple times (idempotent).
"""

import json
import sqlite3
from pathlib import Path


def backfill_uuids(json_path: str, db_path: str):
    """
    Backfill UUIDs for existing memories
    
    Args:
        json_path: Path to memories.json
        db_path: Path to mnemonic.db
    """
    print("\n" + "="*70)
    print("BACKFILL UUIDS FOR EXISTING MEMORIES")
    print("="*70 + "\n")
    
    # Load memories from JSON
    print(f"📖 Reading memories from: {json_path}")
    try:
        with open(json_path, 'r') as f:
            memories = json.load(f)
    except FileNotFoundError:
        print(f"✗ JSON file not found: {json_path}")
        return
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON file: {e}")
        return
    
    print(f"✓ Loaded {len(memories)} memories from JSON\n")
    
    # Connect to SQLite
    print(f"🔗 Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if uuid column exists
    cursor.execute("PRAGMA table_info(memories)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'uuid' not in columns:
        print("✗ UUID column doesn't exist. Run migration M004 first.")
        conn.close()
        return
    
    print("✓ UUID column exists\n")
    
    # Get current state
    cursor.execute("SELECT COUNT(*) FROM memories WHERE uuid IS NULL")
    null_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM memories WHERE uuid IS NOT NULL")
    populated_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM memories")
    total_count = cursor.fetchone()[0]
    
    print("📊 Current State:")
    print(f"   Total memories in SQLite: {total_count}")
    print(f"   With UUIDs: {populated_count}")
    print(f"   Without UUIDs (NULL): {null_count}\n")
    
    if null_count == 0:
        print("✓ All memories already have UUIDs. Nothing to do!\n")
        conn.close()
        return
    
    print(f"🔄 Starting backfill for {null_count} memories...\n")
    
    # Strategy 1: Match by content (most reliable)
    updated_by_content = 0
    skipped = 0
    errors = []
    
    for mem_id, mem_data in memories.items():
        content = mem_data.get('content', '')
        
        if not content:
            skipped += 1
            continue
        
        try:
            # Find memory in SQLite by content
            cursor.execute("""
                SELECT id, uuid FROM memories 
                WHERE content = ? AND uuid IS NULL
                LIMIT 1
            """, (content,))
            
            result = cursor.fetchone()
            
            if result:
                sqlite_id, current_uuid = result
                
                # Update with UUID from JSON
                cursor.execute("""
                    UPDATE memories 
                    SET uuid = ? 
                    WHERE id = ?
                """, (mem_id, sqlite_id))
                
                updated_by_content += 1
                
                if updated_by_content % 10 == 0:
                    print(f"   Processed {updated_by_content} memories...")
        
        except Exception as e:
            errors.append(f"Error processing memory {mem_id}: {e}")
    
    # Commit changes
    conn.commit()
    
    # Get final state
    cursor.execute("SELECT COUNT(*) FROM memories WHERE uuid IS NULL")
    remaining_null = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM memories WHERE uuid IS NOT NULL")
    final_populated = cursor.fetchone()[0]
    
    conn.close()
    
    # Report results
    print("\n" + "="*70)
    print("BACKFILL COMPLETE")
    print("="*70 + "\n")
    
    print(f"✓ Updated: {updated_by_content} memories")
    print(f"⊘ Skipped: {skipped} memories (empty content)")
    
    if errors:
        print(f"✗ Errors: {len(errors)}")
        for error in errors[:5]:  # Show first 5 errors
            print(f"   - {error}")
        if len(errors) > 5:
            print(f"   ... and {len(errors) - 5} more")
    
    print(f"\n📊 Final State:")
    print(f"   Total memories: {total_count}")
    print(f"   With UUIDs: {final_populated}")
    print(f"   Without UUIDs: {remaining_null}")
    
    if remaining_null > 0:
        print(f"\n⚠️  {remaining_null} memories still without UUIDs")
        print(f"   These are likely memories that exist in SQLite but not in JSON")
        print(f"   They will be ignored by the system (SQLite only reads UUID matches)")
    
    print()


def main():
    """Main entry point"""
    import os
    from mnemonic.config import JSON_PATH, DB_PATH
    
    # Use paths from config
    json_path = JSON_PATH if os.path.exists(JSON_PATH) else ".mnemonic/memories.json"
    db_path = DB_PATH if os.path.exists(DB_PATH) else ".mnemonic/mnemonic.db"
    
    print(f"\nUsing paths:")
    print(f"  JSON: {json_path}")
    print(f"  SQLite: {db_path}")
    
    # Confirm before proceeding
    response = input("\n⚠️  This will update your database. Continue? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("\nAborted. No changes made.")
        return
    
    # Run backfill
    backfill_uuids(json_path, db_path)


if __name__ == "__main__":
    main()