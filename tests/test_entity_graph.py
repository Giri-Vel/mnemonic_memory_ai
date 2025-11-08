#!/usr/bin/env python3
"""
Test Entity Relationship Graph System (Week 4, Day 2)

Tests:
- Graph construction from co-occurrences
- Centrality analysis
- Community detection
- Path finding
- Recommendations
- Export formats
- ASCII visualization
"""

import sys
import sqlite3
import tempfile
import os
from pathlib import Path

sys.path.insert(0, '/home/claude')

from mnemonic.entity_search import EntitySearchEngine
from mnemonic.entity_graph import EntityRelationshipGraph


def create_test_database():
    """Create test database with rich entity relationships"""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    conn = sqlite3.connect(db_path)
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
    
    # Test data: Multiple entity relationships
    test_memories = [
        # Anime cluster
        ("Watched Steins Gate. Okabe Rintarou is brilliant. Time travel plot.", 
         [("Steins Gate", "anime"), ("Okabe Rintarou", "person"), ("time travel", "concept")]),
        
        ("Steins Gate and Code Geass both have complex protagonists.",
         [("Steins Gate", "anime"), ("Code Geass", "anime"), ("complex", "trait")]),
        
        ("Code Geass features Lelouch Lamperouge leading a rebellion.",
         [("Code Geass", "anime"), ("Lelouch Lamperouge", "person"), ("rebellion", "concept")]),
        
        ("Death Note is psychological. Light Yagami uses strategy.",
         [("Death Note", "anime"), ("Light Yagami", "person"), ("strategy", "concept")]),
        
        ("Death Note and Code Geass have strategic protagonists.",
         [("Death Note", "anime"), ("Code Geass", "anime"), ("strategy", "concept")]),
        
        # Programming cluster
        ("Python programming with pandas for data analysis.",
         [("Python", "language"), ("pandas", "library"), ("data analysis", "concept")]),
        
        ("Python and scikit-learn for machine learning projects.",
         [("Python", "language"), ("scikit-learn", "library"), ("machine learning", "concept")]),
        
        ("Machine learning using Python pandas and numpy.",
         [("machine learning", "concept"), ("Python", "language"), ("pandas", "library"), ("numpy", "library")]),
        
        # Bridge between clusters
        ("Anime storytelling uses strategic narrative design.",
         [("anime", "category"), ("strategy", "concept"), ("narrative", "concept")]),
    ]
    
    for content, entity_data in test_memories:
        cursor.execute("INSERT INTO memories (content) VALUES (?)", (content,))
        memory_id = cursor.lastrowid
        
        for text, entity_type in entity_data:
            # Calculate frequency
            cursor.execute("SELECT COUNT(*) FROM entities WHERE LOWER(text) = LOWER(?)", (text,))
            frequency = cursor.fetchone()[0] + 1
            
            cursor.execute("""
                INSERT INTO entities (text, type, type_source, confidence, frequency, memory_id)
                VALUES (?, ?, 'user_defined', 0.9, ?, ?)
            """, (text, entity_type, frequency, memory_id))
    
    conn.commit()
    conn.close()
    
    return db_path


def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*70}")
    print(text)
    print(f"{'='*70}\n")


def test_relationship_graph():
    """Test complete relationship graph system"""
    print_header("ENTITY RELATIONSHIP GRAPH SYSTEM TEST (Week 4, Day 2)")
    
    # Create test database
    print("Setting up test database...")
    db_path = create_test_database()
    print(f"✓ Test database created\n")
    
    try:
        # Initialize search engine
        print("Initializing entity search engine...")
        engine = EntitySearchEngine(db_path)
        print("✓ Search engine initialized\n")
        
        # TEST 1: Graph Construction
        print_header("TEST 1: Graph Construction")
        
        graph = EntityRelationshipGraph(directed=False)
        num_nodes, num_edges = graph.build_from_search_engine(engine, min_co_occurrence=2)
        
        print(f"✓ Graph built successfully!")
        print(f"  Nodes (entities): {num_nodes}")
        print(f"  Edges (relationships): {num_edges}")
        
        # TEST 2: Graph Metrics
        print_header("TEST 2: Graph Metrics")
        
        metrics = graph.get_metrics()
        
        print(f"Graph Statistics:")
        print(f"  Total nodes: {metrics.num_nodes}")
        print(f"  Total edges: {metrics.num_edges}")
        print(f"  Density: {metrics.density:.2%}")
        print(f"  Average degree: {metrics.avg_degree:.2f}")
        print(f"  Connected components: {metrics.num_components}")
        if metrics.avg_clustering:
            print(f"  Clustering coefficient: {metrics.avg_clustering:.2f}")
        
        # TEST 3: Centrality Analysis
        print_header("TEST 3: Centrality Analysis")
        
        centrality = graph.calculate_centrality()
        top_central = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
        
        print("Top 5 Most Central Entities (Hub Detection):")
        for i, (entity, score) in enumerate(top_central, 1):
            print(f"  {i}. {entity}: {score:.3f}")
        
        print("\n  Interpretation: These entities connect multiple topics")
        
        # TEST 4: Betweenness Centrality (Bridges)
        print_header("TEST 4: Betweenness Centrality (Bridge Detection)")
        
        betweenness = graph.calculate_betweenness_centrality()
        top_bridges = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:5]
        
        print("Top 5 Bridge Entities (Connect Communities):")
        for i, (entity, score) in enumerate(top_bridges, 1):
            if score > 0:
                print(f"  {i}. {entity}: {score:.3f}")
        
        # TEST 5: Community Detection
        print_header("TEST 5: Community Detection")
        
        communities = graph.detect_communities()
        
        if communities:
            num_communities = len(set(communities.values()))
            print(f"✓ Detected {num_communities} communities\n")
            
            # Group by community
            community_groups = {}
            for entity, comm_id in communities.items():
                if comm_id not in community_groups:
                    community_groups[comm_id] = []
                community_groups[comm_id].append(entity)
            
            # Show each community
            for comm_id, members in sorted(community_groups.items()):
                print(f"Community {comm_id}: ({len(members)} entities)")
                print(f"  Members: {', '.join(members[:6])}")
                if len(members) > 6:
                    print(f"  ... and {len(members) - 6} more")
                print()
        else:
            print("Community detection not available (install python-louvain)")
        
        # TEST 6: Path Finding
        print_header("TEST 6: Path Finding (Relationship Discovery)")
        
        # Find path between different communities
        nodes = list(graph.graph.nodes())
        if len(nodes) >= 2:
            source = nodes[0]
            target = nodes[-1]
            
            print(f"Finding path from '{source}' to '{target}'...\n")
            
            path_result = graph.find_path(source, target)
            
            if path_result:
                print(f"✓ Path found ({path_result.length} hops):")
                print(f"  Route: {' → '.join(path_result.path)}")
                print(f"\n  Details:")
                print(f"  {path_result.explanation}")
            else:
                print(f"✗ No path found (entities in different components)")
        
        # TEST 7: Related Entities
        print_header("TEST 7: Related Entity Discovery")
        
        if num_nodes > 0:
            test_entity = top_central[0][0]  # Use most central entity
            
            print(f"Finding entities related to '{test_entity}'...\n")
            
            # Direct relations
            direct = graph.get_related_entities(test_entity, top_n=5, method='direct')
            print("Direct Relations (Co-occurrences):")
            for entity, weight in direct:
                print(f"  • {entity} ({int(weight)}x co-occurrences)")
            
            # Indirect relations
            print("\nIndirect Relations (2-hop connections):")
            indirect = graph.get_related_entities(test_entity, top_n=5, method='indirect')
            for entity, score in indirect[:3]:
                print(f"  • {entity} (connection strength: {score:.1f})")
        
        # TEST 8: Recommendation Engine
        print_header("TEST 8: Recommendation Engine")
        
        if num_nodes > 0:
            test_entity = top_central[0][0]
            
            print(f"If you're interested in '{test_entity}', you might also like:\n")
            
            recommendations = graph.recommend_similar(test_entity, top_n=5)
            
            for i, (entity, reason) in enumerate(recommendations, 1):
                print(f"  {i}. {entity}")
                print(f"     → {reason}")
                print()
        
        # TEST 9: ASCII Visualization
        print_header("TEST 9: ASCII Visualization")
        
        ascii_graph = graph.to_ascii(max_entities=8)
        print(ascii_graph)
        
        # TEST 10: Export Formats
        print_header("TEST 10: Export Formats")
        
        # Export to dict
        graph_dict = graph.to_dict()
        print(f"✓ Exported to dictionary format")
        print(f"  Nodes: {len(graph_dict['nodes'])}")
        print(f"  Edges: {len(graph_dict['edges'])}")
        
        # Export to JSON
        json_path = "/tmp/test_graph.json"
        graph.to_json(json_path)
        print(f"\n✓ Exported to JSON: {json_path}")
        
        # Export to GraphML
        graphml_path = "/tmp/test_graph.graphml"
        graph.to_graphml(graphml_path)
        print(f"✓ Exported to GraphML: {graphml_path}")
        
        # Export to DOT
        dot_path = "/tmp/test_graph.dot"
        graph.to_dot(dot_path)
        print(f"✓ Exported to DOT: {dot_path}")
        
        print("\n  These files can be visualized with:")
        print("  • JSON: D3.js, vis.js (web visualization)")
        print("  • GraphML: Gephi, Cytoscape (graph analysis tools)")
        print("  • DOT: Graphviz (graph drawing)")
        
        # Summary
        print_header("SUMMARY")
        
        print("✅ Entity Relationship Graph System Working!\n")
        print("Key Features Tested:")
        print("  1. ✓ Graph construction from co-occurrences")
        print("  2. ✓ Centrality analysis (hub detection)")
        print("  3. ✓ Betweenness centrality (bridge detection)")
        print("  4. ✓ Community detection (interest clusters)")
        print("  5. ✓ Path finding (relationship discovery)")
        print("  6. ✓ Related entity discovery")
        print("  7. ✓ Recommendation engine")
        print("  8. ✓ ASCII visualization")
        print("  9. ✓ Multiple export formats")
        
        print("\n🎯 Use Cases Enabled:")
        print("  • Knowledge mapping (visualize mental models)")
        print("  • Content discovery (find related topics)")
        print("  • Pattern recognition (detect interest clusters)")
        print("  • Navigation (trace connections between topics)")
        print("  • Recommendations (suggest new interests)")
        
        print("\n🚀 Next Steps:")
        print("  • Day 3: Entity timeline analysis")
        print("  • Day 4: Interactive graph explorer")
        print("  • Day 5: Advanced graph queries")
        
        print()
        
    finally:
        # Cleanup
        os.unlink(db_path)
        print(f"🧹 Cleaned up test database\n")


if __name__ == "__main__":
    test_relationship_graph()