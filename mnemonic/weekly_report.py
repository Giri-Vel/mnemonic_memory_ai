#!/usr/bin/env python3
"""
weekly_report.py

Generates a simple text weekly learning report using a rolling 7-day window.
Usage:
    python weekly_report.py <path_to_mnemonic.db>

Output: simple text (stdout)
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import json
import argparse

DATE_FMT = "%Y-%m-%d %H:%M:%S"

def parse_ts(ts):
    # Accepts common SQLite timestamp formats; returns a datetime or None
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts)
        except Exception:
            return None
    if isinstance(ts, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(ts, fmt)
            except Exception:
                continue
    return None

def fetch_counts(conn, start_dt, end_dt):
    """
    Return tuple:
      - memories_count
      - entity_count (entities with first_seen or last_seen in window)
      - connections_count (relationships where either entity had first_seen/last_seen in window)
      - daily_memories: dict(date_str -> count) for window
      - top_entity_types: Counter of entity types discovered in window (by first_seen)
    """
    cur = conn.cursor()

    start = start_dt.strftime(DATE_FMT)
    end = end_dt.strftime(DATE_FMT)

    # Memories in window
    cur.execute(
        "SELECT created_at FROM memories WHERE created_at >= ? AND created_at < ?",
        (start, end),
    )
    mem_rows = cur.fetchall()
    memories_count = len(mem_rows)

    # Daily counts
    daily_counter = Counter()
    for (ts_val,) in mem_rows:
        dt = parse_ts(ts_val)
        if dt:
            daily_counter[dt.date().isoformat()] += 1

    # Entities - consider first_seen/last_seen. If both missing, fallback to memory_id mapping.
    # Entities with first_seen in window
    cur.execute(
        """
        SELECT id, name, type, first_seen, last_seen FROM entities
        """
    )
    ent_rows = cur.fetchall()

    entities_in_window = []
    entity_types_counter = Counter()
    ent_ids_in_window = set()
    for row in ent_rows:
        ent_id, name, ent_type, first_seen, last_seen = row
        fs = parse_ts(first_seen)
        ls = parse_ts(last_seen)
        in_window = False
        if fs and start_dt <= fs < end_dt:
            in_window = True
        elif ls and start_dt <= ls < end_dt:
            in_window = True
        # fallback: if entity has memory_id pointing to a memory in window
        if not in_window:
            # fetch memory_id if present
            # NOTE: memory_id column may be NULL; avoid extra queries for performance unless needed
            # We'll query by entity id only if we didn't detect an in-window timestamp
            pass

        if in_window:
            entities_in_window.append((ent_id, ent_type))
            entity_types_counter[ent_type] += 1
            ent_ids_in_window.add(ent_id)

    entity_count = len(entities_in_window)

    # Connections: relationships where either entity1 or entity2 is in ent_ids_in_window
    if ent_ids_in_window:
        placeholders = ",".join("?" for _ in ent_ids_in_window)
        query = f"""
            SELECT COUNT(*) FROM relationships
            WHERE entity1_id IN ({placeholders}) OR entity2_id IN ({placeholders})
        """
        params = tuple(list(ent_ids_in_window) + list(ent_ids_in_window))
        cur.execute(query, params)
        connections_count = cur.fetchone()[0] or 0
    else:
        connections_count = 0

    return memories_count, entity_count, connections_count, daily_counter, entity_types_counter

def safe_div(a, b):
    if b == 0:
        return None
    return a / b

def pct_str(a, b):
    if b == 0:
        return "N/A"
    change = (a - b) / b * 100
    sign = "↑" if change > 0 else ("↓" if change < 0 else "→")
    return f"{sign}{abs(change):.0f}%"

def simple_report(dest_db_path, output_json=False):
    conn = sqlite3.connect(dest_db_path)
    conn.row_factory = sqlite3.Row

    now = datetime.now()
    end_dt = now
    start_dt = now - timedelta(days=7)
    prev_start = now - timedelta(days=14)
    prev_end = now - timedelta(days=7)

    # Fetch current window stats
    (
        mem_cur,
        ent_cur,
        conn_cur,
        daily_cur,
        types_cur,
    ) = fetch_counts(conn, start_dt, end_dt)

    # Fetch previous window stats
    (
        mem_prev,
        ent_prev,
        conn_prev,
        daily_prev,
        types_prev,
    ) = fetch_counts(conn, prev_start, prev_end)

    # Quality metrics
    knowledge_density_cur = safe_div(conn_cur, ent_cur)  # connections per entity
    knowledge_density_prev = safe_div(conn_prev, ent_prev)

    # Topic diversity: number of distinct entity types / total entities seen in window
    type_diversity_cur = safe_div(len(types_cur), max(ent_cur, 1))
    type_diversity_prev = safe_div(len(types_prev), max(ent_prev, 1))

    # Connection growth rate (relative)
    if conn_prev == 0:
        conn_growth = None
    else:
        conn_growth = (conn_cur - conn_prev) / conn_prev

    # Most productive days (top 3)
    top_days = daily_cur.most_common(3)

    # Most active topics by count (from entity types newly seen in window)
    top_types = types_cur.most_common(5)

    # Learning streaks (consecutive days with >=1 memory in window)
    # build list of counts per day for the last 7 days (from start_dt to end_dt-1)
    streak_counts = []
    day_cursor = start_dt.date()
    while day_cursor < end_dt.date() or (day_cursor == end_dt.date() and start_dt.date() != end_dt.date()):
        day_iso = day_cursor.isoformat()
        streak_counts.append(1 if daily_cur.get(day_iso, 0) > 0 else 0)
        day_cursor = day_cursor + timedelta(days=1)

    # longest streak in window
    longest = 0
    cur_streak = 0
    for v in streak_counts:
        if v:
            cur_streak += 1
            if cur_streak > longest:
                longest = cur_streak
        else:
            cur_streak = 0

    if output_json:
        return {
            "memories_current": mem_cur,
            "memories_previous": mem_prev,
            "entities_current": ent_cur,
            "entities_previous": ent_prev,
            "connections_current": conn_cur,
            "connections_previous": conn_prev,
            "knowledge_density": knowledge_density_cur,
            "topic_diversity": type_diversity_cur,
            "longest_streak": longest,
            "top_days": daily_cur,
            "top_entity_types": types_cur
        }

    # Compose simple text report
    print("=" * 70)
    print(f"📅 WEEKLY LEARNING REPORT — Rolling 7 days ending {end_dt.strftime(DATE_FMT)}")
    print("=" * 70)
    # Memories
    mem_line = f"Memories: {mem_cur}"
    if mem_prev is not None:
        mem_line += f" (prev {mem_prev})"
    print(mem_line)

    # Entities
    ent_line = f"Entities (new/seen this window): {ent_cur}"
    if ent_prev is not None:
        ent_line += f" (prev {ent_prev})"
    print(ent_line)

    # Connections
    conn_line = f"Connections: {conn_cur}"
    if conn_prev is not None:
        conn_line += f" (prev {conn_prev})"
    print(conn_line)

    # Simple trend lines
    print()
    print("Trends:")
    # percent strings
    try:
        print(f"  Memories change: {pct_str(mem_cur, mem_prev)}")
    except Exception:
        print("  Memories change: N/A")

    try:
        print(f"  Entities change: {pct_str(ent_cur, ent_prev)}")
    except Exception:
        print("  Entities change: N/A")

    try:
        print(f"  Connections change: {pct_str(conn_cur, conn_prev)}")
    except Exception:
        print("  Connections change: N/A")

    # Quality
    print()
    print("Quality metrics:")
    if knowledge_density_cur is None:
        print("  Knowledge density (connections/entity): N/A")
    else:
        print(f"  Knowledge density (connections/entity): {knowledge_density_cur:.2f}")

    if type_diversity_cur is None:
        print("  Topic diversity (types / entities): N/A")
    else:
        print(f"  Topic diversity (types/entities): {type_diversity_cur:.2f}")

    # Streaks and productivity
    print()
    print("Activity:")
    print(f"  Longest streak in window: {longest} day(s)")
    if top_days:
        pretty_days = ", ".join([f"{d} ({c})" for d, c in top_days])
        print(f"  Top days: {pretty_days}")
    else:
        print("  Top days: none")

    if top_types:
        print("  Top new entity types:", ", ".join([f"{t} ({c})" for t, c in top_types]))
    else:
        print("  Top new entity types: none")

    # Actionable suggestion (very simple)
    print()
    print("Suggested focus:")
    suggestions = []
    if knowledge_density_cur is not None and knowledge_density_cur < 1:
        suggestions.append("Try connecting related entities — increase links per topic.")
    if type_diversity_cur is not None and type_diversity_cur < 0.2:
        suggestions.append("Broaden topic types to improve diversity.")
    if mem_cur < 5:
        suggestions.append("Increase memory capture frequency (aim for 1–2/day).")
    if not suggestions:
        suggestions.append("Keep the current pace — focus on deeper connections.")

    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. {s}")

    print("=" * 70)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()
    if args.format == "json":
        report = simple_report(args.db_path, output_json=True)
        print(json.dumps(report, indent=2))
    else:
        simple_report(args.db_path)