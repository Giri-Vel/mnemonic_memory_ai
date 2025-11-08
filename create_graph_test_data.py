#!/usr/bin/env python3
"""
Quick Setup Script for Graph Explorer

Creates test entity data so you can try the graph explorer immediately.
Run this if you get "no such table: entities" error.

Usage:
    python create_test_data.py
"""

import sqlite3
import os

def create_test_data(db_path='mnemonic.db'):
    """Create test entities and relationships."""
    
    print(f"Creating test data in {db_path}...")
    
    # Connect to database
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    
    # Create entities table
    print("  Creating entities table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            memory_id INTEGER,
            community_id INTEGER,
            centrality REAL
        )
    """)
    
    # Create relationships table
    print("  Creating relationships table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity1_id INTEGER NOT NULL,
            entity2_id INTEGER NOT NULL,
            co_occurrence INTEGER DEFAULT 1,
            FOREIGN KEY (entity1_id) REFERENCES entities(id),
            FOREIGN KEY (entity2_id) REFERENCES entities(id),
            UNIQUE(entity1_id, entity2_id)
        )
    """)
    
    # Insert test entities
    print("  Inserting test entities...")
    entities = [
        # Community 1: Web Development
        ('Python', 'technology', 15, 1, 1, 0.85),
        ('JavaScript', 'technology', 12, 2, 1, 0.75),
        ('TypeScript', 'technology', 10, 3, 1, 0.70),
        ('React', 'technology', 8, 4, 1, 0.65),
        
        # Community 2: Data & Backend
        ('PostgreSQL', 'technology', 7, 5, 2, 0.60),
        ('MongoDB', 'technology', 5, 6, 2, 0.45),
        ('FastAPI', 'technology', 6, 7, 2, 0.50),
        
        # Community 3: DevOps
        ('Docker', 'technology', 9, 8, 3, 0.55),
        ('Kubernetes', 'technology', 4, 9, 3, 0.40),
        ('AWS', 'technology', 6, 10, 3, 0.48),
    ]
    
    cursor.executemany("""
        INSERT OR IGNORE INTO entities 
        (name, type, frequency, memory_id, community_id, centrality)
        VALUES (?, ?, ?, ?, ?, ?)
    """, entities)
    
    # Insert test relationships
    print("  Creating relationships...")
    relationships = [
        # Web dev cluster (strong connections)
        (1, 2, 10),   # Python-JavaScript
        (2, 3, 8),    # JavaScript-TypeScript
        (3, 4, 7),    # TypeScript-React
        (2, 4, 6),    # JavaScript-React
        (1, 3, 5),    # Python-TypeScript
        
        # Data/Backend cluster
        (1, 5, 8),    # Python-PostgreSQL (bridge)
        (1, 7, 6),    # Python-FastAPI
        (5, 6, 3),    # PostgreSQL-MongoDB
        (7, 5, 5),    # FastAPI-PostgreSQL
        
        # DevOps cluster
        (8, 9, 6),    # Docker-Kubernetes
        (9, 10, 4),   # Kubernetes-AWS
        (8, 10, 5),   # Docker-AWS
        
        # Bridges between communities
        (4, 8, 4),    # React-Docker (web to devops)
        (7, 8, 3),    # FastAPI-Docker (backend to devops)
    ]
    
    # Get entity IDs for relationships
    for e1_name_idx, e2_name_idx, weight in relationships:
        cursor.execute("""
            INSERT OR IGNORE INTO relationships 
            (entity1_id, entity2_id, co_occurrence)
            VALUES (?, ?, ?)
        """, (e1_name_idx, e2_name_idx, weight))
    
    # Commit changes
    db.commit()
    
    # Get counts
    cursor.execute("SELECT COUNT(*) FROM entities")
    entity_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM relationships")
    rel_count = cursor.fetchone()[0]
    
    db.close()
    
    print(f"\n✅ Test data created successfully!")
    print(f"   Entities: {entity_count}")
    print(f"   Relationships: {rel_count}")
    print(f"\n🚀 Try these commands:")
    print(f"   mnemonic graph stats")
    print(f"   mnemonic graph important")
    print(f"   mnemonic graph subgraph Python")
    print(f"   mnemonic graph path Python React")
    print()


if __name__ == '__main__':
    import sys
    
    # Get database path
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'mnemonic.db'
    
    # Check if file exists
    if not os.path.exists(db_path):
        print(f"⚠️  Warning: {db_path} not found. Creating new database...")
    
    try:
        create_test_data(db_path)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)