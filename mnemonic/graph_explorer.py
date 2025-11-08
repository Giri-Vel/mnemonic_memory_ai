"""
Interactive Graph Explorer Module

Provides rich querying and exploration of entity relationship graphs:
- Graph filtering by multiple criteria
- Subgraph extraction
- Path finding and exploration
- Graph statistics and analysis
- Temporal graph changes

Author: Mnemonic Team
Created: Week 4 Day 4
"""

import networkx as nx
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import sqlite3


@dataclass
class GraphFilter:
    """Filter criteria for graph exploration."""
    entity_types: Optional[List[str]] = None
    min_frequency: Optional[int] = None
    max_frequency: Optional[int] = None
    min_centrality: Optional[float] = None
    communities: Optional[List[int]] = None
    has_relationships: Optional[bool] = None
    time_range: Optional[Tuple[datetime, datetime]] = None


@dataclass
class PathInfo:
    """Information about a path between entities."""
    path: List[str]
    length: int
    total_weight: float
    edge_types: List[str]
    intermediates: List[str]


@dataclass
class SubgraphInfo:
    """Information about an extracted subgraph."""
    nodes: List[str]
    edges: List[Tuple[str, str, float]]
    node_count: int
    edge_count: int
    density: float
    avg_degree: float
    components: int


@dataclass
class GraphStatistics:
    """Statistical summary of a graph."""
    node_count: int
    edge_count: int
    density: float
    avg_degree: float
    avg_clustering: float
    diameter: Optional[int]
    avg_path_length: Optional[float]
    components: int
    largest_component_size: int


class GraphExplorer:
    """
    Interactive graph exploration and querying system.
    
    Features:
    - Multi-criteria filtering
    - Subgraph extraction
    - Path finding
    - Statistical analysis
    - Temporal changes
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the graph explorer.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.graph: Optional[nx.Graph] = None
        self.entity_metadata: Dict[str, Dict] = {}
        self._load_graph()
    
    def _load_graph(self) -> None:
        """Load the complete graph from database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if entities table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='entities'
        """)
        
        if not cursor.fetchone():
            # Table doesn't exist yet - create empty graph
            self.graph = nx.Graph()
            self.entity_metadata = {}
            conn.close()
            return
        
        # Create graph
        self.graph = nx.Graph()
        
        # Load entities with metadata
        try:
            cursor.execute("""
                SELECT 
                    e.name,
                    e.type,
                    e.frequency,
                    e.community_id,
                    e.centrality
                FROM entities e
            """)
            
            for row in cursor.fetchall():
                entity = row['name']
                self.graph.add_node(entity)
                self.entity_metadata[entity] = {
                    'type': row['type'],
                    'frequency': row['frequency'],
                    'community_id': row['community_id'],
                    'centrality': row['centrality'] or 0.0
                }
        except sqlite3.OperationalError as e:
            # Table exists but might have different schema
            self.graph = nx.Graph()
            self.entity_metadata = {}
            conn.close()
            return
        
        # Load relationships
        try:
            cursor.execute("""
                SELECT 
                    e1.name as source,
                    e2.name as target,
                    r.co_occurrence as weight
                FROM relationships r
                JOIN entities e1 ON r.entity1_id = e1.id
                JOIN entities e2 ON r.entity2_id = e2.id
            """)
            
            for row in cursor.fetchall():
                self.graph.add_edge(
                    row['source'],
                    row['target'],
                    weight=row['weight']
                )
        except sqlite3.OperationalError:
            # Relationships table doesn't exist or different schema
            pass
        
        conn.close()
    
    def filter_graph(self, filter_criteria: GraphFilter) -> nx.Graph:
        """
        Filter the graph based on multiple criteria.
        
        Args:
            filter_criteria: Filter specifications
            
        Returns:
            Filtered subgraph
        """
        if not self.graph:
            return nx.Graph()
        
        # Start with all nodes
        filtered_nodes = set(self.graph.nodes())
        
        # Apply entity type filter
        if filter_criteria.entity_types:
            filtered_nodes = {
                node for node in filtered_nodes
                if self.entity_metadata.get(node, {}).get('type') in filter_criteria.entity_types
            }
        
        # Apply frequency filters
        if filter_criteria.min_frequency is not None:
            filtered_nodes = {
                node for node in filtered_nodes
                if self.entity_metadata.get(node, {}).get('frequency', 0) >= filter_criteria.min_frequency
            }
        
        if filter_criteria.max_frequency is not None:
            filtered_nodes = {
                node for node in filtered_nodes
                if self.entity_metadata.get(node, {}).get('frequency', 0) <= filter_criteria.max_frequency
            }
        
        # Apply centrality filter
        if filter_criteria.min_centrality is not None:
            filtered_nodes = {
                node for node in filtered_nodes
                if self.entity_metadata.get(node, {}).get('centrality', 0.0) >= filter_criteria.min_centrality
            }
        
        # Apply community filter
        if filter_criteria.communities:
            filtered_nodes = {
                node for node in filtered_nodes
                if self.entity_metadata.get(node, {}).get('community_id') in filter_criteria.communities
            }
        
        # Apply relationship filter
        if filter_criteria.has_relationships is not None:
            if filter_criteria.has_relationships:
                # Only nodes with edges
                filtered_nodes = {
                    node for node in filtered_nodes
                    if self.graph.degree(node) > 0
                }
            else:
                # Only isolated nodes
                filtered_nodes = {
                    node for node in filtered_nodes
                    if self.graph.degree(node) == 0
                }
        
        # Create subgraph
        return self.graph.subgraph(filtered_nodes).copy()
    
    def extract_subgraph(
        self,
        center_entity: str,
        radius: int = 1,
        min_edge_weight: float = 1.0
    ) -> SubgraphInfo:
        """
        Extract a subgraph around a center entity.
        
        Args:
            center_entity: Entity at the center
            radius: How many hops to include
            min_edge_weight: Minimum edge weight to include
            
        Returns:
            SubgraphInfo with details
        """
        if not self.graph or center_entity not in self.graph:
            return SubgraphInfo([], [], 0, 0, 0.0, 0.0, 0)
        
        # Get nodes within radius using BFS
        nodes = {center_entity}
        current_level = {center_entity}
        
        for _ in range(radius):
            next_level = set()
            for node in current_level:
                # Add neighbors
                for neighbor in self.graph.neighbors(node):
                    # Check edge weight
                    edge_data = self.graph.get_edge_data(node, neighbor)
                    if edge_data and edge_data.get('weight', 0) >= min_edge_weight:
                        next_level.add(neighbor)
            nodes.update(next_level)
            current_level = next_level
            
            if not current_level:
                break
        
        # Create subgraph
        subgraph = self.graph.subgraph(nodes)
        
        # Extract edges with weights
        edges = [
            (u, v, subgraph[u][v].get('weight', 0))
            for u, v in subgraph.edges()
        ]
        
        # Calculate statistics
        node_count = subgraph.number_of_nodes()
        edge_count = subgraph.number_of_edges()
        
        density = 0.0
        if node_count > 1:
            density = (2 * edge_count) / (node_count * (node_count - 1))
        
        avg_degree = 0.0
        if node_count > 0:
            avg_degree = sum(dict(subgraph.degree()).values()) / node_count
        
        components = nx.number_connected_components(subgraph)
        
        return SubgraphInfo(
            nodes=list(nodes),
            edges=edges,
            node_count=node_count,
            edge_count=edge_count,
            density=round(density, 3),
            avg_degree=round(avg_degree, 2),
            components=components
        )
    
    def find_paths(
        self,
        source: str,
        target: str,
        max_length: int = 5,
        limit: int = 5
    ) -> List[PathInfo]:
        """
        Find paths between two entities.
        
        Args:
            source: Starting entity
            target: Ending entity
            max_length: Maximum path length
            limit: Maximum number of paths to return
            
        Returns:
            List of PathInfo objects
        """
        if not self.graph or source not in self.graph or target not in self.graph:
            return []
        
        try:
            # Find all simple paths up to max_length
            all_paths = nx.all_simple_paths(
                self.graph,
                source,
                target,
                cutoff=max_length
            )
            
            # Convert to PathInfo objects
            path_infos = []
            for path in all_paths:
                if len(path_infos) >= limit:
                    break
                
                # Calculate total weight
                total_weight = 0.0
                edge_types = []
                
                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    edge_data = self.graph.get_edge_data(u, v)
                    if edge_data:
                        total_weight += edge_data.get('weight', 0)
                    
                    # Get edge type (based on entity types)
                    u_type = self.entity_metadata.get(u, {}).get('type', 'unknown')
                    v_type = self.entity_metadata.get(v, {}).get('type', 'unknown')
                    edge_types.append(f"{u_type}-{v_type}")
                
                # Get intermediate nodes
                intermediates = path[1:-1] if len(path) > 2 else []
                
                path_infos.append(PathInfo(
                    path=path,
                    length=len(path) - 1,
                    total_weight=round(total_weight, 2),
                    edge_types=edge_types,
                    intermediates=intermediates
                ))
            
            # Sort by length then weight
            path_infos.sort(key=lambda p: (p.length, -p.total_weight))
            
            return path_infos
        
        except nx.NetworkXNoPath:
            return []
    
    def find_bridges(self, min_weight: float = 1.0) -> List[Tuple[str, str, float]]:
        """
        Find bridge entities that connect different parts of the graph.
        
        Args:
            min_weight: Minimum edge weight to consider
            
        Returns:
            List of bridge edges with weights
        """
        if not self.graph:
            return []
        
        # Filter edges by weight
        weighted_graph = nx.Graph()
        for u, v, data in self.graph.edges(data=True):
            weight = data.get('weight', 0)
            if weight >= min_weight:
                weighted_graph.add_edge(u, v, weight=weight)
        
        # Find bridges
        bridges = list(nx.bridges(weighted_graph))
        
        # Add weights
        bridge_info = [
            (u, v, weighted_graph[u][v].get('weight', 0))
            for u, v in bridges
        ]
        
        # Sort by weight (descending)
        bridge_info.sort(key=lambda x: -x[2])
        
        return bridge_info
    
    def get_graph_statistics(self, graph: Optional[nx.Graph] = None) -> GraphStatistics:
        """
        Calculate comprehensive statistics for a graph.
        
        Args:
            graph: Graph to analyze (uses main graph if None)
            
        Returns:
            GraphStatistics object
        """
        if graph is None:
            graph = self.graph
        
        if not graph or graph.number_of_nodes() == 0:
            return GraphStatistics(0, 0, 0.0, 0.0, 0.0, None, None, 0, 0)
        
        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()
        
        # Density
        density = 0.0
        if node_count > 1:
            density = (2 * edge_count) / (node_count * (node_count - 1))
        
        # Average degree
        avg_degree = 0.0
        if node_count > 0:
            avg_degree = sum(dict(graph.degree()).values()) / node_count
        
        # Average clustering coefficient
        avg_clustering = nx.average_clustering(graph)
        
        # Components
        components = list(nx.connected_components(graph))
        num_components = len(components)
        largest_component_size = max(len(c) for c in components) if components else 0
        
        # Diameter and average path length (only for connected graphs)
        diameter = None
        avg_path_length = None
        
        if num_components == 1:
            try:
                diameter = nx.diameter(graph)
                avg_path_length = nx.average_shortest_path_length(graph)
            except:
                pass
        
        return GraphStatistics(
            node_count=node_count,
            edge_count=edge_count,
            density=round(density, 4),
            avg_degree=round(avg_degree, 2),
            avg_clustering=round(avg_clustering, 4),
            diameter=diameter,
            avg_path_length=round(avg_path_length, 2) if avg_path_length else None,
            components=num_components,
            largest_component_size=largest_component_size
        )
    
    def get_node_neighborhood(
        self,
        entity: str,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Get detailed information about a node and its neighborhood.
        
        Args:
            entity: Entity to analyze
            include_metadata: Include entity metadata
            
        Returns:
            Dictionary with neighborhood information
        """
        if not self.graph or entity not in self.graph:
            return {}
        
        # Get neighbors
        neighbors = list(self.graph.neighbors(entity))
        
        # Get edges with weights
        edges = [
            {
                'neighbor': neighbor,
                'weight': self.graph[entity][neighbor].get('weight', 0),
                'type': self.entity_metadata.get(neighbor, {}).get('type', 'unknown')
            }
            for neighbor in neighbors
        ]
        
        # Sort by weight
        edges.sort(key=lambda x: -x['weight'])
        
        # Calculate local clustering coefficient
        clustering = nx.clustering(self.graph, entity)
        
        # Get degree
        degree = self.graph.degree(entity)
        
        result = {
            'entity': entity,
            'degree': degree,
            'clustering': round(clustering, 4),
            'neighbors': edges
        }
        
        if include_metadata:
            result['metadata'] = self.entity_metadata.get(entity, {})
        
        return result
    
    def compare_communities(
        self,
        community_ids: List[int]
    ) -> Dict[int, Dict[str, Any]]:
        """
        Compare statistics across multiple communities.
        
        Args:
            community_ids: List of community IDs to compare
            
        Returns:
            Dictionary mapping community ID to statistics
        """
        if not self.graph:
            return {}
        
        results = {}
        
        for comm_id in community_ids:
            # Get nodes in this community
            nodes = [
                node for node in self.graph.nodes()
                if self.entity_metadata.get(node, {}).get('community_id') == comm_id
            ]
            
            if not nodes:
                continue
            
            # Create subgraph
            subgraph = self.graph.subgraph(nodes)
            
            # Get statistics
            stats = self.get_graph_statistics(subgraph)
            
            # Get entity types
            entity_types = defaultdict(int)
            for node in nodes:
                entity_type = self.entity_metadata.get(node, {}).get('type', 'unknown')
                entity_types[entity_type] += 1
            
            # Get top entities by centrality
            top_entities = sorted(
                [
                    (node, self.entity_metadata.get(node, {}).get('centrality', 0.0))
                    for node in nodes
                ],
                key=lambda x: -x[1]
            )[:5]
            
            results[comm_id] = {
                'size': len(nodes),
                'statistics': stats,
                'entity_types': dict(entity_types),
                'top_entities': top_entities
            }
        
        return results
    
    def detect_temporal_changes(
        self,
        days_ago: int = 30
    ) -> Dict[str, Any]:
        """
        Detect changes in the graph over time.
        
        Args:
            days_ago: How many days back to compare
            
        Returns:
            Dictionary with change information
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_ago)
        
        # Get entities mentioned in the time period
        cursor.execute("""
            SELECT DISTINCT e.name, e.type
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE m.created_at >= ?
        """, (cutoff_date,))
        
        recent_entities = {row['name']: row['type'] for row in cursor.fetchall()}
        
        # Get all entities
        all_entities = set(self.graph.nodes() if self.graph else [])
        
        # Calculate changes
        new_entities = set(recent_entities.keys()) - all_entities
        active_entities = set(recent_entities.keys()) & all_entities
        dormant_entities = all_entities - set(recent_entities.keys())
        
        # Get statistics for active subgraph
        if active_entities:
            active_subgraph = self.graph.subgraph(active_entities)
            active_stats = self.get_graph_statistics(active_subgraph)
        else:
            active_stats = None
        
        conn.close()
        
        return {
            'period_days': days_ago,
            'total_entities': len(all_entities),
            'new_entities': len(new_entities),
            'active_entities': len(active_entities),
            'dormant_entities': len(dormant_entities),
            'new_entity_list': list(new_entities)[:10],
            'active_statistics': active_stats
        }
    
    def get_entity_importance(
        self,
        limit: int = 10,
        metric: str = 'centrality'
    ) -> List[Tuple[str, float]]:
        """
        Rank entities by importance using various metrics.
        
        Args:
            limit: Number of entities to return
            metric: 'centrality', 'degree', 'betweenness', 'closeness'
            
        Returns:
            List of (entity, score) tuples
        """
        if not self.graph:
            return []
        
        scores = {}
        
        if metric == 'centrality':
            # Use stored centrality
            scores = {
                node: self.entity_metadata.get(node, {}).get('centrality', 0.0)
                for node in self.graph.nodes()
            }
        
        elif metric == 'degree':
            # Degree centrality
            scores = dict(self.graph.degree())
        
        elif metric == 'betweenness':
            # Betweenness centrality
            scores = nx.betweenness_centrality(self.graph)
        
        elif metric == 'closeness':
            # Closeness centrality (only for connected components)
            if nx.is_connected(self.graph):
                scores = nx.closeness_centrality(self.graph)
            else:
                # Calculate for largest component
                largest_cc = max(nx.connected_components(self.graph), key=len)
                subgraph = self.graph.subgraph(largest_cc)
                scores = nx.closeness_centrality(subgraph)
        
        # Sort and limit
        sorted_entities = sorted(
            scores.items(),
            key=lambda x: -x[1]
        )[:limit]
        
        return [(entity, round(score, 4)) for entity, score in sorted_entities]