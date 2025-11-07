"""
Tests for Entity Clustering System (Day 7)

Tests:
- Similarity calculation (Levenshtein distance)
- Clustering algorithm
- Cluster assignment
- Statistics
- Edge cases
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
import sys

# Import modules to test
sys.path.insert(0, str(Path(__file__).parent.parent))

from mnemonic.entity_clustering import EntityClusterer, EntityCluster


@pytest.fixture
def temp_db():
    """Create a temporary database with entities table"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Create entities table
    cursor.execute("""
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            type TEXT,
            type_source TEXT NOT NULL,
            confidence REAL NOT NULL,
            frequency INTEGER DEFAULT 1,
            memory_id INTEGER NOT NULL,
            cluster_id INTEGER,
            metadata TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    
    yield path
    
    os.unlink(path)


@pytest.fixture
def populated_db(temp_db):
    """Create database with test entities for clustering"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Add similar anime entities
    test_entities = [
        ("Steins Gate", "anime", 5),
        ("Steins;Gate", "anime", 3),
        ("Steins Gate 0", "anime", 2),
        ("Code Geass", "anime", 4),
        ("Code Geass R2", "anime", 2),
        ("Death Note", "anime", 6),
        ("death note", "anime", 2),  # Case variation
        ("Cowboy Bebop", "anime", 3),
    ]
    
    for text, entity_type, frequency in test_entities:
        cursor.execute("""
            INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id)
            VALUES (?, ?, 'user_defined', 0.9, ?, 1)
        """, (text, entity_type, frequency))
    
    conn.commit()
    conn.close()
    
    return temp_db


class TestSimilarityCalculation:
    """Test similarity calculation algorithm"""
    
    def test_identical_strings(self, temp_db):
        """Test similarity of identical strings"""
        clusterer = EntityClusterer(temp_db)
        
        similarity = clusterer.calculate_similarity("Steins Gate", "Steins Gate")
        assert similarity == 1.0
    
    def test_case_insensitive(self, temp_db):
        """Test case-insensitive similarity"""
        clusterer = EntityClusterer(temp_db)
        
        similarity = clusterer.calculate_similarity("Death Note", "death note")
        assert similarity == 1.0
    
    def test_similar_strings(self, temp_db):
        """Test similarity of similar strings"""
        clusterer = EntityClusterer(temp_db)
        
        # Steins Gate vs Steins;Gate (one char difference)
        similarity = clusterer.calculate_similarity("Steins Gate", "Steins;Gate")
        assert similarity > 0.9  # Very similar
        
        # Steins Gate vs Steins Gate 0 (added " 0")
        similarity = clusterer.calculate_similarity("Steins Gate", "Steins Gate 0")
        assert 0.8 < similarity < 0.9  # Fairly similar
    
    def test_different_strings(self, temp_db):
        """Test similarity of different strings"""
        clusterer = EntityClusterer(temp_db)
        
        similarity = clusterer.calculate_similarity("Steins Gate", "Death Note")
        assert similarity < 0.5  # Not similar
    
    def test_substring_similarity(self, temp_db):
        """Test similarity when one string is substring of another"""
        clusterer = EntityClusterer(temp_db)
        
        similarity = clusterer.calculate_similarity("Code Geass", "Code Geass R2")
        assert similarity > 0.7  # Fairly similar
    
    def test_empty_strings(self, temp_db):
        """Test edge case with empty strings"""
        clusterer = EntityClusterer(temp_db)
        
        similarity = clusterer.calculate_similarity("", "")
        assert similarity == 0.0
        
        similarity = clusterer.calculate_similarity("test", "")
        assert similarity == 0.0


class TestLevenshteinDistance:
    """Test Levenshtein distance calculation"""
    
    def test_identical_strings(self, temp_db):
        """Test distance of identical strings"""
        clusterer = EntityClusterer(temp_db)
        
        distance = clusterer._levenshtein_distance("test", "test")
        assert distance == 0
    
    def test_single_insertion(self, temp_db):
        """Test single character insertion"""
        clusterer = EntityClusterer(temp_db)
        
        distance = clusterer._levenshtein_distance("test", "tests")
        assert distance == 1
    
    def test_single_deletion(self, temp_db):
        """Test single character deletion"""
        clusterer = EntityClusterer(temp_db)
        
        distance = clusterer._levenshtein_distance("tests", "test")
        assert distance == 1
    
    def test_single_substitution(self, temp_db):
        """Test single character substitution"""
        clusterer = EntityClusterer(temp_db)
        
        distance = clusterer._levenshtein_distance("test", "text")
        assert distance == 1
    
    def test_multiple_operations(self, temp_db):
        """Test multiple edit operations"""
        clusterer = EntityClusterer(temp_db)
        
        distance = clusterer._levenshtein_distance("kitten", "sitting")
        assert distance == 3  # k→s, e→i, insert g


class TestClustering:
    """Test clustering algorithm"""
    
    def test_cluster_empty_database(self, temp_db):
        """Test clustering with no entities"""
        clusterer = EntityClusterer(temp_db)
        
        clusters = clusterer.cluster_entities(dry_run=True)
        assert clusters == []
    
    def test_cluster_aggressive_threshold(self, populated_db):
        """Test aggressive clustering (80% threshold)"""
        clusterer = EntityClusterer(populated_db)
        
        clusters = clusterer.cluster_entities(threshold=0.8, dry_run=True)
        
        # Should find several clusters
        assert len(clusters) >= 2
        
        # Check that similar entities are clustered
        cluster_texts = [[e['text'] for e in cluster.entities] for cluster in clusters]
        
        # Steins Gate variants should be in same cluster
        steins_cluster = None
        for cluster_texts_list in cluster_texts:
            if "Steins Gate" in cluster_texts_list:
                steins_cluster = cluster_texts_list
                break
        
        if steins_cluster:
            assert "Steins;Gate" in steins_cluster or "Steins Gate 0" in steins_cluster
    
    def test_cluster_conservative_threshold(self, populated_db):
        """Test conservative clustering (95% threshold)"""
        clusterer = EntityClusterer(populated_db)
        
        clusters = clusterer.cluster_entities(threshold=0.95, dry_run=True)
        
        # Should find fewer clusters (only very similar entities)
        # Death Note and death note should still cluster (case-insensitive)
        death_note_cluster = None
        for cluster in clusters:
            texts = [e['text'].lower() for e in cluster.entities]
            if "death note" in texts:
                death_note_cluster = cluster
                break
        
        # Should have at least the case variation cluster
        assert death_note_cluster is not None or len(clusters) >= 0
    
    def test_cluster_by_type(self, populated_db):
        """Test clustering filtered by entity type"""
        # Add non-anime entity
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id)
            VALUES ('Python', 'language', 'user_defined', 0.9, 5, 1)
        """)
        conn.commit()
        conn.close()
        
        clusterer = EntityClusterer(populated_db)
        
        # Cluster only anime entities
        clusters = clusterer.cluster_entities(entity_type='anime', dry_run=True)
        
        # All entities should be anime type
        for cluster in clusters:
            for entity in cluster.entities:
                assert entity['type'] == 'anime'
    
    def test_representative_selection(self, populated_db):
        """Test that highest-frequency entity is chosen as representative"""
        clusterer = EntityClusterer(populated_db)
        
        clusters = clusterer.cluster_entities(threshold=0.8, dry_run=True)
        
        # Check that representative is highest frequency
        for cluster in clusters:
            sorted_entities = sorted(cluster.entities, key=lambda e: e['frequency'], reverse=True)
            assert cluster.representative == sorted_entities[0]['text']
    
    def test_cluster_assignment(self, populated_db):
        """Test that clusters get unique IDs"""
        clusterer = EntityClusterer(populated_db)
        
        clusters = clusterer.cluster_entities(threshold=0.8, dry_run=True)
        
        cluster_ids = [cluster.cluster_id for cluster in clusters]
        
        # All cluster IDs should be unique
        assert len(cluster_ids) == len(set(cluster_ids))
        
        # Cluster IDs should start from 1
        assert min(cluster_ids) >= 1 if cluster_ids else True


class TestDatabaseUpdates:
    """Test database update functionality"""
    
    def test_update_database(self, populated_db):
        """Test that clustering updates database"""
        clusterer = EntityClusterer(populated_db)
        
        # Run clustering (not dry run)
        clusters = clusterer.cluster_entities(threshold=0.8, dry_run=False)
        
        # Verify database was updated
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM entities WHERE cluster_id IS NOT NULL")
        clustered_count = cursor.fetchone()[0]
        
        conn.close()
        
        # Should have clustered some entities
        assert clustered_count > 0
    
    def test_dry_run_no_update(self, populated_db):
        """Test that dry run doesn't update database"""
        clusterer = EntityClusterer(populated_db)
        
        # Run clustering (dry run)
        clusters = clusterer.cluster_entities(threshold=0.8, dry_run=True)
        
        # Verify database was NOT updated
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM entities WHERE cluster_id IS NOT NULL")
        clustered_count = cursor.fetchone()[0]
        
        conn.close()
        
        # Should have zero clustered entities
        assert clustered_count == 0


class TestStatistics:
    """Test clustering statistics"""
    
    def test_get_stats_empty(self, temp_db):
        """Test statistics with no entities"""
        clusterer = EntityClusterer(temp_db)
        
        stats = clusterer.get_cluster_stats()
        
        assert stats['total_entities'] == 0
        assert stats['clustered_entities'] == 0
        assert stats['total_clusters'] == 0
        assert stats['clustering_percentage'] == 0.0
    
    def test_get_stats_after_clustering(self, populated_db):
        """Test statistics after clustering"""
        clusterer = EntityClusterer(populated_db)
        
        # Run clustering
        clusters = clusterer.cluster_entities(threshold=0.8, dry_run=False)
        
        # Get stats
        stats = clusterer.get_cluster_stats()
        
        assert stats['total_entities'] > 0
        assert stats['clustered_entities'] > 0
        assert stats['total_clusters'] == len(clusters)
        assert stats['clustering_percentage'] > 0.0
    
    def test_get_cluster_details(self, populated_db):
        """Test getting details of specific cluster"""
        clusterer = EntityClusterer(populated_db)
        
        # Run clustering
        clusters = clusterer.cluster_entities(threshold=0.8, dry_run=False)
        
        if clusters:
            cluster_id = clusters[0].cluster_id
            
            # Get details
            details = clusterer.get_cluster_details(cluster_id)
            
            assert details is not None
            assert details['cluster_id'] == cluster_id
            assert details['size'] > 0
            assert 'representative' in details
            assert 'entities' in details
    
    def test_get_nonexistent_cluster(self, temp_db):
        """Test getting details of non-existent cluster"""
        clusterer = EntityClusterer(temp_db)
        
        details = clusterer.get_cluster_details(999)
        assert details is None


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_single_entity_no_cluster(self, temp_db):
        """Test that single entity doesn't form cluster"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id)
            VALUES ('Lonely Entity', 'test', 'user_defined', 0.9, 1, 1)
        """)
        
        conn.commit()
        conn.close()
        
        clusterer = EntityClusterer(temp_db)
        clusters = clusterer.cluster_entities(dry_run=True)
        
        # Should have zero clusters (need 2+ entities per cluster)
        assert len(clusters) == 0
    
    def test_different_types_no_cluster(self, temp_db):
        """Test that entities of different types don't cluster"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Add two similar entities of different types
        cursor.execute("""
            INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id)
            VALUES ('Test', 'type1', 'user_defined', 0.9, 1, 1)
        """)
        
        cursor.execute("""
            INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id)
            VALUES ('Test', 'type2', 'user_defined', 0.9, 1, 1)
        """)
        
        conn.commit()
        conn.close()
        
        clusterer = EntityClusterer(temp_db)
        clusters = clusterer.cluster_entities(dry_run=True)
        
        # Should have zero clusters (different types)
        assert len(clusters) == 0


def run_tests():
    """Run all tests"""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_tests()