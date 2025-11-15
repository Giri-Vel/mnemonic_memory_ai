import sqlite3
import sys
from datetime import datetime

def upgrade_schema(conn):
    cur = conn.cursor()

    # Fetch existing columns in entities
    cur.execute("PRAGMA table_info(entities)")
    existing_cols = [row[1] for row in cur.fetchall()]

    # Add new entity columns
    new_entity_columns = [
        ("first_seen", "TIMESTAMP", "CURRENT_TIMESTAMP"),
        ("last_seen", "TIMESTAMP", "CURRENT_TIMESTAMP"),
        ("centrality", "REAL", "0.0"),
        ("community_id", "INTEGER", None)
    ]

    for col, col_type, default in new_entity_columns:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE entities ADD COLUMN {col} {col_type}")
            if default is not None:
                cur.execute(f"UPDATE entities SET {col} = {default} WHERE {col} IS NULL")

    # Fetch existing columns in relationships
    cur.execute("PRAGMA table_info(relationships)")
    rel_cols = [row[1] for row in cur.fetchall()]

    # Add relationship_type to relationships table
    if "relationship_type" not in rel_cols:
        cur.execute("ALTER TABLE relationships ADD COLUMN relationship_type TEXT")
        cur.execute("UPDATE relationships SET relationship_type = 'co-occurs' WHERE relationship_type IS NULL")

    conn.commit()


def merge_data(dest_conn, src_path):
    cur = dest_conn.cursor()

    # Attach source DB
    cur.execute(f"ATTACH DATABASE '{src_path}' AS src")

    # --- Merge memories ---
    cur.execute("""
        INSERT OR IGNORE INTO memories (id, content, created_at, category, metadata)
        SELECT id, content, created_at, category, metadata
        FROM src.memories
    """)

    # --- Merge entities ---
    cur.execute("""
        INSERT OR IGNORE INTO entities (
            id, name, type, frequency, community_id,
            centrality, memory_id, first_seen, last_seen
        )
        SELECT 
            id, name, type, frequency, community_id,
            centrality, memory_id, first_seen, last_seen
        FROM src.entities
    """)

    # --- Merge relationships ---
    cur.execute("""
        INSERT OR IGNORE INTO relationships (
            id, entity1_id, entity2_id, co_occurrence, relationship_type
        )
        SELECT 
            id, entity1_id, entity2_id, co_occurrence, relationship_type
        FROM src.relationships
    """)

    dest_conn.commit()
    cur.execute("DETACH src")
    dest_conn.commit()


def main():
    if len(sys.argv) != 3:
        print("Usage: python merge_databases.py <dest_mnemonic.db> <src_my_knowledge.db>")
        sys.exit(1)

    dest_path = sys.argv[1]
    src_path = sys.argv[2]

    print(f"Opening destination DB: {dest_path}")
    dest_conn = sqlite3.connect(dest_path)

    print("💾 Upgrading schema...")
    upgrade_schema(dest_conn)

    print("🔄 Merging data from:", src_path)
    merge_data(dest_conn, src_path)

    print("✅ Merge complete!")
    print("You can now safely use mnemonic.db for Day 6 workflows.")

    dest_conn.close()


if __name__ == "__main__":
    main()