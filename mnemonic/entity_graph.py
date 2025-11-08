"""
Entity Relationship Graph System (Week 4, Day 2)

Builds and analyzes relationship graphs from entity co-occurrences:
- NetworkX graph construction
- Graph metrics (centrality, clustering)
- Community detection
- Path finding
- ASCII visualization
- Multiple export formats (JSON, GraphML, DOT)
"""

import networkx as nx
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, asdict
import json
from collections import defaultdict

try:
    import community as community_louvain
    LOUVAIN_AVAILABLE = True
except ImportError:
    LOUVAIN_AVAILABLE = False


@dataclass
class GraphNode:
    """Represents a node (entity) in the graph"""
    id: str
    entity_type: Optional[str]
    frequency: int
    degree: int = 0
    centrality: float = 0.0
    community: Optional[int] = None


@dataclass
class GraphEdge:
    """Represents an edge (co-occurrence) in the graph"""
    source: str
    target: str
    weight: int
    memories: List[int]


@dataclass
class GraphMetrics:
    """Overall graph statistics"""
    num_nodes: int
    num_edges: int
    density: float
    avg_degree: float
    num_components: int
    num_communities: Optional[int] = None
    avg_clustering: Optional[float] = None


@dataclass
class PathResult:
    """Result from path finding"""
    source: str
    target: str
    path: List[str]
    length: int
    explanation: str


class EntityRelationshipGraph:
    """
    Builds and analyzes entity relationship graphs
    
    Features:
    - Graph construction from co-occurrences
    - Centrality analysis (identify important entities)
    - Community detection (find interest clusters)
    - Path finding (discover relationships)
    - Recommendation engine (suggest related entities)
    - Multiple export formats
    - ASCII visualization
    """
    
    def __init__(self, directed: bool = False):
        """
        Initialize graph builder
        
        Args:
            directed: Whether to create directed graph (default: undirected)
        """
        self.graph = nx.DiGraph() if directed else nx.Graph()
        self.directed = directed
        self.communities = {}
    
    def build_from_search_engine(self, search_engine, min_co_occurrence: int = 2):
        """
        Build graph from EntitySearchEngine
        
        Args:
            search_engine: EntitySearchEngine instance
            min_co_occurrence: Minimum co-occurrence threshold
        """
        from mnemonic.entity_search import EntitySearchEngine
        
        # Get co-occurrences
        co_occurrences = search_engine.find_co_occurrences(
            min_co_occurrence=min_co_occurrence,
            limit=1000
        )
        
        # Get entity stats for node attributes
        stats = search_engine.get_entity_statistics()
        entity_frequencies = {}
        entity_types = {}
        
        for entity_info in stats['top_entities']:
            entity_frequencies[entity_info['text']] = entity_info['frequency']
            entity_types[entity_info['text']] = entity_info['type']
        
        # Add all entities that have co-occurrences as nodes
        entities_in_graph = set()
        for co_occ in co_occurrences:
            entities_in_graph.add(co_occ.entity1)
            entities_in_graph.add(co_occ.entity2)
        
        # Add nodes with attributes
        for entity in entities_in_graph:
            self.graph.add_node(
                entity,
                entity_type=entity_types.get(entity),
                frequency=entity_frequencies.get(entity, 1)
            )
        
        # Add edges
        for co_occ in co_occurrences:
            self.graph.add_edge(
                co_occ.entity1,
                co_occ.entity2,
                weight=co_occ.co_occurrence_count,
                memories=co_occ.memories
            )
        
        return len(entities_in_graph), len(co_occurrences)
    
    def add_node(self, entity: str, entity_type: Optional[str] = None, frequency: int = 1):
        """Add a node to the graph"""
        self.graph.add_node(entity, entity_type=entity_type, frequency=frequency)
    
    def add_edge(self, entity1: str, entity2: str, weight: int = 1, memories: List[int] = None):
        """Add an edge to the graph"""
        self.graph.add_edge(
            entity1, 
            entity2, 
            weight=weight,
            memories=memories or []
        )
    
    def calculate_centrality(self) -> Dict[str, float]:
        """
        Calculate degree centrality (how connected each entity is)
        
        Returns:
            Dictionary mapping entity to centrality score
        """
        if len(self.graph.nodes()) == 0:
            return {}
        
        centrality = nx.degree_centrality(self.graph)
        
        # Store in node attributes
        for node, score in centrality.items():
            self.graph.nodes[node]['centrality'] = score
        
        return centrality
    
    def calculate_betweenness_centrality(self) -> Dict[str, float]:
        """
        Calculate betweenness centrality (entities that bridge communities)
        
        Returns:
            Dictionary mapping entity to betweenness score
        """
        if len(self.graph.nodes()) == 0:
            return {}
        
        return nx.betweenness_centrality(self.graph, weight='weight')
    
    def detect_communities(self) -> Dict[str, int]:
        """
        Detect communities using Louvain algorithm
        
        Returns:
            Dictionary mapping entity to community ID
        """
        if not LOUVAIN_AVAILABLE:
            print("⚠ python-louvain not available. Install with: pip install python-louvain")
            return {}
        
        if len(self.graph.nodes()) == 0:
            return {}
        
        # Convert to undirected for community detection
        if self.directed:
            G = self.graph.to_undirected()
        else:
            G = self.graph
        
        # Detect communities
        self.communities = community_louvain.best_partition(G, weight='weight')
        
        # Store in node attributes
        for node, community_id in self.communities.items():
            self.graph.nodes[node]['community'] = community_id
        
        return self.communities
    
    def get_community_entities(self, community_id: int) -> List[str]:
        """
        Get all entities in a specific community
        
        Args:
            community_id: Community identifier
        
        Returns:
            List of entity names in the community
        """
        if not self.communities:
            self.detect_communities()
        
        return [
            entity for entity, comm_id in self.communities.items()
            if comm_id == community_id
        ]
    
    def find_path(self, source: str, target: str) -> Optional[PathResult]:
        """
        Find shortest path between two entities
        
        Args:
            source: Starting entity
            target: Target entity
        
        Returns:
            PathResult or None if no path exists
        """
        if source not in self.graph or target not in self.graph:
            return None
        
        try:
            path = nx.shortest_path(self.graph, source, target, weight='weight')
            
            # Build explanation
            explanation_parts = []
            for i in range(len(path) - 1):
                edge_data = self.graph[path[i]][path[i+1]]
                weight = edge_data.get('weight', 1)
                explanation_parts.append(
                    f"{path[i]} ↔ {path[i+1]} ({weight} co-occurrences)"
                )
            
            explanation = " → ".join(explanation_parts)
            
            return PathResult(
                source=source,
                target=target,
                path=path,
                length=len(path) - 1,
                explanation=explanation
            )
        
        except nx.NetworkXNoPath:
            return None
    
    def get_related_entities(
        self, 
        entity: str, 
        top_n: int = 10,
        method: str = 'direct'
    ) -> List[Tuple[str, float]]:
        """
        Get entities related to a given entity
        
        Args:
            entity: Entity to find relations for
            top_n: Number of results to return
            method: 'direct' (direct neighbors) or 'indirect' (2-hop neighbors)
        
        Returns:
            List of (entity, score) tuples sorted by relevance
        """
        if entity not in self.graph:
            return []
        
        if method == 'direct':
            # Direct neighbors with edge weights
            neighbors = []
            for neighbor in self.graph.neighbors(entity):
                weight = self.graph[entity][neighbor].get('weight', 1)
                neighbors.append((neighbor, weight))
            
            # Sort by weight
            neighbors.sort(key=lambda x: x[1], reverse=True)
            return neighbors[:top_n]
        
        elif method == 'indirect':
            # 2-hop neighbors (friends of friends)
            indirect = defaultdict(float)
            
            # Get direct neighbors
            direct_neighbors = set(self.graph.neighbors(entity))
            
            # Get their neighbors
            for neighbor in direct_neighbors:
                direct_weight = self.graph[entity][neighbor].get('weight', 1)
                
                for second_neighbor in self.graph.neighbors(neighbor):
                    if second_neighbor != entity and second_neighbor not in direct_neighbors:
                        indirect_weight = self.graph[neighbor][second_neighbor].get('weight', 1)
                        # Combined score
                        indirect[second_neighbor] += direct_weight * indirect_weight
            
            # Sort by score
            results = sorted(indirect.items(), key=lambda x: x[1], reverse=True)
            return results[:top_n]
        
        return []
    
    def recommend_similar(
        self,
        entity: str,
        top_n: int = 5
    ) -> List[Tuple[str, str]]:
        """
        Recommend entities similar to the given entity
        
        Uses a combination of:
        - Direct connections
        - Shared connections
        - Community membership
        
        Args:
            entity: Entity to get recommendations for
            top_n: Number of recommendations
        
        Returns:
            List of (entity, reason) tuples
        """
        if entity not in self.graph:
            return []
        
        recommendations = []
        
        # Get direct neighbors (highest weight)
        direct = self.get_related_entities(entity, top_n=top_n, method='direct')
        for neighbor, weight in direct[:3]:
            recommendations.append((
                neighbor,
                f"Directly related ({int(weight)} co-occurrences)"
            ))
        
        # Get indirect neighbors
        indirect = self.get_related_entities(entity, top_n=top_n, method='indirect')
        for neighbor, score in indirect[:2]:
            recommendations.append((
                neighbor,
                f"Indirectly related (shared connections)"
            ))
        
        # Get community members
        if self.communities and entity in self.communities:
            community_id = self.communities[entity]
            community_members = self.get_community_entities(community_id)
            
            for member in community_members[:2]:
                if member != entity and member not in [r[0] for r in recommendations]:
                    recommendations.append((
                        member,
                        f"Same interest cluster (community {community_id})"
                    ))
        
        return recommendations[:top_n]
    
    def get_metrics(self) -> GraphMetrics:
        """
        Calculate overall graph metrics
        
        Returns:
            GraphMetrics object with statistics
        """
        if len(self.graph.nodes()) == 0:
            return GraphMetrics(0, 0, 0.0, 0.0, 0)
        
        num_nodes = self.graph.number_of_nodes()
        num_edges = self.graph.number_of_edges()
        
        # Density
        density = nx.density(self.graph)
        
        # Average degree
        degrees = [d for n, d in self.graph.degree()]
        avg_degree = sum(degrees) / len(degrees) if degrees else 0.0
        
        # Number of connected components
        if self.directed:
            num_components = nx.number_weakly_connected_components(self.graph)
        else:
            num_components = nx.number_connected_components(self.graph)
        
        # Communities
        num_communities = None
        if self.communities:
            num_communities = len(set(self.communities.values()))
        
        # Clustering coefficient
        avg_clustering = None
        try:
            if not self.directed:
                avg_clustering = nx.average_clustering(self.graph, weight='weight')
        except:
            pass
        
        return GraphMetrics(
            num_nodes=num_nodes,
            num_edges=num_edges,
            density=density,
            avg_degree=avg_degree,
            num_components=num_components,
            num_communities=num_communities,
            avg_clustering=avg_clustering
        )
    
    def to_ascii(self, max_entities: int = 20) -> str:
        """
        Generate ASCII representation of the graph
        
        Args:
            max_entities: Maximum entities to show
        
        Returns:
            ASCII graph string
        """
        if len(self.graph.nodes()) == 0:
            return "Empty graph"
        
        lines = []
        lines.append("\n" + "="*70)
        lines.append("ENTITY RELATIONSHIP GRAPH")
        lines.append("="*70 + "\n")
        
        # Get most central nodes
        centrality = self.calculate_centrality()
        top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:max_entities]
        
        # Show nodes and their connections
        for node, cent in top_nodes:
            node_data = self.graph.nodes[node]
            entity_type = node_data.get('entity_type', 'unknown')
            frequency = node_data.get('frequency', 1)
            
            lines.append(f"[{entity_type}] {node} (mentioned {frequency}x)")
            
            # Show connections
            neighbors = list(self.graph.neighbors(node))
            if neighbors:
                for neighbor in neighbors[:5]:  # Show top 5 connections
                    edge_data = self.graph[node][neighbor]
                    weight = edge_data.get('weight', 1)
                    lines.append(f"  ├─ ({weight}x) → {neighbor}")
                
                if len(neighbors) > 5:
                    lines.append(f"  └─ ... and {len(neighbors) - 5} more")
            
            lines.append("")
        
        # Add metrics
        metrics = self.get_metrics()
        lines.append("="*70)
        lines.append("GRAPH METRICS")
        lines.append("="*70)
        lines.append(f"Nodes: {metrics.num_nodes}")
        lines.append(f"Edges: {metrics.num_edges}")
        lines.append(f"Density: {metrics.density:.2%}")
        lines.append(f"Avg Degree: {metrics.avg_degree:.2f}")
        if metrics.num_communities:
            lines.append(f"Communities: {metrics.num_communities}")
        if metrics.avg_clustering:
            lines.append(f"Clustering: {metrics.avg_clustering:.2f}")
        lines.append("="*70 + "\n")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        """
        Export graph to dictionary format
        
        Returns:
            Dictionary with nodes and edges
        """
        nodes = []
        for node in self.graph.nodes():
            node_data = self.graph.nodes[node]
            nodes.append({
                'id': node,
                'type': node_data.get('entity_type'),
                'frequency': node_data.get('frequency', 1),
                'degree': self.graph.degree(node),
                'centrality': node_data.get('centrality', 0.0),
                'community': node_data.get('community')
            })
        
        edges = []
        for source, target in self.graph.edges():
            edge_data = self.graph[source][target]
            edges.append({
                'source': source,
                'target': target,
                'weight': edge_data.get('weight', 1),
                'memories': edge_data.get('memories', [])
            })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'directed': self.directed,
            'metrics': asdict(self.get_metrics())
        }
    
    def to_json(self, filepath: str):
        """Export graph to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def to_graphml(self, filepath: str):
        """Export graph to GraphML format (for Gephi, Cytoscape)"""
        # Create a copy without list attributes (GraphML doesn't support them)
        G = self.graph.copy()
        for u, v, data in G.edges(data=True):
            if 'memories' in data:
                # Convert list to comma-separated string
                data['memories'] = ','.join(map(str, data['memories']))
        
        nx.write_graphml(G, filepath)
    
    def to_dot(self, filepath: str):
        """Export graph to DOT format (for Graphviz)"""
        try:
            from networkx.drawing.nx_pydot import write_dot
            write_dot(self.graph, filepath)
        except ImportError:
            # Fallback to manual DOT generation
            with open(filepath, 'w') as f:
                if self.directed:
                    f.write("digraph G {\n")
                    edge_symbol = "->"
                else:
                    f.write("graph G {\n")
                    edge_symbol = "--"
                
                # Write nodes
                for node in self.graph.nodes():
                    node_data = self.graph.nodes[node]
                    entity_type = node_data.get('entity_type', 'unknown')
                    f.write(f'  "{node}" [type="{entity_type}"];\n')
                
                # Write edges
                for source, target in self.graph.edges():
                    edge_data = self.graph[source][target]
                    weight = edge_data.get('weight', 1)
                    f.write(f'  "{source}" {edge_symbol} "{target}" [weight={weight}];\n')
                
                f.write("}\n")


def main():
    """Test entity relationship graph"""
    import sys
    from mnemonic.config import DB_PATH
    from mnemonic.entity_search import EntitySearchEngine
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = DB_PATH
    
    print(f"\n{'='*70}")
    print("ENTITY RELATIONSHIP GRAPH TEST")
    print(f"{'='*70}\n")
    
    # Initialize search engine
    print("Initializing entity search engine...")
    engine = EntitySearchEngine(db_path)
    
    # Build graph
    print("Building relationship graph...")
    graph = EntityRelationshipGraph(directed=False)
    num_nodes, num_edges = graph.build_from_search_engine(engine, min_co_occurrence=2)
    
    print(f"✓ Graph built: {num_nodes} entities, {num_edges} relationships\n")
    
    if num_nodes == 0:
        print("No entities found. Add some memories with entities first!")
        return
    
    # Calculate centrality
    print("Calculating centrality...")
    centrality = graph.calculate_centrality()
    top_central = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
    
    print("Top 5 most central entities:")
    for entity, score in top_central:
        print(f"  • {entity}: {score:.2f}")
    print()
    
    # Detect communities
    print("Detecting communities...")
    communities = graph.detect_communities()
    
    if communities:
        num_communities = len(set(communities.values()))
        print(f"✓ Found {num_communities} communities\n")
        
        # Show first 3 communities
        for comm_id in range(min(3, num_communities)):
            members = graph.get_community_entities(comm_id)
            print(f"Community {comm_id}: {', '.join(members[:5])}")
            if len(members) > 5:
                print(f"  ... and {len(members) - 5} more")
        print()
    
    # Show ASCII visualization
    print(graph.to_ascii(max_entities=10))
    
    # Test recommendations
    if num_nodes > 0:
        test_entity = list(graph.graph.nodes())[0]
        print(f"Recommendations for '{test_entity}':")
        recommendations = graph.recommend_similar(test_entity, top_n=5)
        for entity, reason in recommendations:
            print(f"  • {entity} - {reason}")
        print()
    
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()