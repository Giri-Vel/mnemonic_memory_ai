#!/usr/bin/env python3
"""
Diagnostic Script - Compare JSON and SQLite Memories

This helps understand why memories aren't matching during backfill.
"""

import json
import sqlite3
from pathlib import Path


def diagnose_storage_mismatch(json_path: str, db_path: str):
    """Compare memories in JSON and SQLite"""
    
    print("\n" + "="*70)
    print("STORAGE DIAGNOSTIC TOOL")
    print("="*70 + "\n")
    
    # Load JSON memories
    print(f"📖 Reading JSON: {json_path}")
    try:
        with open(json_path, 'r') as f:
            json_memories = json.load(f)
        print(f"✓ Found {len(json_memories)} memories in JSON\n")
    except Exception as e:
        print(f"✗ Error reading JSON: {e}")
        return
    
    # Load SQLite memories
    print(f"🔗 Reading SQLite: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, content, uuid, created_at FROM memories")
    sqlite_memories = cursor.fetchall()
    print(f"✓ Found {len(sqlite_memories)} memories in SQLite\n")
    
    # Show JSON samples
    print("=" * 70)
    print("JSON MEMORIES (first 3):")
    print("=" * 70)
    for i, (mem_id, mem_data) in enumerate(list(json_memories.items())[:3], 1):
        content = mem_data.get('content', '')[:60]
        tags = mem_data.get('tags', [])
        print(f"\n{i}. UUID: {mem_id[:16]}...")
        print(f"   Content: {content}...")
        print(f"   Tags: {tags}")
    
    # Show SQLite samples
    print("\n" + "=" * 70)
    print("SQLITE MEMORIES (first 3):")
    print("=" * 70)
    for i, (sql_id, content, uuid, created) in enumerate(sqlite_memories[:3], 1):
        print(f"\n{i}. ID: {sql_id}, UUID: {uuid}")
        print(f"   Content: {content[:60]}...")
        print(f"   Created: {created}")
    
    # Check for content matches
    print("\n" + "=" * 70)
    print("MATCHING ANALYSIS:")
    print("=" * 70)
    
    json_contents = {mem['content'] for mem in json_memories.values()}
    sqlite_contents = {row[1] for row in sqlite_memories}
    
    matches = json_contents & sqlite_contents
    json_only = json_contents - sqlite_contents
    sqlite_only = sqlite_contents - json_contents
    
    print(f"\n📊 Content Comparison:")
    print(f"   Exact matches: {len(matches)}")
    print(f"   Only in JSON: {len(json_only)}")
    print(f"   Only in SQLite: {len(sqlite_only)}")
    
    if len(matches) > 0:
        print(f"\n✓ Found {len(matches)} matching memories!")
        print("   These can be backfilled.")
    
    if len(json_only) > 0:
        print(f"\n⚠️  {len(json_only)} memories only in JSON:")
        for content in list(json_only)[:3]:
            print(f"   - {content[:60]}...")
    
    if len(sqlite_only) > 0:
        print(f"\n⚠️  {len(sqlite_only)} memories only in SQLite:")
        for content in list(sqlite_only)[:3]:
            print(f"   - {content[:60]}...")
    
    # Check if SQLite is empty or test data
    print("\n" + "=" * 70)
    print("DIAGNOSIS:")
    print("=" * 70)
    
    if len(sqlite_memories) == 0:
        print("\n✓ SQLite is empty - this is fine!")
        print("   New memories will automatically get UUIDs.")
    elif len(matches) == 0:
        print("\n⚠️  No matching memories found!")
        print("\nPossible reasons:")
        print("   1. SQLite has test data from entity extraction testing")
        print("   2. SQLite was populated separately")
        print("   3. Content has been modified")
        print("\n💡 Recommended actions:")
        print("   Option 1: Clear SQLite and start fresh:")
        print("      sqlite3 .mnemonic/mnemonic.db 'DELETE FROM memories'")
        print("   Option 2: Keep SQLite as-is, new memories will get UUIDs")
    else:
        print(f"\n✓ Found {len(matches)} memories that can be backfilled!")
    
    conn.close()
    print("\n" + "="*70 + "\n")


def main():
    """Main entry point"""
    from mnemonic.config import JSON_PATH, DB_PATH
    
    diagnose_storage_mismatch(JSON_PATH, DB_PATH)


if __name__ == "__main__":
    main()