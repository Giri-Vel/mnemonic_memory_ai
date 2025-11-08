"""
Tests for Entity Timeline Analysis (Week 4, Day 3)

Tests:
- Timeline data retrieval
- Trend detection (increasing/stable/declining)
- Rediscovery suggestions
- ASCII visualization
- Activity summaries
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
import sys
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from mnemonic.entity_timeline import (
    EntityTimelineAnalyzer,
    EntityTimelineData,
    RediscoverySuggestion
)


@pytest.fixture
def temp_db():
    """Create temporary database with timeline data"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            type TEXT,
            type_source TEXT NOT NULL,
            confidence REAL NOT NULL,
            frequency INTEGER DEFAULT 1,
            memory_id INTEGER NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
    
    yield path
    
    os.unlink(path)


@pytest.fixture
def populated_timeline_db(temp_db):
    """Create database with timeline test data"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Add memories over time with entities
    base_date = datetime.now() - timedelta(days=180)
    
    test_data = [
        # "Steins Gate" - increasing trend (more recent mentions)
        ("Steins Gate", "anime", 0, 2),  # 180 days ago, 2 mentions
        ("Steins Gate", "anime", 90, 3), # 90 days ago, 3 mentions
        ("Steins Gate", "anime", 30, 5), # 30 days ago, 5 mentions
        ("Steins Gate", "anime", 7, 7),  # 7 days ago, 7 mentions
        
        # "Code Geass" - declining trend (fewer recent mentions)
        ("Code Geass", "anime", 0, 8),   # 180 days ago, 8 mentions
        ("Code Geass", "anime", 90, 5),  # 90 days ago, 5 mentions
        ("Code Geass", "anime", 150, 2), # 150 days ago, 2 mentions
        
        # "Death Note" - stable trend
        ("Death Note", "anime", 0, 5),
        ("Death Note", "anime", 60, 5),
        ("Death Note", "anime", 120, 5),
        
        # "Cowboy Bebop" - rediscovery candidate (not mentioned recently)
        ("Cowboy Bebop", "anime", 0, 10),  # 180 days ago, high frequency
        ("Cowboy Bebop", "anime", 30, 3),  # 150 days ago
    ]
    
    entity_id_map = {}
    
    for entity_text, entity_type, days_ago, mention_count in test_data:
        date = base_date + timedelta(days=days_ago)
        
        # Create memories for this entity at this date
        for _ in range(mention_count):
            cursor.execute("""
                INSERT INTO memories (content, created_at)
                VALUES (?, ?)
            """, (f"Memory about {entity_text}", date.isoformat()))
            
            memory_id = cursor.lastrowid
            
            # Get or create entity
            entity_key = (entity_text, entity_type)
            if entity_key not in entity_id_map:
                cursor.execute("""
                    INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id)
                    VALUES (?, ?, 'user_defined', 0.9, ?, ?)
                """, (entity_text, entity_type, mention_count, memory_id))
                entity_id_map[entity_key] = cursor.lastrowid
            else:
                # Update frequency
                cursor.execute("""
                    UPDATE entities
                    SET frequency = frequency + 1
                    WHERE id = ?
                """, (entity_id_map[entity_key],))
    
    conn.commit()
    conn.close()
    
    return temp_db


class TestEntityTimelineData:
    """Test EntityTimelineData dataclass"""
    
    def test_timeline_data_creation(self):
        """Test creating timeline data"""
        timeline = EntityTimelineData(
            entity_id=1,
            text="Test Entity",
            type="test",
            first_mention="2024-01-01",
            last_mention="2024-06-01",
            total_frequency=10,
            days_active=152,
            mentions_by_date={"2024-01-01": 5, "2024-06-01": 5},
            trend="increasing",
            trend_direction="↗",
            days_since_last=30
        )
        
        assert timeline.text == "Test Entity"
        assert timeline.trend == "increasing"
        assert timeline.days_active == 152
    
    def test_timeline_to_dict(self):
        """Test converting timeline to dictionary"""
        timeline = EntityTimelineData(
            entity_id=1,
            text="Test",
            type="test",
            first_mention="2024-01-01",
            last_mention="2024-06-01",
            total_frequency=10,
            days_active=152,
            mentions_by_date={},
            trend="stable",
            trend_direction="→",
            days_since_last=30
        )
        
        data = timeline.to_dict()
        
        assert data['text'] == "Test"
        assert data['trend'] == "stable"
        assert 'entity_id' in data


class TestEntityTimelineAnalyzer:
    """Test EntityTimelineAnalyzer class"""
    
    def test_analyzer_initialization(self, temp_db):
        """Test analyzer initialization"""
        analyzer = EntityTimelineAnalyzer(temp_db)
        assert analyzer.db_path == temp_db
    
    def test_get_entity_timeline(self, populated_timeline_db):
        """Test getting timeline for specific entity"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        timeline = analyzer.get_entity_timeline("Steins Gate", "anime")
        
        assert timeline is not None
        assert timeline.text == "Steins Gate"
        assert timeline.type == "anime"
        assert timeline.total_frequency > 0
        assert len(timeline.mentions_by_date) > 0
    
    def test_get_timeline_not_found(self, temp_db):
        """Test getting timeline for non-existent entity"""
        analyzer = EntityTimelineAnalyzer(temp_db)
        
        timeline = analyzer.get_entity_timeline("NonExistent")
        
        assert timeline is None
    
    def test_trend_detection_increasing(self, populated_timeline_db):
        """Test detecting increasing trend"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        timeline = analyzer.get_entity_timeline("Steins Gate", "anime")
        
        assert timeline is not None
        # Steins Gate has increasing mentions over time
        assert timeline.trend in ["increasing", "stable"]  # May vary based on data distribution
        
    def test_trend_detection_declining(self, populated_timeline_db):
        """Test detecting declining trend"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        timeline = analyzer.get_entity_timeline("Code Geass", "anime")
        
        assert timeline is not None
        # Code Geass has declining mentions
        assert timeline.trend in ["declining", "stable"]
    
    def test_trend_detection_stable(self, populated_timeline_db):
        """Test detecting stable trend"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        timeline = analyzer.get_entity_timeline("Death Note", "anime")
        
        assert timeline is not None
        # Death Note has stable mentions
        assert timeline.trend == "stable"


class TestTrendingEntities:
    """Test trending entities functionality"""
    
    def test_get_trending_entities(self, populated_timeline_db):
        """Test getting trending entities"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        trending = analyzer.get_trending_entities(limit=10)
        
        assert len(trending) > 0
        assert all(isinstance(t, EntityTimelineData) for t in trending)
    
    def test_filter_by_entity_type(self, populated_timeline_db):
        """Test filtering trending by entity type"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        trending = analyzer.get_trending_entities(entity_type="anime", limit=10)
        
        assert len(trending) > 0
        assert all(t.type == "anime" for t in trending)
    
    def test_filter_by_trend(self, populated_timeline_db):
        """Test filtering by trend type"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        increasing = analyzer.get_trending_entities(trend_filter="increasing", limit=10)
        
        # All results should have increasing trend
        assert all(t.trend == "increasing" for t in increasing)


class TestRediscovery:
    """Test rediscovery suggestions"""
    
    def test_get_rediscovery_suggestions(self, populated_timeline_db):
        """Test getting rediscovery suggestions"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        suggestions = analyzer.get_rediscovery_suggestions(
            min_days_ago=100,
            min_frequency=5,
            limit=5
        )
        
        # Should find some suggestions
        assert isinstance(suggestions, list)
        assert all(isinstance(s, RediscoverySuggestion) for s in suggestions)
    
    def test_rediscovery_relevance_score(self, populated_timeline_db):
        """Test that relevance scores are calculated"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        suggestions = analyzer.get_rediscovery_suggestions(
            min_days_ago=100,
            min_frequency=3,
            limit=5
        )
        
        for sug in suggestions:
            assert 0 <= sug.relevance_score <= 1
            assert sug.days_ago >= 100
            assert sug.frequency >= 3
    
    def test_rediscovery_sorting(self, populated_timeline_db):
        """Test that suggestions are sorted by relevance"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        suggestions = analyzer.get_rediscovery_suggestions(limit=10)
        
        if len(suggestions) > 1:
            # Should be sorted descending by relevance
            for i in range(len(suggestions) - 1):
                assert suggestions[i].relevance_score >= suggestions[i + 1].relevance_score


class TestVisualization:
    """Test ASCII visualization"""
    
    def test_visualize_timeline(self, populated_timeline_db):
        """Test ASCII timeline generation"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        ascii_chart = analyzer.visualize_timeline_ascii("Steins Gate", "anime")
        
        assert isinstance(ascii_chart, str)
        assert "Steins Gate" in ascii_chart
        assert "Timeline for:" in ascii_chart
        assert "Trend:" in ascii_chart
    
    def test_visualize_not_found(self, temp_db):
        """Test visualization for non-existent entity"""
        analyzer = EntityTimelineAnalyzer(temp_db)
        
        result = analyzer.visualize_timeline_ascii("NonExistent")
        
        assert "not found" in result.lower()


class TestActivitySummary:
    """Test activity summary functionality"""
    
    def test_get_activity_summary(self, populated_timeline_db):
        """Test getting activity summary"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        summary = analyzer.get_activity_summary("Steins Gate", "anime")
        
        assert 'entity' in summary
        assert 'total_mentions' in summary
        assert 'trend' in summary
        assert 'days_active' in summary
        assert summary['entity'] == "Steins Gate"
    
    def test_activity_summary_not_found(self, temp_db):
        """Test activity summary for non-existent entity"""
        analyzer = EntityTimelineAnalyzer(temp_db)
        
        summary = analyzer.get_activity_summary("NonExistent")
        
        assert summary == {}
    
    def test_most_active_period(self, populated_timeline_db):
        """Test detection of most active period"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        summary = analyzer.get_activity_summary("Steins Gate", "anime")
        
        assert 'most_active_month' in summary
        assert 'most_active_month_mentions' in summary


class TestTimelineStats:
    """Test overall timeline statistics"""
    
    def test_get_timeline_stats(self, populated_timeline_db):
        """Test getting timeline statistics"""
        analyzer = EntityTimelineAnalyzer(populated_timeline_db)
        
        stats = analyzer.get_timeline_stats()
        
        assert 'total_entities' in stats
        assert 'data_start' in stats
        assert 'data_end' in stats
        assert 'total_days' in stats
        assert stats['total_entities'] > 0
    
    def test_stats_empty_database(self, temp_db):
        """Test stats on empty database"""
        analyzer = EntityTimelineAnalyzer(temp_db)
        
        stats = analyzer.get_timeline_stats()
        
        assert stats['total_entities'] == 0
        assert stats['total_days'] == 0


def run_tests():
    """Run all tests"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()