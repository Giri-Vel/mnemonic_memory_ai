#!/usr/bin/env python3
"""
Daily Knowledge Review - Your Morning Intelligence Briefing

Automatically generates a personalized daily report showing:
- What you learned recently
- Key entities and their relationships
- Learning patterns and gaps
- Suggested focus areas

Usage:
    python daily_review.py <database_path> [--days N] [--format text|json|html]
    
Examples:
    python daily_review.py mnemonic.db
    python daily_review.py mnemonic.db --days 7
    python daily_review.py mnemonic.db --format html > report.html
    
Author: Mnemonic Team
Created: Week 4 Day 5
"""

import sys
import argparse
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict, Counter

# Add mnemonic to path
sys.path.insert(0, str(Path(__file__).parent / 'mnemonic'))

from graph_explorer import GraphExplorer, GraphFilter


class DailyReview:
    """Generate personalized daily knowledge reviews."""
    
    def __init__(self, db_path: str, days: int = 1):
        """
        Initialize the review generator.
        
        Args:
            db_path: Path to database
            days: Number of days to review (default: 1)
        """
        self.db_path = db_path
        self.days = days
        self.explorer = GraphExplorer(db_path)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def _get_recent_memories(self) -> List[Dict]:
        """Get memories from the review period."""
        cursor = self.conn.cursor()
        cutoff = datetime.now() - timedelta(days=self.days)
        
        cursor.execute("""
            SELECT id, content, created_at, category
            FROM memories
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """, (cutoff,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def _get_active_entities(self) -> List[Tuple[str, str, int]]:
        """Get entities mentioned in the review period."""
        cursor = self.conn.cursor()
        cutoff = datetime.now() - timedelta(days=self.days)
        
        cursor.execute("""
            SELECT DISTINCT e.name, e.type, e.frequency
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE m.created_at >= ?
            ORDER BY e.frequency DESC
        """, (cutoff,))
        
        return [(row['name'], row['type'], row['frequency']) for row in cursor.fetchall()]
    
    def _analyze_learning_patterns(self) -> Dict[str, Any]:
        """Analyze what types of things you're learning about."""
        active_entities = self._get_active_entities()
        
        # Count by type
        type_counts = Counter(entity_type for _, entity_type, _ in active_entities)
        
        # Get top entities overall
        top_entities = active_entities[:10]
        
        # Analyze diversity
        unique_entities = len(active_entities)
        total_mentions = sum(freq for _, _, freq in active_entities)
        
        return {
            'type_distribution': dict(type_counts),
            'top_entities': top_entities,
            'unique_entities': unique_entities,
            'total_mentions': total_mentions,
            'diversity_score': unique_entities / max(total_mentions, 1)
        }
    
    def _find_knowledge_gaps(self) -> List[Dict]:
        """Find isolated or weakly connected entities that might need more context."""
        if not self.explorer.graph:
            return []
        
        gaps = []
        
        for entity in self.explorer.graph.nodes():
            degree = self.explorer.graph.degree(entity)
            metadata = self.explorer.entity_metadata.get(entity, {})
            frequency = metadata.get('frequency', 0)
            
            # High frequency but low connectivity = potential gap
            if frequency >= 5 and degree <= 2:
                gaps.append({
                    'entity': entity,
                    'type': metadata.get('type', 'unknown'),
                    'frequency': frequency,
                    'connections': degree,
                    'gap_score': frequency / max(degree, 1)
                })
        
        # Sort by gap score
        gaps.sort(key=lambda x: -x['gap_score'])
        
        return gaps[:5]
    
    def _find_emerging_topics(self) -> List[Dict]:
        """Find entities that are appearing more frequently recently."""
        cursor = self.conn.cursor()
        
        # Get entities from last N days
        recent_cutoff = datetime.now() - timedelta(days=self.days)
        cursor.execute("""
            SELECT e.name, e.type, COUNT(*) as recent_count
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE m.created_at >= ?
            GROUP BY e.name, e.type
        """, (recent_cutoff,))
        recent = {row['name']: row['recent_count'] for row in cursor.fetchall()}
        
        # Get entities from previous period
        older_cutoff = datetime.now() - timedelta(days=self.days * 2)
        cursor.execute("""
            SELECT e.name, e.type, COUNT(*) as older_count
            FROM entities e
            JOIN memories m ON e.memory_id = m.id
            WHERE m.created_at >= ? AND m.created_at < ?
            GROUP BY e.name, e.type
        """, (older_cutoff, recent_cutoff))
        older = {row['name']: row['older_count'] for row in cursor.fetchall()}
        
        # Find emerging topics (more mentions recently than before)
        emerging = []
        for entity, recent_count in recent.items():
            older_count = older.get(entity, 0)
            if recent_count > older_count:
                growth = (recent_count - older_count) / max(older_count, 1)
                emerging.append({
                    'entity': entity,
                    'recent_mentions': recent_count,
                    'previous_mentions': older_count,
                    'growth_rate': growth
                })
        
        emerging.sort(key=lambda x: -x['growth_rate'])
        return emerging[:5]
    
    def _get_key_connections(self) -> List[Dict]:
        """Find the most important connections you're making."""
        if not self.explorer.graph:
            return []
        
        # Get recent active entities
        active_entities = set(entity for entity, _, _ in self._get_active_entities())
        
        # Find connections between them
        connections = []
        for entity in active_entities:
            if entity not in self.explorer.graph:
                continue
            
            neighborhood = self.explorer.get_node_neighborhood(entity, include_metadata=True)
            for neighbor_info in neighborhood.get('neighbors', [])[:3]:
                neighbor = neighbor_info['neighbor']
                if neighbor in active_entities:
                    connections.append({
                        'from': entity,
                        'to': neighbor,
                        'weight': neighbor_info['weight'],
                        'from_type': self.explorer.entity_metadata.get(entity, {}).get('type'),
                        'to_type': neighbor_info['type']
                    })
        
        # Sort by weight
        connections.sort(key=lambda x: -x['weight'])
        
        return connections[:10]
    
    def _get_suggested_focus(self) -> List[str]:
        """Generate suggestions for what to focus on next."""
        suggestions = []
        
        # Suggest exploring knowledge gaps
        gaps = self._find_knowledge_gaps()
        if gaps:
            top_gap = gaps[0]
            suggestions.append(
                f"🔍 Deep dive into '{top_gap['entity']}' - you've mentioned it {top_gap['frequency']} times "
                f"but it has few connections. Understanding its context could be valuable."
            )
        
        # Suggest leveraging emerging topics
        emerging = self._find_emerging_topics()
        if emerging:
            top_emerging = emerging[0]
            suggestions.append(
                f"📈 '{top_emerging['entity']}' is trending in your learning ({top_emerging['growth_rate']:.0%} growth). "
                f"This might be a good area to double down on."
            )
        
        # Suggest connecting islands
        stats = self.explorer.get_graph_statistics()
        if stats.components > 1:
            suggestions.append(
                f"🌉 You have {stats.components} separate knowledge clusters. "
                f"Look for connections between different topics to build a more integrated understanding."
            )
        
        # Suggest reviewing dormant topics
        temporal = self.explorer.detect_temporal_changes(days_ago=self.days)
        if temporal['dormant_entities'] > 0:
            suggestions.append(
                f"💤 {temporal['dormant_entities']} topics haven't been mentioned recently. "
                f"Consider revisiting some older topics to strengthen retention."
            )
        
        return suggestions
    
    def generate_text_report(self) -> str:
        """Generate a text-based report."""
        lines = []
        
        # Header
        period = "today" if self.days == 1 else f"the last {self.days} days"
        lines.append("=" * 70)
        lines.append(f"📊 DAILY KNOWLEDGE REVIEW - {datetime.now().strftime('%Y-%m-%d')}")
        lines.append("=" * 70)
        lines.append(f"\nReviewing your learning from {period}\n")
        
        # Recent memories
        memories = self._get_recent_memories()
        lines.append(f"📝 Recent Activity: {len(memories)} memories captured")
        if memories:
            lines.append("\nMost recent:")
            for mem in memories[:3]:
                content = mem['content'][:100] + "..." if len(mem['content']) > 100 else mem['content']
                lines.append(f"  • {content}")
        lines.append("")
        
        # Learning patterns
        patterns = self._analyze_learning_patterns()
        lines.append(f"🧠 Learning Patterns:")
        lines.append(f"  • Unique entities: {patterns['unique_entities']}")
        lines.append(f"  • Total mentions: {patterns['total_mentions']}")
        lines.append(f"  • Diversity score: {patterns['diversity_score']:.2%}")
        lines.append(f"\n  Topic distribution:")
        for entity_type, count in sorted(patterns['type_distribution'].items(), key=lambda x: -x[1]):
            lines.append(f"    - {entity_type}: {count}")
        lines.append("")
        
        # Top entities
        lines.append(f"⭐ Most Important Entities:")
        for i, (entity, entity_type, freq) in enumerate(patterns['top_entities'][:5], 1):
            lines.append(f"  {i}. {entity} ({entity_type}) - {freq} mentions")
        lines.append("")
        
        # Key connections
        connections = self._get_key_connections()
        if connections:
            lines.append(f"🔗 Key Connections You're Making:")
            for i, conn in enumerate(connections[:5], 1):
                lines.append(
                    f"  {i}. {conn['from']} ↔ {conn['to']} "
                    f"(strength: {conn['weight']})"
                )
            lines.append("")
        
        # Knowledge gaps
        gaps = self._find_knowledge_gaps()
        if gaps:
            lines.append(f"❓ Potential Knowledge Gaps:")
            for i, gap in enumerate(gaps, 1):
                lines.append(
                    f"  {i}. {gap['entity']} - mentioned {gap['frequency']}x "
                    f"but only {gap['connections']} connections"
                )
            lines.append("")
        
        # Emerging topics
        emerging = self._find_emerging_topics()
        if emerging:
            lines.append(f"📈 Emerging Topics:")
            for i, topic in enumerate(emerging, 1):
                lines.append(
                    f"  {i}. {topic['entity']} - "
                    f"{topic['growth_rate']:.0%} growth "
                    f"({topic['recent_mentions']} vs {topic['previous_mentions']})"
                )
            lines.append("")
        
        # Graph statistics
        stats = self.explorer.get_graph_statistics()
        lines.append(f"📊 Knowledge Graph Statistics:")
        lines.append(f"  • Total entities: {stats.node_count}")
        lines.append(f"  • Connections: {stats.edge_count}")
        lines.append(f"  • Density: {stats.density:.4f}")
        lines.append(f"  • Communities: {stats.components}")
        lines.append("")
        
        # Suggestions
        suggestions = self._get_suggested_focus()
        if suggestions:
            lines.append(f"💡 Suggested Focus Areas:")
            for i, suggestion in enumerate(suggestions, 1):
                lines.append(f"  {i}. {suggestion}")
            lines.append("")
        
        # Footer
        lines.append("=" * 70)
        lines.append(f"Generated at {datetime.now().strftime('%H:%M:%S')}")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> str:
        """Generate a JSON report."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'period_days': self.days,
            'memories': self._get_recent_memories(),
            'learning_patterns': self._analyze_learning_patterns(),
            'knowledge_gaps': self._find_knowledge_gaps(),
            'emerging_topics': self._find_emerging_topics(),
            'key_connections': self._get_key_connections(),
            'graph_statistics': {
                'nodes': self.explorer.graph.number_of_nodes() if self.explorer.graph else 0,
                'edges': self.explorer.graph.number_of_edges() if self.explorer.graph else 0,
            },
            'suggestions': self._get_suggested_focus()
        }
        return json.dumps(report, indent=2, default=str)
    
    def generate_html_report(self) -> str:
        """Generate an HTML report."""
        patterns = self._analyze_learning_patterns()
        gaps = self._find_knowledge_gaps()
        emerging = self._find_emerging_topics()
        connections = self._get_key_connections()
        suggestions = self._get_suggested_focus()
        stats = self.explorer.get_graph_statistics()
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Knowledge Review - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 2em;
        }}
        .header .date {{
            opacity: 0.9;
            margin-top: 5px;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            margin-top: 0;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .metric {{
            display: inline-block;
            background: #f0f0f0;
            padding: 10px 15px;
            margin: 5px;
            border-radius: 5px;
        }}
        .metric .value {{
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }}
        .metric .label {{
            font-size: 0.9em;
            color: #666;
        }}
        .entity {{
            display: inline-block;
            background: #e8eaf6;
            padding: 5px 10px;
            margin: 3px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        .gap {{
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 10px;
            margin: 10px 0;
        }}
        .emerging {{
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 10px;
            margin: 10px 0;
        }}
        .suggestion {{
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 10px;
            margin: 10px 0;
        }}
        .connection {{
            display: flex;
            align-items: center;
            padding: 8px;
            margin: 5px 0;
            background: #fafafa;
            border-radius: 4px;
        }}
        .connection .arrow {{
            margin: 0 10px;
            color: #999;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Daily Knowledge Review</h1>
        <div class="date">{datetime.now().strftime('%A, %B %d, %Y')}</div>
    </div>
    
    <div class="section">
        <h2>📈 Learning Overview</h2>
        <div class="metric">
            <div class="value">{patterns['unique_entities']}</div>
            <div class="label">Unique Entities</div>
        </div>
        <div class="metric">
            <div class="value">{patterns['total_mentions']}</div>
            <div class="label">Total Mentions</div>
        </div>
        <div class="metric">
            <div class="value">{patterns['diversity_score']:.0%}</div>
            <div class="label">Diversity Score</div>
        </div>
        <div class="metric">
            <div class="value">{stats.node_count}</div>
            <div class="label">Graph Nodes</div>
        </div>
        <div class="metric">
            <div class="value">{stats.edge_count}</div>
            <div class="label">Connections</div>
        </div>
    </div>
    
    <div class="section">
        <h2>⭐ Top Entities</h2>
        {''.join(f'<div class="entity"><strong>{entity}</strong> ({entity_type}) - {freq}x</div>' 
                 for entity, entity_type, freq in patterns['top_entities'][:10])}
    </div>
    
    {f'''<div class="section">
        <h2>❓ Knowledge Gaps</h2>
        {''.join(f'<div class="gap"><strong>{gap["entity"]}</strong> - {gap["frequency"]} mentions but only {gap["connections"]} connections</div>' for gap in gaps)}
    </div>''' if gaps else ''}
    
    {f'''<div class="section">
        <h2>📈 Emerging Topics</h2>
        {''.join(f'<div class="emerging"><strong>{topic["entity"]}</strong> - {topic["growth_rate"]:.0%} growth ({topic["recent_mentions"]} vs {topic["previous_mentions"]})</div>' for topic in emerging)}
    </div>''' if emerging else ''}
    
    {f'''<div class="section">
        <h2>🔗 Key Connections</h2>
        {''.join(f'<div class="connection"><strong>{conn["from"]}</strong><span class="arrow">↔</span><strong>{conn["to"]}</strong> (strength: {conn["weight"]})</div>' for conn in connections[:5])}
    </div>''' if connections else ''}
    
    {f'''<div class="section">
        <h2>💡 Suggested Focus</h2>
        {''.join(f'<div class="suggestion">{suggestion}</div>' for suggestion in suggestions)}
    </div>''' if suggestions else ''}
    
    <div class="section" style="text-align: center; color: #999; font-size: 0.9em;">
        Generated at {datetime.now().strftime('%H:%M:%S')}
    </div>
</body>
</html>"""
        return html


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate daily knowledge review',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python daily_review.py mnemonic.db
  python daily_review.py mnemonic.db --days 7
  python daily_review.py mnemonic.db --format html > report.html
  python daily_review.py mnemonic.db --format json | jq .
        """
    )
    parser.add_argument('database', help='Path to database file')
    parser.add_argument(
        '--days',
        type=int,
        default=1,
        help='Number of days to review (default: 1)'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json', 'html'],
        default='text',
        help='Output format (default: text)'
    )
    
    args = parser.parse_args()
    
    # Generate review
    review = DailyReview(args.database, args.days)
    
    if args.format == 'json':
        print(review.generate_json_report())
    elif args.format == 'html':
        print(review.generate_html_report())
    else:
        print(review.generate_text_report())


if __name__ == '__main__':
    main()