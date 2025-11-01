#!/usr/bin/env python3
"""
View Actual Checkpoints from Database

This script shows you the REAL checkpoints created for your memories,
not the test data.
"""

import sqlite3
import json
import sys
from pathlib import Path


def view_checkpoints(db_path: str, limit: int = 10):
    """View actual checkpoints from the database"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\n{'='*70}")
    print("ACTUAL CHECKPOINTS FROM DATABASE")
    print(f"{'='*70}\n")
    
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM entity_extraction_checkpoints")
    total = cursor.fetchone()[0]
    print(f"📊 Total checkpoints: {total}\n")
    
    if total == 0:
        print("❌ No checkpoints found!")
        print("Make sure entity extraction is integrated into memory_system.py")
        conn.close()
        return
    
    # Get checkpoints with memory content
    cursor.execute("""
        SELECT 
            c.memory_id,
            m.content,
            c.noun_phrases,
            c.checkpoint_version,
            c.created_at
        FROM entity_extraction_checkpoints c
        JOIN memories m ON c.memory_id = m.id
        ORDER BY c.created_at DESC
        LIMIT ?
    """, (limit,))
    
    checkpoints = cursor.fetchall()
    
    for i, (memory_id, content, noun_phrases_json, version, created_at) in enumerate(checkpoints, 1):
        print(f"{'─'*70}")
        print(f"Checkpoint #{i}")
        print(f"{'─'*70}")
        print(f"Memory ID: {memory_id}")
        print(f"Version: {version}")
        print(f"Created: {created_at}")
        print(f"\nContent: {content[:100]}..." if len(content) > 100 else f"\nContent: {content}")
        print()
        
        # Parse and display noun phrases
        try:
            noun_phrases = json.loads(noun_phrases_json)
            
            if noun_phrases:
                print("Noun Phrases with Quality Scores:")
                print("-" * 70)
                
                # Sort by quality score
                sorted_phrases = sorted(
                    noun_phrases, 
                    key=lambda p: p.get('quality_score', 0), 
                    reverse=True
                )
                
                for phrase in sorted_phrases:
                    quality = phrase.get('quality_score', 0)
                    text = phrase['text']
                    pos = ', '.join(phrase.get('pos_tags', []))
                    
                    # Visual quality indicator
                    if quality >= 5:
                        indicator = "🔥"
                    elif quality >= 3:
                        indicator = "✨"
                    elif quality >= 1:
                        indicator = "💡"
                    else:
                        indicator = "  "
                    
                    print(f"{indicator} [{quality:2d}] {text:30s} ({pos})")
            else:
                print("No noun phrases found in this checkpoint")
        
        except json.JSONDecodeError:
            print("⚠️  Error parsing noun phrases")
        
        print()
    
    conn.close()
    
    print(f"{'='*70}")
    print(f"Showing {min(limit, total)} of {total} total checkpoints")
    print(f"{'='*70}\n")


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = ".mnemonic/mnemonic.db"
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print("Usage: python view_checkpoints.py [db_path]")
        sys.exit(1)
    
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    view_checkpoints(db_path, limit)


if __name__ == "__main__":
    main()