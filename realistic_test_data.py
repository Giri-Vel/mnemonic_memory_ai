"""
Realistic Test Data Generator for Mnemonic

Creates realistic memories, entities, and relationships for testing.
Simulates real-world usage patterns with:
- Diverse topics and entity types
- Temporal patterns (older and recent memories)
- Realistic co-occurrence patterns
- Community structures

Usage:
    python realistic_test_data.py output.db [--size small|medium|large]
    
Author: Mnemonic Team
Created: Week 4 Day 5
"""

import sqlite3
import argparse
from datetime import datetime, timedelta
import random
import json
from typing import List, Tuple, Dict, Set
from collections import defaultdict


class RealisticDataGenerator:
    """Generate realistic test data for Mnemonic."""
    
    # Realistic memory templates by category
    MEMORY_TEMPLATES = {
        'learning': [
            "Today I learned about {concept} in {domain}. It's fascinating how {detail}.",
            "Read a great article about {concept}. Key takeaways: {detail}.",
            "Attended a {domain} workshop on {concept}. The instructor explained {detail}.",
            "Working through {concept} tutorial. {detail} was particularly interesting.",
            "Deep dive into {concept} today. Understanding {detail} is crucial.",
        ],
        'work': [
            "Team meeting about {concept}. We discussed {detail} and decided to {action}.",
            "Code review for {concept} implementation. {detail} needs improvement.",
            "Sprint planning - prioritizing {concept}. Team wants to {action}.",
            "Bug in {concept} module. Root cause: {detail}. Will {action}.",
            "Performance optimization for {concept}. {detail} showed significant gains.",
        ],
        'personal': [
            "Thinking about {concept} and how it relates to {domain}. {detail}.",
            "Conversation with {person} about {concept}. They mentioned {detail}.",
            "Reflection: {concept} is important because {detail}.",
            "Goal: Learn more about {concept}. Plan: {action}.",
            "Interesting connection between {concept} and {domain}. {detail}.",
        ],
        'technical': [
            "Exploring {concept} in {language}. {detail} is the key pattern.",
            "Refactoring {concept} to use {technology}. {detail} improves maintainability.",
            "Debugging {concept} issue. Found that {detail} was the problem.",
            "Implemented {concept} using {technology}. {detail} works well.",
            "Architecture decision: Using {concept} because {detail}.",
        ]
    }
    
    # Entity pools by type
    CONCEPTS = [
        'machine learning', 'neural networks', 'transformers', 'attention mechanism',
        'backpropagation', 'gradient descent', 'embeddings', 'tokenization',
        'fine-tuning', 'transfer learning', 'reinforcement learning', 'GANs',
        'distributed systems', 'microservices', 'containerization', 'kubernetes',
        'database indexing', 'query optimization', 'caching strategies', 'load balancing',
        'API design', 'REST', 'GraphQL', 'websockets', 'authentication',
        'encryption', 'hashing', 'certificates', 'OAuth', 'JWT',
        'agile methodology', 'sprint planning', 'retrospectives', 'code review',
        'test-driven development', 'CI/CD', 'deployment', 'monitoring'
    ]
    
    DOMAINS = [
        'AI/ML', 'backend engineering', 'frontend development', 'DevOps',
        'data science', 'computer vision', 'NLP', 'distributed systems',
        'web development', 'mobile development', 'cloud architecture', 'security',
        'system design', 'databases', 'networking', 'algorithms'
    ]
    
    TECHNOLOGIES = [
        'Python', 'JavaScript', 'TypeScript', 'Go', 'Rust',
        'React', 'Vue', 'Angular', 'Node.js', 'Django',
        'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch',
        'Docker', 'Kubernetes', 'AWS', 'GCP', 'Azure',
        'PyTorch', 'TensorFlow', 'scikit-learn', 'pandas'
    ]
    
    LANGUAGES = [
        'Python', 'JavaScript', 'Java', 'C++', 'Go',
        'Rust', 'TypeScript', 'Swift', 'Kotlin', 'Ruby'
    ]
    
    PEOPLE = [
        'Alice', 'Bob', 'Carol', 'Dave', 'Eve',
        'Frank', 'Grace', 'Henry', 'Iris', 'Jack'
    ]
    
    DETAILS = [
        'the underlying principles are elegant',
        'it solves the scalability problem',
        'performance improves by 50%',
        'it integrates well with existing systems',
        'the API is intuitive',
        'it handles edge cases gracefully',
        'the documentation is excellent',
        'it reduces complexity significantly',
        'the learning curve is manageable',
        'it follows best practices'
    ]
    
    ACTIONS = [
        'implement it next sprint',
        'prototype it first',
        'research alternatives',
        'write documentation',
        'create a proof of concept',
        'discuss with the team',
        'schedule a deep dive',
        'add it to the roadmap'
    ]
    
    def __init__(self, db_path: str, size: str = 'medium'):
        """
        Initialize the generator.
        
        Args:
            db_path: Path to SQLite database
            size: 'small' (100 memories), 'medium' (500), 'large' (2000)
        """
        self.db_path = db_path
        self.size_config = {
            'small': 100,
            'medium': 500,
            'large': 2000
        }
        self.num_memories = self.size_config.get(size, 500)
        self.conn = None
    
    def _create_schema(self) -> None:
        """Create database schema."""
        cursor = self.conn.cursor()
        
        # Memories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category TEXT,
                metadata TEXT
            )
        """)
        
        # Entities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                community_id INTEGER,
                centrality REAL DEFAULT 0.0,
                memory_id INTEGER,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, type)
            )
        """)
        
        # Relationships table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity1_id INTEGER NOT NULL,
                entity2_id INTEGER NOT NULL,
                co_occurrence INTEGER DEFAULT 1,
                relationship_type TEXT DEFAULT 'co-occurs',
                FOREIGN KEY (entity1_id) REFERENCES entities(id),
                FOREIGN KEY (entity2_id) REFERENCES entities(id),
                UNIQUE(entity1_id, entity2_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at)")
        
        self.conn.commit()
    
    def _generate_memory(self, days_ago: int, category: str) -> Tuple[str, str]:
        """
        Generate a realistic memory.
        
        Args:
            days_ago: How many days ago this memory was created
            category: Memory category
            
        Returns:
            (content, created_at) tuple
        """
        template = random.choice(self.MEMORY_TEMPLATES[category])
        
        # Fill in template variables
        content = template.format(
            concept=random.choice(self.CONCEPTS),
            domain=random.choice(self.DOMAINS),
            technology=random.choice(self.TECHNOLOGIES),
            language=random.choice(self.LANGUAGES),
            person=random.choice(self.PEOPLE),
            detail=random.choice(self.DETAILS),
            action=random.choice(self.ACTIONS)
        )
        
        # Calculate timestamp
        created_at = datetime.now() - timedelta(days=days_ago)
        
        return content, created_at.isoformat()
    
    def _extract_entities_from_memory(self, content: str) -> Dict[str, List[str]]:
        """
        Simple entity extraction from memory content.
        
        Args:
            content: Memory content
            
        Returns:
            Dictionary mapping entity type to list of entities
        """
        entities = defaultdict(list)
        
        # Extract concepts
        for concept in self.CONCEPTS:
            if concept.lower() in content.lower():
                entities['CONCEPT'].append(concept)
        
        # Extract technologies
        for tech in self.TECHNOLOGIES:
            if tech in content:
                entities['TECHNOLOGY'].append(tech)
        
        # Extract languages
        for lang in self.LANGUAGES:
            if lang in content:
                entities['LANGUAGE'].append(lang)
        
        # Extract domains
        for domain in self.DOMAINS:
            if domain in content:
                entities['DOMAIN'].append(domain)
        
        # Extract people
        for person in self.PEOPLE:
            if person in content:
                entities['PERSON'].append(person)
        
        return entities
    
    def _store_entity(self, name: str, entity_type: str, memory_id: int) -> int:
        """
        Store or update an entity.
        
        Args:
            name: Entity name
            entity_type: Entity type
            memory_id: ID of memory containing this entity
            
        Returns:
            Entity ID
        """
        cursor = self.conn.cursor()
        
        # Try to insert, update if exists
        cursor.execute("""
            INSERT INTO entities (name, type, frequency, memory_id, last_seen)
            VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(name, type) DO UPDATE SET
                frequency = frequency + 1,
                last_seen = CURRENT_TIMESTAMP
        """, (name, entity_type, memory_id))
        
        # Get entity ID
        cursor.execute("""
            SELECT id FROM entities WHERE name = ? AND type = ?
        """, (name, entity_type))
        
        return cursor.fetchone()[0]
    
    def _store_relationship(self, entity1_id: int, entity2_id: int) -> None:
        """
        Store or update a relationship between entities.
        
        Args:
            entity1_id: First entity ID
            entity2_id: Second entity ID
        """
        cursor = self.conn.cursor()
        
        # Ensure entity1_id < entity2_id for consistency
        if entity1_id > entity2_id:
            entity1_id, entity2_id = entity2_id, entity1_id
        
        cursor.execute("""
            INSERT INTO relationships (entity1_id, entity2_id, co_occurrence)
            VALUES (?, ?, 1)
            ON CONFLICT(entity1_id, entity2_id) DO UPDATE SET
                co_occurrence = co_occurrence + 1
        """, (entity1_id, entity2_id))
    
    def _calculate_communities(self) -> None:
        """Calculate community IDs using simple clustering."""
        cursor = self.conn.cursor()
        
        # Get all entities with their relationships
        cursor.execute("""
            SELECT DISTINCT e.id, e.type
            FROM entities e
        """)
        entities = cursor.fetchall()
        
        # Simple community assignment based on type and frequency
        for entity_id, entity_type in entities:
            # Assign community based on type hash
            community_id = hash(entity_type) % 10
            
            cursor.execute("""
                UPDATE entities
                SET community_id = ?
                WHERE id = ?
            """, (community_id, entity_id))
        
        self.conn.commit()
    
    def _calculate_centrality(self) -> None:
        """Calculate centrality scores based on relationships."""
        cursor = self.conn.cursor()
        
        # Get degree for each entity
        cursor.execute("""
            SELECT e.id, COUNT(DISTINCT r.id) as degree
            FROM entities e
            LEFT JOIN relationships r ON (e.id = r.entity1_id OR e.id = r.entity2_id)
            GROUP BY e.id
        """)
        
        degrees = cursor.fetchall()
        
        # Normalize centrality scores
        max_degree = max((d[1] for d in degrees), default=1)
        
        for entity_id, degree in degrees:
            centrality = degree / max_degree if max_degree > 0 else 0.0
            
            cursor.execute("""
                UPDATE entities
                SET centrality = ?
                WHERE id = ?
            """, (centrality, entity_id))
        
        self.conn.commit()
    
    def generate(self) -> Dict[str, int]:
        """
        Generate the complete test dataset.
        
        Returns:
            Statistics about generated data
        """
        self.conn = sqlite3.connect(self.db_path)
        
        try:
            self._create_schema()
            
            print(f"Generating {self.num_memories} realistic memories...")
            
            categories = list(self.MEMORY_TEMPLATES.keys())
            entity_ids_by_memory = []
            
            # Generate memories with temporal distribution
            for i in range(self.num_memories):
                # More recent memories are more likely
                if random.random() < 0.5:
                    days_ago = random.randint(0, 30)  # Last month
                elif random.random() < 0.8:
                    days_ago = random.randint(31, 90)  # Last 3 months
                else:
                    days_ago = random.randint(91, 365)  # Last year
                
                category = random.choice(categories)
                content, created_at = self._generate_memory(days_ago, category)
                
                # Store memory
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO memories (content, created_at, category)
                    VALUES (?, ?, ?)
                """, (content, created_at, category))
                memory_id = cursor.lastrowid
                
                # Extract and store entities
                entities = self._extract_entities_from_memory(content)
                entity_ids = []
                
                for entity_type, entity_names in entities.items():
                    for entity_name in entity_names:
                        entity_id = self._store_entity(entity_name, entity_type, memory_id)
                        entity_ids.append(entity_id)
                
                entity_ids_by_memory.append(entity_ids)
                
                # Store relationships (all entities in same memory are related)
                for j in range(len(entity_ids)):
                    for k in range(j + 1, len(entity_ids)):
                        self._store_relationship(entity_ids[j], entity_ids[k])
                
                if (i + 1) % 100 == 0:
                    print(f"  Generated {i + 1}/{self.num_memories} memories...")
                    self.conn.commit()
            
            self.conn.commit()
            
            print("Calculating communities...")
            self._calculate_communities()
            
            print("Calculating centrality scores...")
            self._calculate_centrality()
            
            # Get statistics
            cursor = self.conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM memories")
            num_memories = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM entities")
            num_entities = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM relationships")
            num_relationships = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT type) FROM entities")
            num_types = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT community_id) FROM entities")
            num_communities = cursor.fetchone()[0]
            
            stats = {
                'memories': num_memories,
                'entities': num_entities,
                'relationships': num_relationships,
                'entity_types': num_types,
                'communities': num_communities
            }
            
            print("\n✅ Test data generated successfully!")
            print(f"   Memories: {stats['memories']}")
            print(f"   Entities: {stats['entities']}")
            print(f"   Relationships: {stats['relationships']}")
            print(f"   Entity Types: {stats['entity_types']}")
            print(f"   Communities: {stats['communities']}")
            
            return stats
            
        finally:
            if self.conn:
                self.conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate realistic test data for Mnemonic'
    )
    parser.add_argument(
        'database',
        help='Path to output database file'
    )
    parser.add_argument(
        '--size',
        choices=['small', 'medium', 'large'],
        default='medium',
        help='Dataset size (small=100, medium=500, large=2000 memories)'
    )
    
    args = parser.parse_args()
    
    generator = RealisticDataGenerator(args.database, args.size)
    generator.generate()


if __name__ == '__main__':
    main()