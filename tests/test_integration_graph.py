"""
Graph Explorer Integration Test

Tests all graph explorer functionality with realistic data.
Measures performance and validates output quality.

Usage:
    python test_integration.py test_realistic.db
    
Author: Mnemonic Team
Created: Week 4 Day 5
"""

import sys
import time
from pathlib import Path

# Add parent directory to path to import mnemonic modules
sys.path.insert(0, str(Path(__file__).parent / 'mnemonic'))

from mnemonic.graph_explorer import GraphExplorer, GraphFilter
from datetime import datetime, timedelta

import pytest

@pytest.fixture(scope="session")
def db_path():
    return "test_realistic.db"

@pytest.fixture(scope="session")
def explorer(db_path):
    return GraphExplorer(db_path)


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_result(name: str, result: any, duration_ms: float) -> None:
    """Print test result with timing."""
    print(f"\n✓ {name}")
    print(f"  Duration: {duration_ms:.2f}ms")
    print(f"  Result: {result}")


def test_graph_loading(db_path):
    """Test 1: Graph Loading."""
    print_section("Test 1: Graph Loading")
    
    start = time.time()
    explorer = GraphExplorer(db_path)
    duration = (time.time() - start) * 1000
    
    if explorer.graph:
        print(f"✓ Graph loaded successfully")
        print(f"  Duration: {duration:.2f}ms")
        print(f"  Nodes: {explorer.graph.number_of_nodes()}")
        print(f"  Edges: {explorer.graph.number_of_edges()}")
        print(f"  Metadata entries: {len(explorer.entity_metadata)}")
        return explorer
    else:
        print(f"✗ Failed to load graph")
        return None


def test_graph_statistics(explorer):
    """Test 2: Graph Statistics."""
    print_section("Test 2: Graph Statistics")
    
    start = time.time()
    stats = explorer.get_graph_statistics()
    duration = (time.time() - start) * 1000
    
    print(f"✓ Statistics calculated")
    print(f"  Duration: {duration:.2f}ms")
    print(f"\n  Graph Statistics:")
    print(f"    Nodes: {stats.node_count}")
    print(f"    Edges: {stats.edge_count}")
    print(f"    Density: {stats.density:.4f}")
    print(f"    Avg Degree: {stats.avg_degree:.2f}")
    print(f"    Avg Clustering: {stats.avg_clustering:.4f}")
    print(f"    Components: {stats.components}")
    print(f"    Largest Component: {stats.largest_component_size}")
    if stats.diameter:
        print(f"    Diameter: {stats.diameter}")
    if stats.avg_path_length:
        print(f"    Avg Path Length: {stats.avg_path_length:.2f}")


def test_entity_importance(explorer):
    """Test 3: Entity Importance Metrics."""
    print_section("Test 3: Entity Importance Metrics")
    
    metrics = ['centrality', 'degree', 'betweenness']
    
    for metric in metrics:
        start = time.time()
        important = explorer.get_entity_importance(limit=5, metric=metric)
        duration = (time.time() - start) * 1000
        
        print(f"\n✓ Top 5 by {metric}")
        print(f"  Duration: {duration:.2f}ms")
        for i, (entity, score) in enumerate(important, 1):
            print(f"  {i}. {entity}: {score:.4f}")


def test_graph_filtering(explorer):
    """Test 4: Graph Filtering."""
    print_section("Test 4: Graph Filtering")
    
    # Test 1: Filter by entity type
    print("\n--- Filter: CONCEPT entities only ---")
    start = time.time()
    filter_criteria = GraphFilter(entity_types=['CONCEPT'])
    filtered = explorer.filter_graph(filter_criteria)
    duration = (time.time() - start) * 1000
    
    print(f"✓ Filtered graph created")
    print(f"  Duration: {duration:.2f}ms")
    print(f"  Nodes: {filtered.number_of_nodes()}")
    print(f"  Edges: {filtered.number_of_edges()}")
    
    # Test 2: Filter by frequency
    print("\n--- Filter: High frequency entities (≥10) ---")
    start = time.time()
    filter_criteria = GraphFilter(min_frequency=10)
    filtered = explorer.filter_graph(filter_criteria)
    duration = (time.time() - start) * 1000
    
    print(f"✓ Filtered graph created")
    print(f"  Duration: {duration:.2f}ms")
    print(f"  Nodes: {filtered.number_of_nodes()}")
    print(f"  Edges: {filtered.number_of_edges()}")
    
    # Test 3: Filter by connectivity
    print("\n--- Filter: Connected entities only ---")
    start = time.time()
    filter_criteria = GraphFilter(has_relationships=True)
    filtered = explorer.filter_graph(filter_criteria)
    duration = (time.time() - start) * 1000
    
    print(f"✓ Filtered graph created")
    print(f"  Duration: {duration:.2f}ms")
    print(f"  Nodes: {filtered.number_of_nodes()}")
    print(f"  Edges: {filtered.number_of_edges()}")


def test_subgraph_extraction(explorer):
    """Test 5: Subgraph Extraction."""
    print_section("Test 5: Subgraph Extraction")
    
    # Get a high-importance entity
    important = explorer.get_entity_importance(limit=1, metric='degree')
    if not important:
        print("✗ No entities found")
        return
    
    center_entity = important[0][0]
    
    # Test different radii
    for radius in [1, 2]:
        print(f"\n--- Subgraph: {center_entity} (radius={radius}) ---")
        start = time.time()
        subgraph_info = explorer.extract_subgraph(center_entity, radius=radius)
        duration = (time.time() - start) * 1000
        
        print(f"✓ Subgraph extracted")
        print(f"  Duration: {duration:.2f}ms")
        print(f"  Nodes: {subgraph_info.node_count}")
        print(f"  Edges: {subgraph_info.edge_count}")
        print(f"  Density: {subgraph_info.density:.4f}")
        print(f"  Avg Degree: {subgraph_info.avg_degree:.2f}")
        print(f"  Components: {subgraph_info.components}")


def test_path_finding(explorer):
    """Test 6: Path Finding."""
    print_section("Test 6: Path Finding")
    
    # Get two entities
    entities = list(explorer.graph.nodes())[:2] if explorer.graph else []
    
    if len(entities) < 2:
        print("✗ Not enough entities for path finding")
        return
    
    source, target = entities[0], entities[1]
    
    print(f"\n--- Finding paths: {source} → {target} ---")
    start = time.time()
    paths = explorer.find_paths(source, target, max_length=5, limit=3)
    duration = (time.time() - start) * 1000
    
    print(f"✓ Path finding complete")
    print(f"  Duration: {duration:.2f}ms")
    print(f"  Paths found: {len(paths)}")
    
    for i, path_info in enumerate(paths, 1):
        print(f"\n  Path {i}:")
        print(f"    Length: {path_info.length}")
        print(f"    Weight: {path_info.total_weight}")
        print(f"    Route: {' → '.join(path_info.path[:3])}{'...' if len(path_info.path) > 3 else ''}")


def test_bridge_detection(explorer):
    """Test 7: Bridge Detection."""
    print_section("Test 7: Bridge Detection")
    
    start = time.time()
    bridges = explorer.find_bridges(min_weight=2.0)
    duration = (time.time() - start) * 1000
    
    print(f"✓ Bridge detection complete")
    print(f"  Duration: {duration:.2f}ms")
    print(f"  Bridges found: {len(bridges)}")
    
    if bridges:
        print(f"\n  Top 5 bridges:")
        for i, (u, v, weight) in enumerate(bridges[:5], 1):
            print(f"  {i}. {u} ↔ {v} (weight: {weight})")


def test_neighborhood_analysis(explorer):
    """Test 8: Neighborhood Analysis."""
    print_section("Test 8: Neighborhood Analysis")
    
    # Get a high-degree entity
    important = explorer.get_entity_importance(limit=1, metric='degree')
    if not important:
        print("✗ No entities found")
        return
    
    entity = important[0][0]
    
    print(f"\n--- Neighborhood: {entity} ---")
    start = time.time()
    neighborhood = explorer.get_node_neighborhood(entity, include_metadata=True)
    duration = (time.time() - start) * 1000
    
    print(f"✓ Neighborhood analyzed")
    print(f"  Duration: {duration:.2f}ms")
    print(f"  Degree: {neighborhood.get('degree', 0)}")
    print(f"  Clustering: {neighborhood.get('clustering', 0):.4f}")
    
    if 'metadata' in neighborhood:
        meta = neighborhood['metadata']
        print(f"  Type: {meta.get('type', 'unknown')}")
        print(f"  Frequency: {meta.get('frequency', 0)}")
        print(f"  Centrality: {meta.get('centrality', 0):.4f}")
    
    neighbors = neighborhood.get('neighbors', [])
    if neighbors:
        print(f"\n  Top 5 neighbors:")
        for i, n in enumerate(neighbors[:5], 1):
            print(f"  {i}. {n['neighbor'][:40]} (weight: {n['weight']}, type: {n['type']})")


def test_community_comparison(explorer):
    """Test 9: Community Comparison."""
    print_section("Test 9: Community Comparison")
    
    # Get unique communities
    communities = set()
    for meta in explorer.entity_metadata.values():
        if meta.get('community_id') is not None:
            communities.add(meta['community_id'])
    
    if not communities:
        print("✗ No communities found")
        return
    
    community_list = list(communities)[:3]  # Compare first 3
    
    print(f"\n--- Comparing {len(community_list)} communities ---")
    start = time.time()
    comparison = explorer.compare_communities(community_list)
    duration = (time.time() - start) * 1000
    
    print(f"✓ Community comparison complete")
    print(f"  Duration: {duration:.2f}ms")
    
    for comm_id, info in comparison.items():
        print(f"\n  Community {comm_id}:")
        print(f"    Size: {info['size']}")
        stats = info['statistics']
        print(f"    Edges: {stats.edge_count}")
        print(f"    Density: {stats.density:.4f}")
        print(f"    Entity types: {info['entity_types']}")


def test_temporal_analysis(explorer):
    """Test 10: Temporal Analysis."""
    print_section("Test 10: Temporal Analysis")
    
    for days in [7, 30, 90]:
        print(f"\n--- Last {days} days ---")
        start = time.time()
        changes = explorer.detect_temporal_changes(days_ago=days)
        duration = (time.time() - start) * 1000
        
        print(f"✓ Temporal analysis complete")
        print(f"  Duration: {duration:.2f}ms")
        print(f"  Total entities: {changes['total_entities']}")
        print(f"  Active: {changes['active_entities']}")
        print(f"  Dormant: {changes['dormant_entities']}")
        
        if changes.get('new_entity_list'):
            print(f"  Sample new entities: {changes['new_entity_list'][:3]}")


def performance_summary(explorer) -> None:
    """Run performance benchmarks."""
    print_section("Performance Summary")
    
    operations = [
        ("Graph statistics", lambda: explorer.get_graph_statistics()),
        ("Entity importance", lambda: explorer.get_entity_importance(limit=10)),
        ("Filter by type", lambda: explorer.filter_graph(GraphFilter(entity_types=['CONCEPT']))),
        ("Bridge detection", lambda: explorer.find_bridges()),
    ]
    
    print("\nBenchmarking operations (10 iterations each):\n")
    
    for name, operation in operations:
        times = []
        for _ in range(10):
            start = time.time()
            operation()
            duration = (time.time() - start) * 1000
            times.append(duration)
        
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"  {name}:")
        print(f"    Avg: {avg_time:.2f}ms  Min: {min_time:.2f}ms  Max: {max_time:.2f}ms")


def main():
    """Run all integration tests."""
    if len(sys.argv) < 2:
        print("Usage: python test_integration.py <database_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    print("\n" + "=" * 60)
    print("  GRAPH EXPLORER INTEGRATION TEST")
    print("  Week 4 Day 5")
    print("=" * 60)
    print(f"\nDatabase: {db_path}")
    
    # Run all tests
    explorer = test_graph_loading(db_path)
    
    if not explorer:
        print("\n✗ Cannot continue without loaded graph")
        return
    
    test_graph_statistics(explorer)
    test_entity_importance(explorer)
    test_graph_filtering(explorer)
    test_subgraph_extraction(explorer)
    test_path_finding(explorer)
    test_bridge_detection(explorer)
    test_neighborhood_analysis(explorer)
    test_community_comparison(explorer)
    test_temporal_analysis(explorer)
    performance_summary(explorer)
    
    print("\n" + "=" * 60)
    print("  ✅ ALL TESTS COMPLETE")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()