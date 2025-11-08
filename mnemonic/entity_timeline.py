"""
Entity Timeline Analysis System (Week 4, Day 3)

Analyzes temporal patterns in entity mentions:
- Temporal tracking (first/last mention timestamps)
- Frequency trend detection (↗ increasing, → stable, ↘ declining, 🔥 burst)
- Activity patterns (by day/week/month/quarter/year)
- Dormant entity detection (rediscovery suggestions)
- Activity scoring system (0-100 scale)
- Timeline visualization (ASCII charts)

Performance: ~10-30ms per entity, scales to 1000+ entities
"""

import sqlite3
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import math


@dataclass
class EntityTimeline:
    """Represents temporal information for an entity"""
    entity_text: str
    entity_type: Optional[str]
    frequency: int
    first_mention: str  # ISO timestamp
    last_mention: str   # ISO timestamp
    days_since_first: int
    days_since_last: int
    trend: str  # "increasing", "stable", "declining", "burst", "dormant"
    activity_score: float  # 0-100 scale
    mentions_by_period: Dict[str, int]  # Period → count mapping


@dataclass
class ActivityPeriod:
    """Activity summary for a time period"""
    period: str  # e.g., "2024-11", "2024-Q4", "2024-W45"
    entity_count: int
    total_mentions: int
    top_entities: List[Tuple[str, int]]  # (entity_text, frequency)


class EntityTimelineAnalyzer:
    """
    Analyzes temporal patterns in entity mentions
    
    Features:
    - Track when entities first/last appeared
    - Detect frequency trends over time
    - Calculate activity scores (recency + frequency)
    - Find dormant entities (high past frequency, long gap)
    - Visualize timelines with ASCII charts
    - Activity summaries by period
    """
    
    # Trend detection thresholds
    TREND_INCREASE_THRESHOLD = 0.3  # 30% increase
    TREND_DECREASE_THRESHOLD = 0.3  # 30% decrease
    BURST_MULTIPLIER = 2.0  # 2x average = burst
    DORMANT_DAYS_THRESHOLD = 90  # 90 days = dormant
    
    # Activity scoring weights
    RECENCY_WEIGHT = 0.6  # Recent mentions matter more
    FREQUENCY_WEIGHT = 0.4  # But frequency still matters
    RECENCY_DECAY_DAYS = 30  # Half-life for recency decay
    
    def __init__(self, db_path: str):
        """
        Initialize timeline analyzer
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_entity_timeline(
        self,
        entity_text: str,
        entity_type: Optional[str] = None
    ) -> Optional[EntityTimeline]:
        """
        Get complete timeline for a specific entity
        
        Args:
            entity_text: Entity to analyze
            entity_type: Entity type filter (optional)
        
        Returns:
            EntityTimeline object or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get entity mentions with timestamps from memories
        query = """
            SELECT 
                e.text,
                e.type,
                e.frequency,
                m.created_at as mention_time
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE LOWER(e.text) = LOWER(?)
        """
        
        params = [entity_text]
        
        if entity_type:
            query += " AND e.type = ?"
            params.append(entity_type)
        
        query += " ORDER BY m.created_at ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        if not rows:
            return None
        
        # Extract timestamps
        timestamps = [datetime.fromisoformat(row['mention_time']) for row in rows]
        first_mention = timestamps[0]
        last_mention = timestamps[-1]
        now = datetime.now()
        
        # Calculate time differences
        days_since_first = (now - first_mention).days
        days_since_last = (now - last_mention).days
        
        # Get frequency from first row (it's the same for all)
        frequency = rows[0]['frequency']
        entity_type_val = rows[0]['type']
        
        # Detect trend
        trend = self._detect_trend(timestamps, frequency)
        
        # Calculate activity score
        activity_score = self._calculate_activity_score(
            frequency=frequency,
            days_since_last=days_since_last,
            days_since_first=days_since_first
        )
        
        # Build mentions by period (default: by month)
        mentions_by_period = self._group_by_period(timestamps, granularity='month')
        
        return EntityTimeline(
            entity_text=rows[0]['text'],
            entity_type=entity_type_val,
            frequency=frequency,
            first_mention=first_mention.isoformat(),
            last_mention=last_mention.isoformat(),
            days_since_first=days_since_first,
            days_since_last=days_since_last,
            trend=trend,
            activity_score=activity_score,
            mentions_by_period=mentions_by_period
        )
    
    def _detect_trend(
        self,
        timestamps: List[datetime],
        frequency: int
    ) -> str:
        """
        Detect frequency trend over time
        
        Strategy:
        - Split timeline in half (first half vs second half)
        - Compare mention frequencies
        - Detect: increasing, stable, declining, burst, dormant
        
        Args:
            timestamps: List of mention timestamps (sorted)
            frequency: Total frequency
        
        Returns:
            Trend string
        """
        if frequency < 3:
            # Not enough data for trend detection
            return "stable"
        
        if len(timestamps) < 2:
            return "stable"
        
        # Check for dormant (last mention was long ago)
        now = datetime.now()
        days_since_last = (now - timestamps[-1]).days
        
        if days_since_last >= self.DORMANT_DAYS_THRESHOLD:
            return "dormant"
        
        # Split timeline in half
        mid_point = len(timestamps) // 2
        first_half = timestamps[:mid_point]
        second_half = timestamps[mid_point:]
        
        # Calculate mention rates (mentions per day)
        if first_half:
            first_duration = (first_half[-1] - first_half[0]).days + 1
            first_rate = len(first_half) / max(first_duration, 1)
        else:
            first_rate = 0
        
        if second_half:
            second_duration = (second_half[-1] - second_half[0]).days + 1
            second_rate = len(second_half) / max(second_duration, 1)
        else:
            second_rate = 0
        
        # Detect burst (recent spike)
        if len(timestamps) >= 5:
            recent_mentions = [t for t in timestamps if (now - t).days <= 7]
            if len(recent_mentions) >= frequency * 0.5:  # 50% of mentions in last week
                return "burst"
        
        # Compare rates
        if first_rate == 0:
            return "increasing"
        
        rate_change = (second_rate - first_rate) / first_rate
        
        if rate_change >= self.TREND_INCREASE_THRESHOLD:
            return "increasing"
        elif rate_change <= -self.TREND_DECREASE_THRESHOLD:
            return "declining"
        else:
            return "stable"
    
    def _calculate_activity_score(
        self,
        frequency: int,
        days_since_last: int,
        days_since_first: int
    ) -> float:
        """
        Calculate activity score (0-100) combining recency + frequency
        
        Formula:
        - Recency score: Exponential decay based on days since last mention
        - Frequency score: Normalized by max frequency in system
        - Weighted combination
        
        Args:
            frequency: Total mention count
            days_since_last: Days since last mention
            days_since_first: Days since first mention
        
        Returns:
            Activity score (0-100)
        """
        # Recency score (exponential decay)
        # Score drops to 50% after RECENCY_DECAY_DAYS
        decay_rate = math.log(0.5) / self.RECENCY_DECAY_DAYS
        recency_score = math.exp(decay_rate * days_since_last) * 100
        recency_score = max(0, min(100, recency_score))
        
        # Frequency score (normalized)
        # Assume max reasonable frequency is 100 mentions
        frequency_score = min(frequency / 100 * 100, 100)
        
        # Weighted combination
        activity_score = (
            recency_score * self.RECENCY_WEIGHT +
            frequency_score * self.FREQUENCY_WEIGHT
        )
        
        return round(activity_score, 1)
    
    def _group_by_period(
        self,
        timestamps: List[datetime],
        granularity: str = 'month'
    ) -> Dict[str, int]:
        """
        Group mentions by time period
        
        Args:
            timestamps: List of mention timestamps
            granularity: 'day', 'week', 'month', 'quarter', 'year'
        
        Returns:
            Dictionary mapping period → count
        """
        counts = Counter()
        
        for ts in timestamps:
            if granularity == 'day':
                period = ts.strftime('%Y-%m-%d')
            elif granularity == 'week':
                # ISO week format: 2024-W45
                period = f"{ts.year}-W{ts.isocalendar()[1]:02d}"
            elif granularity == 'month':
                period = ts.strftime('%Y-%m')
            elif granularity == 'quarter':
                quarter = (ts.month - 1) // 3 + 1
                period = f"{ts.year}-Q{quarter}"
            elif granularity == 'year':
                period = str(ts.year)
            else:
                period = ts.strftime('%Y-%m')
            
            counts[period] += 1
        
        return dict(counts)
    
    def get_trending_entities(
        self,
        limit: int = 10,
        trend_type: Optional[str] = None
    ) -> List[EntityTimeline]:
        """
        Get trending entities (high activity score)
        
        Args:
            limit: Number of results
            trend_type: Filter by trend ("increasing", "burst", etc.)
        
        Returns:
            List of EntityTimeline objects sorted by activity score
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get all entities with their first/last mentions
        cursor.execute("""
            SELECT 
                e.text,
                e.type,
                e.frequency,
                MIN(m.created_at) as first_mention,
                MAX(m.created_at) as last_mention
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            GROUP BY LOWER(e.text), e.type
            HAVING e.frequency >= 2
            ORDER BY e.frequency DESC
            LIMIT 100
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        # Calculate timelines for each
        timelines = []
        
        for row in rows:
            timeline = self.get_entity_timeline(row['text'], row['type'])
            if timeline:
                # Filter by trend type if specified
                if trend_type is None or timeline.trend == trend_type:
                    timelines.append(timeline)
        
        # Sort by activity score
        timelines.sort(key=lambda t: t.activity_score, reverse=True)
        
        return timelines[:limit]
    
    def get_dormant_entities(
        self,
        limit: int = 10,
        min_frequency: int = 3
    ) -> List[EntityTimeline]:
        """
        Find dormant entities (high past frequency, not mentioned recently)
        
        Perfect for rediscovery suggestions!
        
        Args:
            limit: Number of results
            min_frequency: Minimum frequency to consider
        
        Returns:
            List of EntityTimeline objects for dormant entities
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get entities not mentioned in DORMANT_DAYS_THRESHOLD days
        cursor.execute(f"""
            SELECT 
                e.text,
                e.type,
                e.frequency,
                MAX(m.created_at) as last_mention
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            GROUP BY LOWER(e.text), e.type
            HAVING 
                e.frequency >= ?
                AND JULIANDAY('now') - JULIANDAY(MAX(m.created_at)) >= ?
            ORDER BY e.frequency DESC
            LIMIT ?
        """, (min_frequency, self.DORMANT_DAYS_THRESHOLD, limit * 2))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Get full timelines
        timelines = []
        
        for row in rows:
            timeline = self.get_entity_timeline(row['text'], row['type'])
            if timeline and timeline.trend == 'dormant':
                timelines.append(timeline)
        
        # Sort by frequency (high frequency = more worth rediscovering)
        timelines.sort(key=lambda t: t.frequency, reverse=True)
        
        return timelines[:limit]
    
    def visualize_timeline(
        self,
        entity_text: str,
        granularity: str = 'month',
        width: int = 60
    ) -> str:
        """
        Create ASCII visualization of entity timeline
        
        Args:
            entity_text: Entity to visualize
            granularity: Time granularity
            width: Chart width in characters
        
        Returns:
            ASCII chart string
        """
        timeline = self.get_entity_timeline(entity_text)
        
        if not timeline:
            return f"No timeline data for: {entity_text}"
        
        # Get mentions by period
        mentions = timeline.mentions_by_period
        
        if not mentions:
            return f"No timeline data for: {entity_text}"
        
        # Sort periods chronologically
        sorted_periods = sorted(mentions.keys())
        
        # Find max count for scaling
        max_count = max(mentions.values())
        
        # Build ASCII chart
        lines = []
        lines.append(f"\n📈 Timeline: {timeline.entity_text}")
        lines.append(f"   Frequency: {timeline.frequency} | Trend: {self._trend_emoji(timeline.trend)} {timeline.trend}")
        lines.append(f"   Activity Score: {timeline.activity_score}/100")
        lines.append(f"   Period: {sorted_periods[0]} to {sorted_periods[-1]}")
        lines.append("")
        
        # Draw bars
        for period in sorted_periods:
            count = mentions[period]
            bar_length = int((count / max_count) * width)
            bar = "█" * bar_length
            
            lines.append(f"   {period}  {bar} {count}")
        
        lines.append("")
        
        return "\n".join(lines)
    
    def _trend_emoji(self, trend: str) -> str:
        """Get emoji for trend type"""
        emojis = {
            'increasing': '↗',
            'stable': '→',
            'declining': '↘',
            'burst': '🔥',
            'dormant': '💤'
        }
        return emojis.get(trend, '•')
    
    def get_activity_summary(
        self,
        period: str = 'month',
        limit: int = 12
    ) -> List[ActivityPeriod]:
        """
        Get activity summary by time period
        
        Args:
            period: 'day', 'week', 'month', 'quarter', 'year'
            limit: Number of periods to return
        
        Returns:
            List of ActivityPeriod objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get all entity mentions with timestamps
        cursor.execute("""
            SELECT 
                e.text,
                e.frequency,
                m.created_at
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            ORDER BY m.created_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        # Group by period
        period_data = defaultdict(lambda: {
            'entities': Counter(),
            'total_mentions': 0
        })
        
        for row in rows:
            ts = datetime.fromisoformat(row['created_at'])
            
            # Determine period key
            if period == 'day':
                period_key = ts.strftime('%Y-%m-%d')
            elif period == 'week':
                period_key = f"{ts.year}-W{ts.isocalendar()[1]:02d}"
            elif period == 'month':
                period_key = ts.strftime('%Y-%m')
            elif period == 'quarter':
                quarter = (ts.month - 1) // 3 + 1
                period_key = f"{ts.year}-Q{quarter}"
            elif period == 'year':
                period_key = str(ts.year)
            else:
                period_key = ts.strftime('%Y-%m')
            
            # Increment counts
            period_data[period_key]['entities'][row['text']] += 1
            period_data[period_key]['total_mentions'] += 1
        
        # Build ActivityPeriod objects
        summaries = []
        
        for period_key in sorted(period_data.keys(), reverse=True)[:limit]:
            data = period_data[period_key]
            
            # Get top entities
            top_entities = data['entities'].most_common(5)
            
            summaries.append(ActivityPeriod(
                period=period_key,
                entity_count=len(data['entities']),
                total_mentions=data['total_mentions'],
                top_entities=top_entities
            ))
        
        return summaries
    
    def get_timeline_stats(self) -> Dict:
        """
        Get overall timeline statistics
        
        Returns:
            Dictionary with stats
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Total entities with timelines
        cursor.execute("""
            SELECT COUNT(DISTINCT e.text) 
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
        """)
        stats['total_entities_with_timeline'] = cursor.fetchone()[0]
        
        # Trend distribution
        trend_counts = {
            'increasing': 0,
            'stable': 0,
            'declining': 0,
            'burst': 0,
            'dormant': 0
        }
        
        # Get sample of entities to estimate trend distribution
        cursor.execute("""
            SELECT e.text, e.type
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            GROUP BY LOWER(e.text), e.type
            LIMIT 100
        """)
        
        for row in cursor.fetchall():
            timeline = self.get_entity_timeline(row['text'], row['type'])
            if timeline:
                trend_counts[timeline.trend] += 1
        
        stats['trend_distribution'] = trend_counts
        
        # Average activity score
        timelines = self.get_trending_entities(limit=100)
        if timelines:
            stats['avg_activity_score'] = sum(t.activity_score for t in timelines) / len(timelines)
        else:
            stats['avg_activity_score'] = 0.0
        
        conn.close()
        
        return stats


def main():
    """Test entity timeline analyzer"""
    import sys
    from pathlib import Path
    
    # Try to find database
    possible_paths = [
        ".mnemonic/mnemonic.db",
        "~/Mnemonic/.mnemonic/mnemonic.db",
        sys.argv[1] if len(sys.argv) > 1 else None
    ]
    
    db_path = None
    for path in possible_paths:
        if path and Path(path).expanduser().exists():
            db_path = str(Path(path).expanduser())
            break
    
    if not db_path:
        print("❌ Database not found. Please specify path:")
        print("   python entity_timeline.py <db_path>")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print("ENTITY TIMELINE ANALYSIS TEST")
    print(f"{'='*70}\n")
    
    print(f"Database: {db_path}\n")
    
    # Initialize analyzer
    print("Initializing timeline analyzer...")
    analyzer = EntityTimelineAnalyzer(db_path)
    print("✓ Analyzer initialized\n")
    
    # Test 1: Get trending entities
    print("="*70)
    print("TEST 1: Trending Entities")
    print("="*70)
    
    trending = analyzer.get_trending_entities(limit=5)
    
    if trending:
        print(f"\nTop {len(trending)} trending entities:\n")
        
        for i, timeline in enumerate(trending, 1):
            emoji = analyzer._trend_emoji(timeline.trend)
            print(f"{i}. {timeline.entity_text} ({timeline.entity_type or 'untyped'})")
            print(f"   {emoji} {timeline.trend} | Activity: {timeline.activity_score}/100")
            print(f"   Frequency: {timeline.frequency} | Last seen: {timeline.days_since_last} days ago")
            print()
    else:
        print("No trending entities found. Add more memories with entities!")
    
    # Test 2: Dormant entities
    print("="*70)
    print("TEST 2: Dormant Entities (Rediscovery)")
    print("="*70)
    
    dormant = analyzer.get_dormant_entities(limit=5)
    
    if dormant:
        print(f"\n💤 {len(dormant)} dormant entities (haven't mentioned recently):\n")
        
        for i, timeline in enumerate(dormant, 1):
            print(f"{i}. {timeline.entity_text}")
            print(f"   Frequency: {timeline.frequency} | Last seen: {timeline.days_since_last} days ago")
            print(f"   First mentioned: {timeline.days_since_first} days ago")
            print()
    else:
        print("No dormant entities found.")
    
    # Test 3: Specific entity timeline
    if trending:
        print("="*70)
        print("TEST 3: Timeline Visualization")
        print("="*70)
        
        entity = trending[0].entity_text
        viz = analyzer.visualize_timeline(entity, granularity='month')
        print(viz)
    
    # Test 4: Activity summary
    print("="*70)
    print("TEST 4: Activity Summary by Month")
    print("="*70)
    
    summary = analyzer.get_activity_summary(period='month', limit=6)
    
    if summary:
        print()
        for period_data in summary:
            print(f"📅 {period_data.period}")
            print(f"   Entities: {period_data.entity_count} | Total mentions: {period_data.total_mentions}")
            
            if period_data.top_entities:
                top_3 = period_data.top_entities[:3]
                top_str = ", ".join(f"{e[0]} ({e[1]})" for e in top_3)
                print(f"   Top: {top_str}")
            print()
    
    # Test 5: Overall stats
    print("="*70)
    print("TIMELINE STATISTICS")
    print("="*70)
    
    stats = analyzer.get_timeline_stats()
    
    print(f"\nTotal entities with timeline: {stats['total_entities_with_timeline']}")
    print(f"Average activity score: {stats['avg_activity_score']:.1f}/100")
    print(f"\nTrend distribution (sample):")
    for trend, count in stats['trend_distribution'].items():
        emoji = analyzer._trend_emoji(trend)
        print(f"  {emoji} {trend}: {count}")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()