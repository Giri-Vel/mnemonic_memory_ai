"""
Tests for Entity Timeline Analysis System

Tests:
- Timeline creation and tracking
- Trend detection algorithms
- Activity scoring
- Dormant entity detection
- Timeline visualization
- Activity summaries
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from mnemonic.entity_timeline import (
    EntityTimelineAnalyzer,
    EntityTimeline,
    ActivityPeriod
)


@pytest.fixture
def test_db():
    """Create temporary test database with sample data"""
    # Create temp database
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY,
            content TEXT NOT NULL,
            uuid TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            text TEXT NOT NULL,
            type TEXT,
            type_source TEXT,
            confidence REAL,
            frequency INTEGER DEFAULT 1,
            memory_id INTEGER,
            cluster_id INTEGER,
            metadata TEXT,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (memory_id) REFERENCES memories(id)
        )
    """)
    
    # Insert test data
    # Entity 1: "Python" - increasing trend (3 months, getting more frequent)
    base_date = datetime.now()
    
    # Month 1: 2 mentions
    for i in range(2):
        date = base_date - timedelta(days=90 - i)
        cursor.execute(
            "INSERT INTO memories (content, created_at) VALUES (?, ?)",
            (f"Learning Python basics {i}", date.isoformat())
        )
        memory_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("Python", "technology", "user_defined", 0.9, 5, memory_id)
        )
    
    # Month 2: 3 mentions
    for i in range(3):
        date = base_date - timedelta(days=60 - i)
        cursor.execute(
            "INSERT INTO memories (content, created_at) VALUES (?, ?)",
            (f"Python advanced topics {i}", date.isoformat())
        )
        memory_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("Python", "technology", "user_defined", 0.9, 5, memory_id)
        )
    
    # Month 3: 5 mentions (recent - increasing trend)
    for i in range(5):
        date = base_date - timedelta(days=10 - i)
        cursor.execute(
            "INSERT INTO memories (content, created_at) VALUES (?, ?)",
            (f"Python project work {i}", date.isoformat())
        )
        memory_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("Python", "technology", "user_defined", 0.9, 10, memory_id)
        )
    
    # Entity 2: "JavaScript" - dormant (mentioned 95 days ago, freq=5)
    for i in range(5):
        date = base_date - timedelta(days=95 + i)
        cursor.execute(
            "INSERT INTO memories (content, created_at) VALUES (?, ?)",
            (f"JavaScript tutorial {i}", date.isoformat())
        )
        memory_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("JavaScript", "technology", "user_defined", 0.9, 5, memory_id)
        )
    
    # Entity 3: "React" - burst (5 mentions in last 3 days)
    for i in range(5):
        date = base_date - timedelta(days=2 - (i * 0.5))
        cursor.execute(
            "INSERT INTO memories (content, created_at) VALUES (?, ?)",
            (f"React learning {i}", date.isoformat())
        )
        memory_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("React", "technology", "user_defined", 0.9, 5, memory_id)
        )
    
    # Entity 4: "Go" - stable (consistent mentions)
    for i in range(6):
        date = base_date - timedelta(days=60 - (i * 10))
        cursor.execute(
            "INSERT INTO memories (content, created_at) VALUES (?, ?)",
            (f"Go programming {i}", date.isoformat())
        )
        memory_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("Go", "technology", "user_defined", 0.9, 6, memory_id)
        )
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    os.unlink(db_path)


class TestEntityTimelineAnalyzer:
    """Test suite for EntityTimelineAnalyzer"""
    
    def test_initialization(self, test_db):
        """Test analyzer initialization"""
        analyzer = EntityTimelineAnalyzer(test_db)
        assert analyzer.db_path == test_db
    
    def test_get_entity_timeline(self, test_db):
        """Test getting timeline for specific entity"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        # Get Python timeline
        timeline = analyzer.get_entity_timeline("Python")
        
        assert timeline is not None
        assert timeline.entity_text == "Python"
        assert timeline.entity_type == "technology"
        assert timeline.frequency >= 5  # At least 5 mentions
        assert timeline.first_mention is not None
        assert timeline.last_mention is not None
        assert timeline.days_since_last < 15  # Recent mention
        assert 0 <= timeline.activity_score <= 100
    
    def test_trend_detection_increasing(self, test_db):
        """Test detection of increasing trend"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        timeline = analyzer.get_entity_timeline("Python")
        
        # Python should show increasing trend (2 → 3 → 5 mentions)
        assert timeline.trend == "increasing"
    
    def test_trend_detection_dormant(self, test_db):
        """Test detection of dormant entities"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        timeline = analyzer.get_entity_timeline("JavaScript")
        
        # JavaScript should be dormant (95+ days)
        assert timeline.trend == "dormant"
        assert timeline.days_since_last >= 90
    
    def test_trend_detection_burst(self, test_db):
        """Test detection of burst activity"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        timeline = analyzer.get_entity_timeline("React")
        
        # React should show burst (5 mentions in 3 days)
        assert timeline.trend == "burst"
    
    def test_trend_detection_stable(self, test_db):
        """Test detection of stable trend"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        timeline = analyzer.get_entity_timeline("Go")
        
        # Go should be stable (consistent mentions)
        assert timeline.trend == "stable"
    
    def test_activity_score_calculation(self, test_db):
        """Test activity score calculation"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        # Recent, frequent entity should have high score
        python_timeline = analyzer.get_entity_timeline("Python")
        assert python_timeline.activity_score > 50
        
        # Dormant entity should have low score
        js_timeline = analyzer.get_entity_timeline("JavaScript")
        assert js_timeline.activity_score < 30
    
    def test_activity_score_recency_weight(self, test_db):
        """Test that recency is weighted properly in activity score"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        # React (recent burst) should score higher than JavaScript (dormant)
        react_timeline = analyzer.get_entity_timeline("React")
        js_timeline = analyzer.get_entity_timeline("JavaScript")
        
        assert react_timeline.activity_score > js_timeline.activity_score
    
    def test_mentions_by_period(self, test_db):
        """Test grouping mentions by time period"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        timeline = analyzer.get_entity_timeline("Python")
        
        # Should have mentions grouped by month
        assert len(timeline.mentions_by_period) > 0
        
        # Each period should have counts
        for period, count in timeline.mentions_by_period.items():
            assert isinstance(period, str)
            assert count > 0
    
    def test_get_trending_entities(self, test_db):
        """Test getting trending entities"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        trending = analyzer.get_trending_entities(limit=3)
        
        assert len(trending) <= 3
        assert all(isinstance(t, EntityTimeline) for t in trending)
        
        # Should be sorted by activity score
        if len(trending) > 1:
            for i in range(len(trending) - 1):
                assert trending[i].activity_score >= trending[i+1].activity_score
    
    def test_get_trending_entities_filter(self, test_db):
        """Test filtering trending entities by trend type"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        # Get only burst entities
        burst_entities = analyzer.get_trending_entities(limit=10, trend_type="burst")
        
        assert all(t.trend == "burst" for t in burst_entities)
    
    def test_get_dormant_entities(self, test_db):
        """Test getting dormant entities"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        dormant = analyzer.get_dormant_entities(limit=5, min_frequency=3)
        
        # JavaScript should be in dormant list
        dormant_texts = [t.entity_text for t in dormant]
        assert "JavaScript" in dormant_texts
        
        # All should be dormant
        assert all(t.trend == "dormant" for t in dormant)
        assert all(t.days_since_last >= 90 for t in dormant)
    
    def test_visualize_timeline(self, test_db):
        """Test ASCII timeline visualization"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        viz = analyzer.visualize_timeline("Python", granularity='month')
        
        # Should be a non-empty string
        assert isinstance(viz, str)
        assert len(viz) > 0
        
        # Should contain entity name and trend info
        assert "Python" in viz
        assert "Trend:" in viz
        assert "Activity Score:" in viz
    
    def test_visualize_timeline_not_found(self, test_db):
        """Test visualization for non-existent entity"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        viz = analyzer.visualize_timeline("NonExistent")
        
        assert "No timeline data" in viz
    
    def test_get_activity_summary(self, test_db):
        """Test activity summary by period"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        summary = analyzer.get_activity_summary(period='month', limit=3)
        
        assert len(summary) <= 3
        assert all(isinstance(p, ActivityPeriod) for p in summary)
        
        # Each period should have data
        for period_data in summary:
            assert period_data.entity_count > 0
            assert period_data.total_mentions > 0
            assert len(period_data.top_entities) > 0
    
    def test_get_activity_summary_granularities(self, test_db):
        """Test different time granularities"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        granularities = ['day', 'week', 'month', 'quarter', 'year']
        
        for granularity in granularities:
            summary = analyzer.get_activity_summary(period=granularity, limit=5)
            
            # Should return results for each granularity
            assert len(summary) > 0
            
            # Period format should match granularity
            period_format = summary[0].period
            if granularity == 'week':
                assert '-W' in period_format
            elif granularity == 'quarter':
                assert '-Q' in period_format
    
    def test_get_timeline_stats(self, test_db):
        """Test overall timeline statistics"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        stats = analyzer.get_timeline_stats()
        
        assert 'total_entities_with_timeline' in stats
        assert 'trend_distribution' in stats
        assert 'avg_activity_score' in stats
        
        # Should have counted entities
        assert stats['total_entities_with_timeline'] > 0
        
        # Should have trend distribution
        trend_dist = stats['trend_distribution']
        assert isinstance(trend_dist, dict)
        assert all(k in trend_dist for k in ['increasing', 'stable', 'declining', 'burst', 'dormant'])
    
    def test_trend_emoji(self, test_db):
        """Test trend emoji mapping"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        assert analyzer._trend_emoji('increasing') == '↗'
        assert analyzer._trend_emoji('stable') == '→'
        assert analyzer._trend_emoji('declining') == '↘'
        assert analyzer._trend_emoji('burst') == '🔥'
        assert analyzer._trend_emoji('dormant') == '💤'
    
    def test_entity_not_found(self, test_db):
        """Test handling of non-existent entity"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        timeline = analyzer.get_entity_timeline("NonExistentEntity")
        
        assert timeline is None
    
    def test_timeline_with_type_filter(self, test_db):
        """Test timeline retrieval with entity type filter"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        # Get Python with type filter
        timeline = analyzer.get_entity_timeline("Python", entity_type="technology")
        
        assert timeline is not None
        assert timeline.entity_type == "technology"
        
        # Wrong type should return None
        timeline_wrong = analyzer.get_entity_timeline("Python", entity_type="wrong_type")
        assert timeline_wrong is None


class TestTimelinePeriodGrouping:
    """Test period grouping functionality"""
    
    def test_group_by_day(self, test_db):
        """Test grouping by day"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        timeline = analyzer.get_entity_timeline("Python")
        
        # Create timeline with day granularity
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.created_at 
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE LOWER(e.text) = LOWER('Python')
        """)
        
        timestamps = [datetime.fromisoformat(row[0]) for row in cursor.fetchall()]
        conn.close()
        
        daily_counts = analyzer._group_by_period(timestamps, 'day')
        
        # Should have daily breakdown
        assert len(daily_counts) > 0
        
        # Keys should be in YYYY-MM-DD format
        for period in daily_counts.keys():
            assert len(period.split('-')) == 3
    
    def test_group_by_week(self, test_db):
        """Test grouping by week"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        timeline = analyzer.get_entity_timeline("Python")
        
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.created_at 
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE LOWER(e.text) = LOWER('Python')
        """)
        
        timestamps = [datetime.fromisoformat(row[0]) for row in cursor.fetchall()]
        conn.close()
        
        weekly_counts = analyzer._group_by_period(timestamps, 'week')
        
        # Keys should be in YYYY-WXX format
        for period in weekly_counts.keys():
            assert '-W' in period
    
    def test_group_by_quarter(self, test_db):
        """Test grouping by quarter"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        timeline = analyzer.get_entity_timeline("Python")
        
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.created_at 
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE LOWER(e.text) = LOWER('Python')
        """)
        
        timestamps = [datetime.fromisoformat(row[0]) for row in cursor.fetchall()]
        conn.close()
        
        quarterly_counts = analyzer._group_by_period(timestamps, 'quarter')
        
        # Keys should be in YYYY-QX format
        for period in quarterly_counts.keys():
            assert '-Q' in period


class TestActivityScoring:
    """Test activity scoring algorithms"""
    
    def test_recency_decay(self, test_db):
        """Test that recency decays over time"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        # Same frequency, different recency
        recent_score = analyzer._calculate_activity_score(
            frequency=5,
            days_since_last=1,
            days_since_first=30
        )
        
        old_score = analyzer._calculate_activity_score(
            frequency=5,
            days_since_last=60,
            days_since_first=90
        )
        
        # Recent should score higher
        assert recent_score > old_score
    
    def test_frequency_matters(self, test_db):
        """Test that frequency affects score"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        # Same recency, different frequency
        high_freq_score = analyzer._calculate_activity_score(
            frequency=20,
            days_since_last=5,
            days_since_first=30
        )
        
        low_freq_score = analyzer._calculate_activity_score(
            frequency=3,
            days_since_last=5,
            days_since_first=30
        )
        
        # Higher frequency should score higher
        assert high_freq_score > low_freq_score
    
    def test_score_bounds(self, test_db):
        """Test that scores stay within 0-100 range"""
        analyzer = EntityTimelineAnalyzer(test_db)
        
        # Extreme values
        scores = [
            analyzer._calculate_activity_score(100, 0, 1),  # Max
            analyzer._calculate_activity_score(1, 365, 365),  # Min
            analyzer._calculate_activity_score(50, 30, 60),  # Mid
        ]
        
        for score in scores:
            assert 0 <= score <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])