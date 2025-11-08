"""
Tests for Interactive Graph Explorer

Tests graph filtering, subgraph extraction, path finding, and statistics.

Author: Mnemonic Team
Created: Week 4 Day 4
"""

import pytest
import sqlite3
import os
from datetime import datetime, timedelta
import networkx as nx

from mnemonic.graph_explorer import (
    GraphExplorer,
    GraphFilter,
    PathInfo,
    SubgraphInfo,
    GraphStatistics
)


@pytest.fixture
def test_db():
    """Create a test database with realistic graph data."""
    db_path = "test_graph_explorer.db"
    
    # Remove if exists
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            content TEXT,
            created_at TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            type TEXT,
            frequency INTEGER DEFAULT 1,
            memory_id INTEGER,
            community_id INTEGER,
            centrality REAL,
            FOREIGN KEY (memory_id) REFERENCES memories(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY,
            entity1_id INTEGER,
            entity2_id INTEGER,
            co_occurrence INTEGER DEFAULT 1,
            FOREIGN KEY (entity1_id) REFERENCES entities(id),
            FOREIGN KEY (entity2_id) REFERENCES entities(id)
        )
    """)
    
    # Insert test data - Create a realistic graph structure
    now = datetime.now()
    
    # Community 1: Programming Languages (strongly connected)
    memories = [
        (1, "Python programming", (now - timedelta(days=5)).isoformat()),
        (2, "JavaScript development", (now - timedelta(days=10)).isoformat()),
        (3, "TypeScript features", (now - timedelta(days=15)).isoformat()),
        (4, "React framework", (now - timedelta(days=20)).isoformat()),
        (5, "Docker containers", (now - timedelta(days=100)).isoformat()),
    ]
    
    cursor.executemany("INSERT INTO memories VALUES (?, ?, ?)", memories)
    
    # Entities with different properties
    entities = [
        # Community 1 - Active technologies
        (1, "Python", "technology", 15, 1, 1, 0.85),
        (2, "JavaScript", "technology", 12, 2, 1, 0.75),
        (3, "TypeScript", "technology", 10, 3, 1, 0.70),
        (4, "React", "technology", 8, 4, 1, 0.65),
        
        # Community 2 - Infrastructure (moderately connected)
        (5, "Docker", "technology", 6, 5, 2, 0.45),
        (6, "Kubernetes", "technology", 4, 5, 2, 0.40),
        (7, "AWS", "technology", 5, 5, 2, 0.50),
        
        # Community 3 - Database (loosely connected)
        (8, "PostgreSQL", "technology", 7, 1, 3, 0.55),
        (9, "MongoDB", "technology", 3, 2, 3, 0.35),
        
        # Isolated entity
        (10, "Rust", "technology", 2, 3, None, 0.10),
    ]
    
    cursor.executemany("INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?)", entities)
    
    # Relationships - Create interesting graph structure
    relationships = [
        # Strong cluster: Python-JavaScript-TypeScript-React
        (1, 1, 2, 10),  # Python-JavaScript (strong)
        (2, 2, 3, 8),   # JavaScript-TypeScript (strong)
        (3, 3, 4, 7),   # TypeScript-React (strong)
        (4, 1, 3, 5),   # Python-TypeScript (medium)
        (5, 2, 4, 6),   # JavaScript-React (medium)
        
        # Infrastructure cluster
        (6, 5, 6, 4),   # Docker-Kubernetes (medium)
        (7, 6, 7, 3),   # Kubernetes-AWS (medium)
        (8, 5, 7, 3),   # Docker-AWS (medium)
        
        # Database cluster
        (9, 8, 9, 2),   # PostgreSQL-MongoDB (weak)
        
        # Bridges between communities
        (10, 1, 8, 4),  # Python-PostgreSQL (bridge)
        (11, 5, 8, 2),  # Docker-PostgreSQL (bridge)
        (12, 4, 5, 3),  # React-Docker (bridge)
    ]
    
    cursor.executemany("INSERT INTO relationships VALUES (?, ?, ?, ?)", relationships)
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


class TestGraphExplorerInit:
    """Test graph explorer initialization."""
    
    def test_initialization(self, test_db):
        """Test basic initialization."""
        explorer = GraphExplorer(test_db)
        
        assert explorer.graph is not None
        assert explorer.graph.number_of_nodes() == 10
        assert explorer.graph.number_of_edges() == 12
        assert len(explorer.entity_metadata) == 10
    
    def test_metadata_loaded(self, test_db):
        """Test that entity metadata is properly loaded."""
        explorer = GraphExplorer(test_db)
        
        python_meta = explorer.entity_metadata.get("Python")
        assert python_meta is not None
        assert python_meta['type'] == 'technology'
        assert python_meta['frequency'] == 15
        assert python_meta['community_id'] == 1
        assert python_meta['centrality'] == 0.85


class TestGraphFiltering:
    """Test graph filtering functionality."""
    
    def test_filter_by_type(self, test_db):
        """Test filtering by entity type."""
        explorer = GraphExplorer(test_db)
        
        filter_criteria = GraphFilter(entity_types=['technology'])
        filtered = explorer.filter_graph(filter_criteria)
        
        assert filtered.number_of_nodes() == 10  # All are technology
    
    def test_filter_by_frequency(self, test_db):
        """Test filtering by frequency."""
        explorer = GraphExplorer(test_db)
        
        # High frequency only
        filter_criteria = GraphFilter(min_frequency=10)
        filtered = explorer.filter_graph(filter_criteria)
        
        assert filtered.number_of_nodes() == 3  # Python, JavaScript, TypeScript
        assert "Python" in filtered.nodes()
        assert "Rust" not in filtered.nodes()
    
    def test_filter_by_centrality(self, test_db):
        """Test filtering by centrality."""
        explorer = GraphExplorer(test_db)
        
        filter_criteria = GraphFilter(min_centrality=0.60)
        filtered = explorer.filter_graph(filter_criteria)
        
        assert filtered.number_of_nodes() == 4  # Top 4 by centrality
        assert "Python" in filtered.nodes()
        assert "Docker" not in filtered.nodes()
    
    def test_filter_by_community(self, test_db):
        """Test filtering by community."""
        explorer = GraphExplorer(test_db)
        
        filter_criteria = GraphFilter(communities=[1])
        filtered = explorer.filter_graph(filter_criteria)
        
        assert filtered.number_of_nodes() == 4  # Community 1
        assert "Python" in filtered.nodes()
        assert "Docker" not in filtered.nodes()
    
    def test_filter_with_relationships(self, test_db):
        """Test filtering for connected nodes only."""
        explorer = GraphExplorer(test_db)
        
        filter_criteria = GraphFilter(has_relationships=True)
        filtered = explorer.filter_graph(filter_criteria)
        
        assert "Rust" not in filtered.nodes()  # Isolated
        assert "Python" in filtered.nodes()  # Connected
    
    def test_filter_isolated_nodes(self, test_db):
        """Test filtering for isolated nodes."""
        explorer = GraphExplorer(test_db)
        
        filter_criteria = GraphFilter(has_relationships=False)
        filtered = explorer.filter_graph(filter_criteria)
        
        assert filtered.number_of_nodes() == 1
        assert "Rust" in filtered.nodes()
    
    def test_combined_filters(self, test_db):
        """Test multiple filters combined."""
        explorer = GraphExplorer(test_db)
        
        filter_criteria = GraphFilter(
            entity_types=['technology'],
            min_frequency=5,
            min_centrality=0.50,
            has_relationships=True
        )
        filtered = explorer.filter_graph(filter_criteria)
        
        # Should get high-frequency, high-centrality, connected entities
        assert filtered.number_of_nodes() >= 3
        assert "Python" in filtered.nodes()
        assert "Rust" not in filtered.nodes()


class TestSubgraphExtraction:
    """Test subgraph extraction."""
    
    def test_extract_radius_1(self, test_db):
        """Test extraction with radius 1."""
        explorer = GraphExplorer(test_db)
        
        subgraph = explorer.extract_subgraph("Python", radius=1)
        
        assert subgraph.node_count >= 1
        assert "Python" in subgraph.nodes
        assert "JavaScript" in subgraph.nodes  # Direct neighbor
        assert subgraph.edge_count > 0
    
    def test_extract_radius_2(self, test_db):
        """Test extraction with radius 2."""
        explorer = GraphExplorer(test_db)
        
        subgraph = explorer.extract_subgraph("Python", radius=2)
        
        # Should include Python's neighbors and their neighbors
        assert subgraph.node_count > 3
        assert "React" in subgraph.nodes  # 2 hops away via JavaScript
    
    def test_extract_with_min_weight(self, test_db):
        """Test extraction with minimum edge weight."""
        explorer = GraphExplorer(test_db)
        
        # Only strong connections
        subgraph = explorer.extract_subgraph("Python", radius=2, min_edge_weight=5.0)
        
        # Should exclude weak edges
        assert subgraph.node_count < explorer.graph.number_of_nodes()
    
    def test_subgraph_statistics(self, test_db):
        """Test subgraph statistics calculation."""
        explorer = GraphExplorer(test_db)
        
        subgraph = explorer.extract_subgraph("Python", radius=1)
        
        assert subgraph.density >= 0
        assert subgraph.avg_degree >= 0
        assert subgraph.components >= 1
    
    def test_isolated_entity_subgraph(self, test_db):
        """Test subgraph of isolated entity."""
        explorer = GraphExplorer(test_db)
        
        subgraph = explorer.extract_subgraph("Rust", radius=1)
        
        assert subgraph.node_count == 1
        assert subgraph.edge_count == 0
        assert "Rust" in subgraph.nodes


class TestPathFinding:
    """Test path finding functionality."""
    
    def test_find_direct_path(self, test_db):
        """Test finding direct path between neighbors."""
        explorer = GraphExplorer(test_db)
        
        paths = explorer.find_paths("Python", "JavaScript")
        
        assert len(paths) > 0
        assert paths[0].length == 1  # Direct connection
        assert paths[0].path == ["Python", "JavaScript"]
    
    def test_find_indirect_path(self, test_db):
        """Test finding indirect paths."""
        explorer = GraphExplorer(test_db)
        
        paths = explorer.find_paths("Python", "React", max_length=3)
        
        assert len(paths) > 0
        # Shortest path should be 2-3 hops
        assert paths[0].length <= 3
    
    def test_multiple_paths(self, test_db):
        """Test finding multiple paths."""
        explorer = GraphExplorer(test_db)
        
        paths = explorer.find_paths("Python", "React", limit=3)
        
        # Should find multiple paths through different intermediates
        assert len(paths) > 1
        # Paths should be sorted by length
        assert paths[0].length <= paths[-1].length
    
    def test_path_weights(self, test_db):
        """Test path weight calculation."""
        explorer = GraphExplorer(test_db)
        
        paths = explorer.find_paths("Python", "JavaScript")
        
        assert paths[0].total_weight > 0
    
    def test_path_intermediates(self, test_db):
        """Test intermediate node tracking."""
        explorer = GraphExplorer(test_db)
        
        paths = explorer.find_paths("Python", "React", max_length=4)
        
        # Should find paths with intermediates
        long_paths = [p for p in paths if p.length > 1]
        assert any(len(p.intermediates) > 0 for p in long_paths)
    
    def test_no_path_exists(self, test_db):
        """Test when no path exists."""
        explorer = GraphExplorer(test_db)
        
        paths = explorer.find_paths("Python", "Rust")
        
        assert len(paths) == 0  # Rust is isolated


class TestBridgeDetection:
    """Test bridge entity detection."""
    
    def test_find_bridges(self, test_db):
        """Test finding bridge edges."""
        explorer = GraphExplorer(test_db)
        
        bridges = explorer.find_bridges(min_weight=1.0)
        
        assert len(bridges) > 0
        # Bridges should have weights
        assert all(isinstance(b[2], (int, float)) for b in bridges)
    
    def test_bridges_sorted_by_weight(self, test_db):
        """Test that bridges are sorted by weight."""
        explorer = GraphExplorer(test_db)
        
        bridges = explorer.find_bridges()
        
        if len(bridges) > 1:
            # Check descending order
            for i in range(len(bridges) - 1):
                assert bridges[i][2] >= bridges[i + 1][2]


class TestGraphStatistics:
    """Test graph statistics calculation."""
    
    def test_full_graph_statistics(self, test_db):
        """Test statistics on full graph."""
        explorer = GraphExplorer(test_db)
        
        stats = explorer.get_graph_statistics()
        
        assert stats.node_count == 10
        assert stats.edge_count == 12
        assert 0 <= stats.density <= 1
        assert stats.avg_degree > 0
        assert 0 <= stats.avg_clustering <= 1
        assert stats.components >= 1
    
    def test_subgraph_statistics(self, test_db):
        """Test statistics on filtered subgraph."""
        explorer = GraphExplorer(test_db)
        
        filter_criteria = GraphFilter(communities=[1])
        subgraph = explorer.filter_graph(filter_criteria)
        stats = explorer.get_graph_statistics(subgraph)
        
        assert stats.node_count == 4
        assert stats.edge_count > 0
    
    def test_connected_graph_metrics(self, test_db):
        """Test diameter and path length for connected graphs."""
        explorer = GraphExplorer(test_db)
        
        # Get largest connected component
        filter_criteria = GraphFilter(has_relationships=True)
        subgraph = explorer.filter_graph(filter_criteria)
        stats = explorer.get_graph_statistics(subgraph)
        
        # Should have diameter if fully connected
        assert stats.components >= 1
    
    def test_empty_graph_statistics(self, test_db):
        """Test statistics on empty graph."""
        explorer = GraphExplorer(test_db)
        
        empty_graph = nx.Graph()
        stats = explorer.get_graph_statistics(empty_graph)
        
        assert stats.node_count == 0
        assert stats.edge_count == 0


class TestNeighborhoodAnalysis:
    """Test node neighborhood analysis."""
    
    def test_get_neighborhood(self, test_db):
        """Test getting node neighborhood."""
        explorer = GraphExplorer(test_db)
        
        neighborhood = explorer.get_node_neighborhood("Python")
        
        assert neighborhood['entity'] == "Python"
        assert neighborhood['degree'] > 0
        assert 0 <= neighborhood['clustering'] <= 1
        assert len(neighborhood['neighbors']) > 0
    
    def test_neighborhood_with_metadata(self, test_db):
        """Test neighborhood with metadata."""
        explorer = GraphExplorer(test_db)
        
        neighborhood = explorer.get_node_neighborhood("Python", include_metadata=True)
        
        assert 'metadata' in neighborhood
        assert neighborhood['metadata']['type'] == 'technology'
    
    def test_neighbor_weights(self, test_db):
        """Test that neighbor weights are included."""
        explorer = GraphExplorer(test_db)
        
        neighborhood = explorer.get_node_neighborhood("Python")
        
        # Neighbors should have weights
        assert all('weight' in n for n in neighborhood['neighbors'])
        # Should be sorted by weight (descending)
        weights = [n['weight'] for n in neighborhood['neighbors']]
        assert weights == sorted(weights, reverse=True)
    
    def test_isolated_node_neighborhood(self, test_db):
        """Test neighborhood of isolated node."""
        explorer = GraphExplorer(test_db)
        
        neighborhood = explorer.get_node_neighborhood("Rust")
        
        assert neighborhood['degree'] == 0
        assert len(neighborhood['neighbors']) == 0


class TestCommunityComparison:
    """Test community comparison."""
    
    def test_compare_communities(self, test_db):
        """Test comparing multiple communities."""
        explorer = GraphExplorer(test_db)
        
        comparison = explorer.compare_communities([1, 2])
        
        assert 1 in comparison
        assert 2 in comparison
        assert comparison[1]['size'] > 0
        assert 'statistics' in comparison[1]
    
    def test_community_statistics(self, test_db):
        """Test community-level statistics."""
        explorer = GraphExplorer(test_db)
        
        comparison = explorer.compare_communities([1])
        
        comm1 = comparison[1]
        assert 'entity_types' in comm1
        assert 'top_entities' in comm1
        assert len(comm1['top_entities']) <= 5
    
    def test_empty_community(self, test_db):
        """Test comparison with non-existent community."""
        explorer = GraphExplorer(test_db)
        
        comparison = explorer.compare_communities([999])
        
        assert 999 not in comparison  # Should skip non-existent


class TestTemporalChanges:
    """Test temporal change detection."""
    
    def test_detect_recent_changes(self, test_db):
        """Test detecting changes in recent period."""
        explorer = GraphExplorer(test_db)
        
        changes = explorer.detect_temporal_changes(days_ago=30)
        
        assert 'total_entities' in changes
        assert 'active_entities' in changes
        assert 'dormant_entities' in changes
        assert changes['period_days'] == 30
    
    def test_active_vs_dormant(self, test_db):
        """Test active vs dormant classification."""
        explorer = GraphExplorer(test_db)
        
        changes = explorer.detect_temporal_changes(days_ago=30)
        
        # Python, JS, TS, React are recent
        assert changes['active_entities'] >= 4
        # Docker is old (100 days)
        assert changes['dormant_entities'] >= 1


class TestEntityImportance:
    """Test entity importance ranking."""
    
    def test_importance_by_centrality(self, test_db):
        """Test ranking by centrality."""
        explorer = GraphExplorer(test_db)
        
        top_entities = explorer.get_entity_importance(limit=5, metric='centrality')
        
        assert len(top_entities) <= 5
        # Python should be top (highest centrality)
        assert top_entities[0][0] == "Python"
        # Should be sorted descending
        scores = [score for _, score in top_entities]
        assert scores == sorted(scores, reverse=True)
    
    def test_importance_by_degree(self, test_db):
        """Test ranking by degree."""
        explorer = GraphExplorer(test_db)
        
        top_entities = explorer.get_entity_importance(limit=5, metric='degree')
        
        assert len(top_entities) <= 5
        assert all(isinstance(score, (int, float)) for _, score in top_entities)
    
    def test_importance_by_betweenness(self, test_db):
        """Test ranking by betweenness centrality."""
        explorer = GraphExplorer(test_db)
        
        top_entities = explorer.get_entity_importance(limit=5, metric='betweenness')
        
        assert len(top_entities) <= 5
        # Bridge entities should rank high
    
    def test_importance_limit(self, test_db):
        """Test limiting number of results."""
        explorer = GraphExplorer(test_db)
        
        top_3 = explorer.get_entity_importance(limit=3)
        
        assert len(top_3) == 3


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])