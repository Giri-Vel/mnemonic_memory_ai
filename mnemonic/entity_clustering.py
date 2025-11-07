"""
Entity Clustering System (Day 7)

Clusters similar entities using aggressive fuzzy matching (80%+ similarity).

Use Cases:
- "Steins Gate" = "Steins;Gate" = "Steins Gate 0"
- "Sarah Chen" = "Sarah" = "S. Chen"
- "Porsche 911" = "911 Turbo" = "Porsche 911 Turbo"

Algorithm:
1. Calculate similarity between all entity pairs (Levenshtein distance)
2. Group entities with similarity >= threshold (default: 0.8)
3. Assign cluster_id to grouped entities
4. Update database with cluster assignments
"""

import sqlite3
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class EntityCluster:
    """Represents a cluster of similar entities"""
    cluster_id: int
    entities: List[Dict]  # List of entity dicts
    representative: str  # Most common/best entity text
    total_frequency: int
    similarity_score: float  # Average intra-cluster similarity


class EntityClusterer:
    """
    Clusters entities using aggressive fuzzy matching
    
    Strategy:
    - 80%+ similarity = same cluster (aggressive)
    - Uses Levenshtein distance for similarity
    - Groups transitively (if A→B and B→C, then A→C)
    - Prefers higher-frequency entities as representatives
    """
    
    # Aggressive threshold (0.8 = 80% similar)
    DEFAULT_THRESHOLD = 0.8
    
    def __init__(self, db_path: str, verbose: bool = False):
        """
        Initialize the entity clusterer
        
        Args:
            db_path: Path to SQLite database
            verbose: Enable verbose logging
        """
        self.db_path = db_path
        self.verbose = verbose
    
    def _log(self, message: str):
        """Log message if verbose mode enabled"""
        if self.verbose:
            print(f"[Clusterer] {message}")
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two strings using normalized Levenshtein distance
        
        Args:
            text1: First string
            text2: Second string
        
        Returns:
            Similarity score (0.0 to 1.0, where 1.0 = identical)
        """
        # Normalize texts (lowercase, strip)
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        # Handle empty strings - they should be considered different (0.0 similarity)
        if not t1 or not t2:
            return 0.0
        
        # Identical check
        if t1 == t2:
            return 1.0
        
        # Calculate Levenshtein distance
        distance = self._levenshtein_distance(t1, t2)
        
        # Normalize by max length
        max_len = max(len(t1), len(t2))
        
        if max_len == 0:
            return 0.0
        
        # Convert distance to similarity (0 = identical, max_len = completely different)
        similarity = 1.0 - (distance / max_len)
        
        return similarity
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings
        
        Args:
            s1: First string
            s2: Second string
        
        Returns:
            Edit distance (number of operations to transform s1 to s2)
        """
        # Handle empty strings
        if len(s1) == 0:
            return len(s2)
        if len(s2) == 0:
            return len(s1)
        
        # Create distance matrix
        matrix = [[0] * (len(s2) + 1) for _ in range(len(s1) + 1)]
        
        # Initialize first column and row
        for i in range(len(s1) + 1):
            matrix[i][0] = i
        for j in range(len(s2) + 1):
            matrix[0][j] = j
        
        # Fill matrix
        for i in range(1, len(s1) + 1):
            for j in range(1, len(s2) + 1):
                if s1[i-1] == s2[j-1]:
                    cost = 0
                else:
                    cost = 1
                
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # Deletion
                    matrix[i][j-1] + 1,      # Insertion
                    matrix[i-1][j-1] + cost  # Substitution
                )
        
        return matrix[len(s1)][len(s2)]
    
    def cluster_entities(
        self,
        threshold: Optional[float] = None,
        entity_type: Optional[str] = None,
        dry_run: bool = False
    ) -> List[EntityCluster]:
        """
        Cluster entities using fuzzy matching
        
        Args:
            threshold: Similarity threshold (default: 0.8)
            entity_type: Only cluster entities of this type (None = all)
            dry_run: If True, don't update database (just return clusters)
        
        Returns:
            List of EntityCluster objects
        """
        threshold = threshold or self.DEFAULT_THRESHOLD
        
        self._log(f"Starting clustering (threshold: {threshold})")
        
        # Get all confirmed entities
        entities = self._get_entities(entity_type)
        
        if len(entities) == 0:
            self._log("No entities to cluster")
            return []
        
        self._log(f"Loaded {len(entities)} entities")
        
        # Build similarity graph
        similarity_graph = self._build_similarity_graph(entities, threshold)
        
        self._log(f"Built similarity graph with {len(similarity_graph)} connections")
        
        # Find connected components (clusters)
        clusters = self._find_clusters(entities, similarity_graph)
        
        self._log(f"Found {len(clusters)} clusters")
        
        # Assign cluster IDs and calculate stats
        entity_clusters = self._create_cluster_objects(clusters, entities)
        
        # Update database (unless dry run)
        if not dry_run:
            self._update_database(entity_clusters)
            self._log("Database updated with cluster assignments")
        
        return entity_clusters
    
    def _get_entities(self, entity_type: Optional[str] = None) -> List[Dict]:
        """
        Get all confirmed entities from database
        
        Args:
            entity_type: Filter by type (None = all types)
        
        Returns:
            List of entity dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if entity_type:
            cursor.execute("""
                SELECT id, text, type, frequency, cluster_id
                FROM entities
                WHERE type = ?
                ORDER BY frequency DESC
            """, (entity_type,))
        else:
            cursor.execute("""
                SELECT id, text, type, frequency, cluster_id
                FROM entities
                ORDER BY frequency DESC
            """)
        
        entities = []
        for row in cursor.fetchall():
            entities.append({
                'id': row[0],
                'text': row[1],
                'type': row[2],
                'frequency': row[3],
                'cluster_id': row[4]
            })
        
        conn.close()
        
        return entities
    
    def _build_similarity_graph(
        self,
        entities: List[Dict],
        threshold: float
    ) -> Dict[int, List[int]]:
        """
        Build similarity graph (adjacency list)
        
        Args:
            entities: List of entity dictionaries
            threshold: Similarity threshold
        
        Returns:
            Graph as adjacency list {entity_id: [similar_entity_ids]}
        """
        graph = defaultdict(list)
        
        # Compare all pairs
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                e1 = entities[i]
                e2 = entities[j]
                
                # Only cluster entities of same type
                if e1['type'] != e2['type']:
                    continue
                
                # Calculate similarity
                similarity = self.calculate_similarity(e1['text'], e2['text'])
                
                # Add edge if similar enough
                if similarity >= threshold:
                    graph[e1['id']].append(e2['id'])
                    graph[e2['id']].append(e1['id'])
        
        return dict(graph)
    
    def _find_clusters(
        self,
        entities: List[Dict],
        graph: Dict[int, List[int]]
    ) -> List[Set[int]]:
        """
        Find connected components (clusters) using DFS
        
        Args:
            entities: List of entity dictionaries
            graph: Similarity graph
        
        Returns:
            List of clusters (each cluster is a set of entity IDs)
        """
        entity_ids = {e['id'] for e in entities}
        visited = set()
        clusters = []
        
        def dfs(node_id: int, cluster: Set[int]):
            """Depth-first search to find connected component"""
            visited.add(node_id)
            cluster.add(node_id)
            
            # Visit neighbors
            for neighbor_id in graph.get(node_id, []):
                if neighbor_id not in visited:
                    dfs(neighbor_id, cluster)
        
        # Find all connected components
        for entity_id in entity_ids:
            if entity_id not in visited:
                cluster = set()
                dfs(entity_id, cluster)
                
                # Only keep clusters with 2+ entities
                if len(cluster) >= 2:
                    clusters.append(cluster)
        
        return clusters
    
    def _create_cluster_objects(
        self,
        clusters: List[Set[int]],
        entities: List[Dict]
    ) -> List[EntityCluster]:
        """
        Create EntityCluster objects with representatives
        
        Args:
            clusters: List of clusters (sets of entity IDs)
            entities: List of entity dictionaries
        
        Returns:
            List of EntityCluster objects
        """
        entity_by_id = {e['id']: e for e in entities}
        entity_clusters = []
        
        for cluster_id, entity_ids in enumerate(clusters, start=1):
            # Get entities in this cluster
            cluster_entities = [entity_by_id[eid] for eid in entity_ids]
            
            # Sort by frequency (descending)
            cluster_entities.sort(key=lambda e: e['frequency'], reverse=True)
            
            # Choose representative (highest frequency)
            representative = cluster_entities[0]['text']
            
            # Calculate total frequency
            total_frequency = sum(e['frequency'] for e in cluster_entities)
            
            # Calculate average intra-cluster similarity
            similarities = []
            for i in range(len(cluster_entities)):
                for j in range(i + 1, len(cluster_entities)):
                    sim = self.calculate_similarity(
                        cluster_entities[i]['text'],
                        cluster_entities[j]['text']
                    )
                    similarities.append(sim)
            
            avg_similarity = sum(similarities) / len(similarities) if similarities else 1.0
            
            entity_clusters.append(EntityCluster(
                cluster_id=cluster_id,
                entities=cluster_entities,
                representative=representative,
                total_frequency=total_frequency,
                similarity_score=avg_similarity
            ))
        
        return entity_clusters
    
    def _update_database(self, clusters: List[EntityCluster]) -> None:
        """
        Update database with cluster assignments
        
        Args:
            clusters: List of EntityCluster objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for cluster in clusters:
                for entity in cluster.entities:
                    cursor.execute("""
                        UPDATE entities
                        SET cluster_id = ?
                        WHERE id = ?
                    """, (cluster.cluster_id, entity['id']))
            
            conn.commit()
        
        except Exception as e:
            conn.rollback()
            self._log(f"Error updating database: {e}")
            raise
        finally:
            conn.close()
    
    def get_cluster_stats(self) -> Dict:
        """
        Get clustering statistics
        
        Returns:
            Dictionary with clustering stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total entities
        cursor.execute("SELECT COUNT(*) FROM entities")
        stats['total_entities'] = cursor.fetchone()[0]
        
        # Clustered entities
        cursor.execute("SELECT COUNT(*) FROM entities WHERE cluster_id IS NOT NULL")
        stats['clustered_entities'] = cursor.fetchone()[0]
        
        # Unique clusters
        cursor.execute("SELECT COUNT(DISTINCT cluster_id) FROM entities WHERE cluster_id IS NOT NULL")
        stats['total_clusters'] = cursor.fetchone()[0]
        
        # Average cluster size
        if stats['total_clusters'] > 0:
            stats['avg_cluster_size'] = stats['clustered_entities'] / stats['total_clusters']
        else:
            stats['avg_cluster_size'] = 0.0
        
        # Clustering percentage
        if stats['total_entities'] > 0:
            stats['clustering_percentage'] = (stats['clustered_entities'] / stats['total_entities']) * 100
        else:
            stats['clustering_percentage'] = 0.0
        
        # Largest clusters
        cursor.execute("""
            SELECT cluster_id, COUNT(*) as size
            FROM entities
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
            ORDER BY size DESC
            LIMIT 5
        """)
        
        stats['largest_clusters'] = [
            {'cluster_id': row[0], 'size': row[1]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        return stats
    
    def get_cluster_details(self, cluster_id: int) -> Optional[Dict]:
        """
        Get detailed information about a specific cluster
        
        Args:
            cluster_id: Cluster identifier
        
        Returns:
            Dictionary with cluster details or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, text, type, frequency
            FROM entities
            WHERE cluster_id = ?
            ORDER BY frequency DESC
        """, (cluster_id,))
        
        entities = []
        for row in cursor.fetchall():
            entities.append({
                'id': row[0],
                'text': row[1],
                'type': row[2],
                'frequency': row[3]
            })
        
        conn.close()
        
        if not entities:
            return None
        
        return {
            'cluster_id': cluster_id,
            'size': len(entities),
            'representative': entities[0]['text'],  # Highest frequency
            'total_frequency': sum(e['frequency'] for e in entities),
            'entities': entities
        }


def main():
    """Test the entity clustering system"""
    import sys
    from mnemonic.config import DB_PATH
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = DB_PATH
    
    print(f"\n{'='*70}")
    print("ENTITY CLUSTERING TEST")
    print(f"{'='*70}\n")
    
    print(f"Database: {db_path}\n")
    
    # Initialize clusterer
    print("Initializing clusterer...")
    clusterer = EntityClusterer(db_path, verbose=True)
    print("✓ Clusterer initialized\n")
    
    # Test similarity calculation
    print("Testing Similarity Calculation:")
    print("-" * 70)
    test_pairs = [
        ("Steins Gate", "Steins;Gate"),
        ("Steins Gate", "Steins Gate 0"),
        ("Sarah Chen", "Sarah"),
        ("Sarah Chen", "S. Chen"),
        ("Porsche 911", "911 Turbo"),
        ("Python", "JavaScript")
    ]
    
    for text1, text2 in test_pairs:
        similarity = clusterer.calculate_similarity(text1, text2)
        print(f"{text1:20s} ↔ {text2:20s} = {similarity:.2f}")
    
    print()
    
    # Cluster entities
    print("Clustering entities (threshold: 0.8)...")
    print("-" * 70)
    clusters = clusterer.cluster_entities(threshold=0.8, dry_run=False)
    
    if clusters:
        print(f"\n✓ Found {len(clusters)} clusters:\n")
        
        for cluster in clusters:
            print(f"Cluster {cluster.cluster_id}:")
            print(f"  Representative: {cluster.representative}")
            print(f"  Total frequency: {cluster.total_frequency}")
            print(f"  Avg similarity: {cluster.similarity_score:.2f}")
            print(f"  Entities ({len(cluster.entities)}):")
            for entity in cluster.entities:
                print(f"    - {entity['text']} (freq: {entity['frequency']})")
            print()
    else:
        print("No clusters found (no similar entities)")
    
    # Show stats
    print(f"{'='*70}")
    print("CLUSTERING STATISTICS:")
    stats = clusterer.get_cluster_stats()
    
    print(f"  Total entities: {stats['total_entities']}")
    print(f"  Clustered entities: {stats['clustered_entities']}")
    print(f"  Total clusters: {stats['total_clusters']}")
    print(f"  Avg cluster size: {stats['avg_cluster_size']:.1f}")
    print(f"  Clustering percentage: {stats['clustering_percentage']:.1f}%")
    
    if stats['largest_clusters']:
        print(f"\n  Largest clusters:")
        for cluster in stats['largest_clusters']:
            print(f"    Cluster {cluster['cluster_id']}: {cluster['size']} entities")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()