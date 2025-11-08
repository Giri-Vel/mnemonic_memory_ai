"""
CLI Module for Graph Explorer

Provides interactive command-line interface for graph exploration features.

Commands:
- graph filter      : Filter graph by criteria
- graph subgraph    : Extract subgraph around entity
- graph path        : Find paths between entities
- graph bridges     : Find bridge connections
- graph stats       : Show graph statistics
- graph neighborhood: Show entity neighborhood
- graph communities : Compare communities
- graph temporal    : Detect temporal changes
- graph important   : Rank entities by importance

Author: Mnemonic Team
Created: Week 4 Day 4
"""

import click
import sqlite3
from datetime import datetime
from typing import Optional
from tabulate import tabulate

from mnemonic.graph_explorer import (
    GraphExplorer,
    GraphFilter
)


def check_entities_exist(db_path: str) -> tuple[bool, int]:
    """
    Check if entities table exists and has data.
    
    Returns:
        (exists, count) - Whether table exists and entity count
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='entities'
        """)
        
        if not cursor.fetchone():
            conn.close()
            return False, 0
        
        # Count entities
        cursor.execute("SELECT COUNT(*) FROM entities")
        count = cursor.fetchone()[0]
        
        conn.close()
        return True, count
        
    except Exception:
        return False, 0


def show_no_data_message():
    """Show helpful message when no entity data exists."""
    click.echo("\n⚠️  No entity data found in database\n")
    click.echo("The graph explorer needs entity data to work.\n")
    click.echo("📋 To get started:")
    click.echo("  1. Store some memories with entity mentions:")
    click.echo("     $ mnemonic store \"Learning Python for data science\"")
    click.echo("     $ mnemonic store \"Building a React app\"")
    click.echo()
    click.echo("  2. If you have entity extraction configured:")
    click.echo("     $ mnemonic entities status")
    click.echo()
    click.echo("  3. Then try graph commands:")
    click.echo("     $ mnemonic graph stats")
    click.echo()


@click.group()
def graph():
    """Interactive graph exploration and analysis."""
    pass


@graph.command()
@click.option('--type', '-t', 'entity_types', multiple=True,
              help='Filter by entity type (can specify multiple)')
@click.option('--min-frequency', type=int,
              help='Minimum entity frequency')
@click.option('--max-frequency', type=int,
              help='Maximum entity frequency')
@click.option('--min-centrality', type=float,
              help='Minimum centrality score')
@click.option('--community', '-c', 'communities', multiple=True, type=int,
              help='Filter by community ID (can specify multiple)')
@click.option('--connected/--isolated', default=None,
              help='Filter by connection status')
@click.option('--db', default='mnemonic.db',
              help='Database path')
def filter(entity_types, min_frequency, max_frequency, min_centrality,
           communities, connected, db):
    """
    Filter the graph by multiple criteria.
    
    Examples:
        # High-frequency entities
        mnemonic graph filter --min-frequency 10
        
        # Technology entities with high centrality
        mnemonic graph filter --type technology --min-centrality 0.5
        
        # Entities in specific communities
        mnemonic graph filter --community 1 --community 2
        
        # Only connected entities
        mnemonic graph filter --connected
    """
    explorer = GraphExplorer(db)
    
    # Build filter
    filter_criteria = GraphFilter(
        entity_types=list(entity_types) if entity_types else None,
        min_frequency=min_frequency,
        max_frequency=max_frequency,
        min_centrality=min_centrality,
        communities=list(communities) if communities else None,
        has_relationships=connected
    )
    
    # Apply filter
    filtered_graph = explorer.filter_graph(filter_criteria)
    
    # Get statistics
    stats = explorer.get_graph_statistics(filtered_graph)
    
    click.echo(f"\n🔍 Filtered Graph Results\n")
    click.echo(f"Filters Applied:")
    if entity_types:
        click.echo(f"  • Types: {', '.join(entity_types)}")
    if min_frequency:
        click.echo(f"  • Min Frequency: {min_frequency}")
    if max_frequency:
        click.echo(f"  • Max Frequency: {max_frequency}")
    if min_centrality:
        click.echo(f"  • Min Centrality: {min_centrality}")
    if communities:
        click.echo(f"  • Communities: {', '.join(map(str, communities))}")
    if connected is not None:
        click.echo(f"  • Status: {'Connected' if connected else 'Isolated'}")
    
    click.echo(f"\n📊 Statistics:")
    click.echo(f"  Nodes: {stats.node_count}")
    click.echo(f"  Edges: {stats.edge_count}")
    click.echo(f"  Density: {stats.density:.4f}")
    click.echo(f"  Avg Degree: {stats.avg_degree:.2f}")
    click.echo(f"  Components: {stats.components}")
    
    # Show top entities
    if filtered_graph.number_of_nodes() > 0:
        click.echo(f"\n📋 Top Entities:")
        nodes = list(filtered_graph.nodes())[:20]
        for i, node in enumerate(nodes, 1):
            meta = explorer.entity_metadata.get(node, {})
            freq = meta.get('frequency', 0)
            cent = meta.get('centrality', 0.0)
            click.echo(f"  {i}. {node} (freq: {freq}, centrality: {cent:.3f})")
        
        if len(filtered_graph.nodes()) > 20:
            click.echo(f"  ... and {len(filtered_graph.nodes()) - 20} more")


@graph.command()
@click.argument('entity')
@click.option('--radius', '-r', default=1, type=int,
              help='Number of hops to include')
@click.option('--min-weight', default=1.0, type=float,
              help='Minimum edge weight')
@click.option('--visualize/--no-visualize', default=True,
              help='Show ASCII visualization')
@click.option('--db', default='mnemonic.db',
              help='Database path')
def subgraph(entity, radius, min_weight, visualize, db):
    """
    Extract and analyze subgraph around an entity.
    
    Examples:
        # 1-hop neighborhood
        mnemonic graph subgraph Python
        
        # 2-hop with visualization
        mnemonic graph subgraph Python --radius 2
        
        # Only strong connections
        mnemonic graph subgraph Python --min-weight 5.0
    """
    explorer = GraphExplorer(db)
    
    subgraph_info = explorer.extract_subgraph(entity, radius, min_weight)
    
    click.echo(f"\n🌐 Subgraph: {entity}\n")
    click.echo(f"Radius: {radius} hops")
    click.echo(f"Min Weight: {min_weight}\n")
    
    click.echo(f"📊 Statistics:")
    click.echo(f"  Nodes: {subgraph_info.node_count}")
    click.echo(f"  Edges: {subgraph_info.edge_count}")
    click.echo(f"  Density: {subgraph_info.density:.3f}")
    click.echo(f"  Avg Degree: {subgraph_info.avg_degree:.2f}")
    click.echo(f"  Components: {subgraph_info.components}")
    
    if visualize and subgraph_info.edges:
        click.echo(f"\n🔗 Connections:")
        
        # Sort edges by weight
        sorted_edges = sorted(subgraph_info.edges, key=lambda x: -x[2])
        
        for source, target, weight in sorted_edges[:15]:
            bar_length = int(weight / 2)
            bar = "█" * min(bar_length, 20)
            click.echo(f"  {source:20s} {'─' * 3} {target:20s} {bar} {weight:.1f}")
        
        if len(subgraph_info.edges) > 15:
            click.echo(f"  ... and {len(subgraph_info.edges) - 15} more edges")
    
    # Show all nodes
    if subgraph_info.node_count <= 20:
        click.echo(f"\n📋 All Nodes:")
        for node in sorted(subgraph_info.nodes):
            meta = explorer.entity_metadata.get(node, {})
            node_type = meta.get('type', 'unknown')
            click.echo(f"  • {node} ({node_type})")


@graph.command()
@click.argument('source')
@click.argument('target')
@click.option('--max-length', '-l', default=5, type=int,
              help='Maximum path length')
@click.option('--limit', default=5, type=int,
              help='Maximum number of paths to show')
@click.option('--db', default='mnemonic.db',
              help='Database path')
def path(source, target, max_length, limit, db):
    """
    Find paths between two entities.
    
    Examples:
        # Find shortest paths
        mnemonic graph path Python React
        
        # Allow longer paths
        mnemonic graph path Python PostgreSQL --max-length 4
        
        # Show more alternatives
        mnemonic graph path Python Docker --limit 10
    """
    explorer = GraphExplorer(db)
    
    paths = explorer.find_paths(source, target, max_length, limit)
    
    if not paths:
        click.echo(f"\n❌ No path found between '{source}' and '{target}'")
        click.echo(f"   (max length: {max_length})")
        return
    
    click.echo(f"\n🛤️  Paths from '{source}' to '{target}'\n")
    
    for i, path_info in enumerate(paths, 1):
        click.echo(f"Path {i} (length: {path_info.length}, weight: {path_info.total_weight:.1f}):")
        
        # Show path with arrows
        path_str = " → ".join(path_info.path)
        click.echo(f"  {path_str}")
        
        # Show intermediates if any
        if path_info.intermediates:
            click.echo(f"  Via: {', '.join(path_info.intermediates)}")
        
        click.echo()


@graph.command()
@click.option('--min-weight', default=1.0, type=float,
              help='Minimum edge weight to consider')
@click.option('--limit', default=10, type=int,
              help='Maximum number of bridges to show')
@click.option('--db', default='mnemonic.db',
              help='Database path')
def bridges(min_weight, limit, db):
    """
    Find bridge connections in the graph.
    
    Bridges are edges whose removal would disconnect the graph.
    These represent important connections between different parts
    of your knowledge graph.
    
    Examples:
        # Find all bridges
        mnemonic graph bridges
        
        # Only strong bridges
        mnemonic graph bridges --min-weight 3.0
    """
    explorer = GraphExplorer(db)
    
    bridge_edges = explorer.find_bridges(min_weight)
    
    if not bridge_edges:
        click.echo(f"\n🌉 No bridges found (min weight: {min_weight})")
        return
    
    click.echo(f"\n🌉 Bridge Connections\n")
    click.echo(f"Bridges are critical connections that hold the graph together.\n")
    
    # Show bridges in a table
    table_data = []
    for i, (u, v, weight) in enumerate(bridge_edges[:limit], 1):
        u_meta = explorer.entity_metadata.get(u, {})
        v_meta = explorer.entity_metadata.get(v, {})
        
        u_type = u_meta.get('type', 'unknown')
        v_type = v_meta.get('type', 'unknown')
        
        table_data.append([
            i,
            f"{u} ({u_type})",
            f"{v} ({v_type})",
            f"{weight:.1f}"
        ])
    
    click.echo(tabulate(
        table_data,
        headers=["#", "Entity 1", "Entity 2", "Weight"],
        tablefmt="simple"
    ))
    
    if len(bridge_edges) > limit:
        click.echo(f"\n... and {len(bridge_edges) - limit} more bridges")


@graph.command()
@click.option('--full/--summary', default=False,
              help='Show full or summary statistics')
@click.option('--db', default='mnemonic.db',
              help='Database path')
def stats(full, db):
    """
    Show comprehensive graph statistics.
    
    Examples:
        # Quick summary
        mnemonic graph stats
        
        # Full detailed statistics
        mnemonic graph stats --full
    """
    # Check if data exists
    exists, count = check_entities_exist(db)
    if not exists or count == 0:
        show_no_data_message()
        return
    
    explorer = GraphExplorer(db)
    
    graph_stats = explorer.get_graph_statistics()
    
    click.echo(f"\n📊 Graph Statistics\n")
    
    # Basic stats
    click.echo(f"🔢 Size:")
    click.echo(f"  Nodes: {graph_stats.node_count}")
    click.echo(f"  Edges: {graph_stats.edge_count}")
    
    # Connectivity
    click.echo(f"\n🔗 Connectivity:")
    click.echo(f"  Density: {graph_stats.density:.4f}")
    click.echo(f"  Avg Degree: {graph_stats.avg_degree:.2f}")
    click.echo(f"  Components: {graph_stats.components}")
    click.echo(f"  Largest Component: {graph_stats.largest_component_size} nodes")
    
    if full:
        # Clustering
        click.echo(f"\n🕸️  Clustering:")
        click.echo(f"  Avg Clustering: {graph_stats.avg_clustering:.4f}")
        
        # Distance metrics
        if graph_stats.diameter:
            click.echo(f"\n📏 Distance:")
            click.echo(f"  Diameter: {graph_stats.diameter}")
            click.echo(f"  Avg Path Length: {graph_stats.avg_path_length:.2f}")
        
        # Entity types breakdown
        click.echo(f"\n📋 Entity Types:")
        type_counts = {}
        for meta in explorer.entity_metadata.values():
            entity_type = meta.get('type', 'unknown')
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1
        
        for entity_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            percentage = (count / graph_stats.node_count) * 100
            click.echo(f"  {entity_type}: {count} ({percentage:.1f}%)")


@graph.command()
@click.argument('entity')
@click.option('--with-metadata/--no-metadata', default=True,
              help='Include entity metadata')
@click.option('--db', default='mnemonic.db',
              help='Database path')
def neighborhood(entity, with_metadata, db):
    """
    Show detailed neighborhood information for an entity.
    
    Examples:
        # Full neighborhood details
        mnemonic graph neighborhood Python
        
        # Without metadata
        mnemonic graph neighborhood Python --no-metadata
    """
    explorer = GraphExplorer(db)
    
    neighborhood = explorer.get_node_neighborhood(entity, with_metadata)
    
    if not neighborhood:
        click.echo(f"\n❌ Entity '{entity}' not found")
        return
    
    click.echo(f"\n🏘️  Neighborhood: {entity}\n")
    
    # Basic info
    click.echo(f"📊 Metrics:")
    click.echo(f"  Degree: {neighborhood['degree']}")
    click.echo(f"  Clustering: {neighborhood['clustering']:.4f}")
    
    # Metadata
    if with_metadata and 'metadata' in neighborhood:
        meta = neighborhood['metadata']
        click.echo(f"\n📋 Metadata:")
        click.echo(f"  Type: {meta.get('type', 'unknown')}")
        click.echo(f"  Frequency: {meta.get('frequency', 0)}")
        click.echo(f"  Community: {meta.get('community_id', 'None')}")
        click.echo(f"  Centrality: {meta.get('centrality', 0.0):.3f}")
    
    # Neighbors
    if neighborhood['neighbors']:
        click.echo(f"\n🔗 Neighbors ({len(neighborhood['neighbors'])}):")
        
        table_data = []
        for i, neighbor in enumerate(neighborhood['neighbors'][:15], 1):
            neighbor_name = neighbor['neighbor']
            weight = neighbor['weight']
            neighbor_type = neighbor['type']
            
            # Create weight bar
            bar_length = int(weight / 2)
            bar = "█" * min(bar_length, 15)
            
            table_data.append([
                i,
                neighbor_name,
                neighbor_type,
                f"{bar} {weight:.1f}"
            ])
        
        click.echo(tabulate(
            table_data,
            headers=["#", "Entity", "Type", "Weight"],
            tablefmt="simple"
        ))
        
        if len(neighborhood['neighbors']) > 15:
            click.echo(f"\n... and {len(neighborhood['neighbors']) - 15} more neighbors")


@graph.command()
@click.argument('community_ids', nargs=-1, type=int, required=True)
@click.option('--db', default='mnemonic.db',
              help='Database path')
def communities(community_ids, db):
    """
    Compare statistics across communities.
    
    Examples:
        # Compare two communities
        mnemonic graph communities 1 2
        
        # Compare multiple
        mnemonic graph communities 1 2 3 4
    """
    explorer = GraphExplorer(db)
    
    comparison = explorer.compare_communities(list(community_ids))
    
    if not comparison:
        click.echo(f"\n❌ No data found for specified communities")
        return
    
    click.echo(f"\n🏘️  Community Comparison\n")
    
    for comm_id in community_ids:
        if comm_id not in comparison:
            click.echo(f"Community {comm_id}: Not found\n")
            continue
        
        comm_data = comparison[comm_id]
        stats = comm_data['statistics']
        
        click.echo(f"Community {comm_id}:")
        click.echo(f"  Size: {comm_data['size']} entities")
        click.echo(f"  Edges: {stats.edge_count}")
        click.echo(f"  Density: {stats.density:.4f}")
        click.echo(f"  Avg Degree: {stats.avg_degree:.2f}")
        
        # Entity types
        if comm_data['entity_types']:
            click.echo(f"  Types: {', '.join(f'{k}({v})' for k, v in comm_data['entity_types'].items())}")
        
        # Top entities
        if comm_data['top_entities']:
            top_names = [name for name, _ in comm_data['top_entities'][:3]]
            click.echo(f"  Top: {', '.join(top_names)}")
        
        click.echo()


@graph.command()
@click.option('--days', '-d', default=30, type=int,
              help='Number of days to analyze')
@click.option('--db', default='mnemonic.db',
              help='Database path')
def temporal(days, db):
    """
    Detect temporal changes in the graph.
    
    Shows which entities are newly added, recently active, or dormant.
    
    Examples:
        # Last 30 days
        mnemonic graph temporal
        
        # Last 7 days
        mnemonic graph temporal --days 7
        
        # Last quarter
        mnemonic graph temporal --days 90
    """
    explorer = GraphExplorer(db)
    
    changes = explorer.detect_temporal_changes(days)
    
    click.echo(f"\n📅 Temporal Analysis (last {days} days)\n")
    
    click.echo(f"📊 Overview:")
    click.echo(f"  Total Entities: {changes['total_entities']}")
    click.echo(f"  New Entities: {changes['new_entities']}")
    click.echo(f"  Active Entities: {changes['active_entities']}")
    click.echo(f"  Dormant Entities: {changes['dormant_entities']}")
    
    # Activity percentage
    if changes['total_entities'] > 0:
        activity_pct = (changes['active_entities'] / changes['total_entities']) * 100
        click.echo(f"  Activity Rate: {activity_pct:.1f}%")
    
    # New entities
    if changes['new_entity_list']:
        click.echo(f"\n🆕 Recently Added:")
        for entity in changes['new_entity_list'][:10]:
            click.echo(f"  • {entity}")
    
    # Active graph stats
    if changes['active_statistics']:
        stats = changes['active_statistics']
        click.echo(f"\n📈 Active Subgraph:")
        click.echo(f"  Nodes: {stats.node_count}")
        click.echo(f"  Edges: {stats.edge_count}")
        click.echo(f"  Density: {stats.density:.4f}")
        click.echo(f"  Avg Degree: {stats.avg_degree:.2f}")


@graph.command()
@click.option('--metric', '-m',
              type=click.Choice(['centrality', 'degree', 'betweenness', 'closeness']),
              default='centrality',
              help='Importance metric to use')
@click.option('--limit', '-l', default=10, type=int,
              help='Number of entities to show')
@click.option('--db', default='mnemonic.db',
              help='Database path')
def important(metric, limit, db):
    """
    Rank entities by importance using various metrics.
    
    Metrics:
        centrality   - PageRank-based importance
        degree       - Number of connections
        betweenness  - How often entity appears on shortest paths
        closeness    - Average distance to all other entities
    
    Examples:
        # Top 10 by centrality
        mnemonic graph important
        
        # Top 20 by betweenness
        mnemonic graph important --metric betweenness --limit 20
        
        # Most connected
        mnemonic graph important --metric degree
    """
    explorer = GraphExplorer(db)
    
    top_entities = explorer.get_entity_importance(limit, metric)
    
    if not top_entities:
        click.echo(f"\n❌ No entities found")
        return
    
    # Metric descriptions
    metric_desc = {
        'centrality': 'PageRank-based importance',
        'degree': 'Number of connections',
        'betweenness': 'Frequency on shortest paths',
        'closeness': 'Average distance to others'
    }
    
    click.echo(f"\n⭐ Top {limit} Entities by {metric.title()}")
    click.echo(f"   ({metric_desc[metric]})\n")
    
    table_data = []
    for i, (entity, score) in enumerate(top_entities, 1):
        meta = explorer.entity_metadata.get(entity, {})
        entity_type = meta.get('type', 'unknown')
        frequency = meta.get('frequency', 0)
        
        # Create score bar
        if metric == 'degree':
            bar_length = int(score / 2)
        else:
            bar_length = int(score * 20)
        bar = "█" * min(bar_length, 20)
        
        table_data.append([
            i,
            entity,
            entity_type,
            frequency,
            f"{bar} {score:.3f}"
        ])
    
    click.echo(tabulate(
        table_data,
        headers=["Rank", "Entity", "Type", "Frequency", f"{metric.title()} Score"],
        tablefmt="simple"
    ))


if __name__ == '__main__':
    graph()