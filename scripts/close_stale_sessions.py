"""
One-time migration: close sessions that are still is_active=1 but
haven't been updated in more than 24 hours.

Usage:
    python scripts/close_stale_sessions.py [--db PATH] [--dry-run]
"""
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


DEFAULT_DB = Path(__file__).parent.parent / ".mnemonic" / "mnemonic.db"
SUMMARY = "Session auto-closed (stale)"


def close_stale_sessions(db_path: str, dry_run: bool = False) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, start_time, updated_at, memory_count
        FROM sessions
        WHERE is_active = 1
          AND JULIANDAY('now') - JULIANDAY(updated_at) > 1
    """)
    stale = cursor.fetchall()

    if not stale:
        print("No stale sessions found.")
        conn.close()
        return 0

    now = datetime.now().isoformat()

    for row in stale:
        print(
            f"  {'[dry-run] ' if dry_run else ''}Closing session {row['id']}"
            f" | started={row['start_time']}"
            f" | last_updated={row['updated_at']}"
            f" | memories={row['memory_count']}"
        )

    if not dry_run:
        cursor.execute("""
            UPDATE sessions
            SET is_active = 0,
                end_time = ?,
                summary = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE is_active = 1
              AND JULIANDAY('now') - JULIANDAY(updated_at) > 1
        """, (now, SUMMARY))
        conn.commit()
        print(f"\nClosed {cursor.rowcount} stale session(s).")
    else:
        print(f"\n{len(stale)} session(s) would be closed (dry-run, no changes made).")

    conn.close()
    return len(stale)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Close stale active sessions.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to mnemonic.db")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()

    print(f"DB: {args.db}")
    print(f"Mode: {'dry-run' if args.dry_run else 'live'}\n")
    close_stale_sessions(args.db, dry_run=args.dry_run)
