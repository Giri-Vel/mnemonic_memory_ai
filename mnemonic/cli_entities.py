"""
CLI Commands for Entity Type Management + Timeline Analysis

Commands:
- mnemonic entities suggest
- mnemonic entities add-type <n>
- mnemonic entities remove-type <n>
- mnemonic entities list-types
- mnemonic entities status
- mnemonic entities reextract --worker
- mnemonic entities rediscover
- mnemonic entities cluster
- mnemonic timeline trending         # NEW: Week 4 Day 3
- mnemonic timeline dormant           # NEW: Week 4 Day 3
- mnemonic timeline show <entity>     # NEW: Week 4 Day 3
- mnemonic timeline summary           # NEW: Week 4 Day 3
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from pathlib import Path

console = Console()


def get_db_path():
    """Get the database path"""
    from mnemonic.config import DB_PATH
    return DB_PATH


@click.group(name='entities')
def entities_group():
    """Manage entity types and extraction"""
    pass


# ============================================================================
# ENTITY TYPE MANAGEMENT COMMANDS (existing)
# ============================================================================

@entities_group.command(name='suggest')
@click.option('--limit', '-n', default=10, help='Number of suggestions to show')
def suggest_entities(limit):
    """Suggest new entity types based on patterns in your memories"""
    try:
        from mnemonic.entity_type_manager import EntityTypeManager
        
        db_path = get_db_path()
        
        if not Path(db_path).exists():
            console.print("[yellow]⚠[/yellow] Database not found. Have you stored any memories yet?")
            console.print(f"[dim]Expected: {db_path}[/dim]\n")
            return
        
        manager = EntityTypeManager(db_path)
        suggestions = manager.suggest_entity_types()[:limit]
        
        if not suggestions:
            console.print("[yellow]No entity type suggestions found.[/yellow]")
            console.print("\n[dim]Suggestions appear when:\n"
                        "  • Tags appear on 5+ memories\n"
                        "  • Noun phrases appear 3+ times\n"
                        "\n"
                        "Add more memories to get suggestions![/dim]\n")
            return
        
        table = Table(
            title=f"🔍 Suggested Entity Types",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Type Name", style="bold green", width=20)
        table.add_column("Source", style="cyan", width=12)
        table.add_column("Count", style="yellow", width=8)
        table.add_column("Examples", style="white", width=40)
        
        for i, suggestion in enumerate(suggestions, 1):
            examples_str = ", ".join(suggestion.examples[:2])
            if len(examples_str) > 40:
                examples_str = examples_str[:37] + "..."
            
            table.add_row(
                str(i),
                suggestion.type_name,
                suggestion.source,
                str(suggestion.occurrence_count),
                examples_str
            )
        
        console.print(table)
        console.print(f"\n[dim]💡 To add a type: [bold]mnemonic entities add-type <name>[/bold][/dim]\n")
        
    except ImportError as e:
        console.print(f"[red]✗ Error: Required module not found[/red]")
        console.print(f"[dim]Have you run migration M003? {e}[/dim]")
    except Exception as e:
        console.print(f"[red]✗ Error getting suggestions: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@entities_group.command(name='add-type')
@click.argument('type_name')
def add_entity_type(type_name):
    """Add a new entity type"""
    try:
        from mnemonic.entity_type_manager import EntityTypeManager
        
        db_path = get_db_path()
        
        if not Path(db_path).exists():
            console.print("[red]✗ Database not found. Store some memories first![/red]")
            return
        
        manager = EntityTypeManager(db_path)
        
        console.print(f"Adding entity type '[bold]{type_name}[/bold]'...")
        
        success = manager.add_entity_type(type_name)
        
        if success:
            console.print(f"[green]✓[/green] Added entity type '[bold]{type_name}[/bold]'")
            console.print("[dim]⚙ Re-extraction queued (processing in background)[/dim]")
            console.print(f"[dim]💡 Check status with: [bold]mnemonic entities status[/bold][/dim]")
            console.print(f"[dim]💡 Run worker with: [bold]mnemonic entities reextract --worker[/bold][/dim]\n")
        else:
            console.print(f"[yellow]⚠[/yellow] Entity type '[bold]{type_name}[/bold]' already exists")
        
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
    except Exception as e:
        console.print(f"[red]✗ Error adding entity type: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@entities_group.command(name='remove-type')
@click.argument('type_name')
@click.option('--force', '-f', is_flag=True, help='Force removal even if used in memories')
def remove_entity_type(type_name, force):
    """Remove an entity type"""
    try:
        from mnemonic.entity_type_manager import EntityTypeManager
        
        db_path = get_db_path()
        manager = EntityTypeManager(db_path)
        
        success, message = manager.remove_entity_type(type_name, force=force)
        
        if success:
            console.print(f"[green]✓[/green] Removed entity type '[bold]{type_name}[/bold]'")
            if message:
                console.print(f"[yellow]⚠[/yellow] {message}")
        else:
            console.print(f"[red]✗ {message}[/red]")
            if message and "Use force=True" in message:
                console.print(f"[dim]💡 Add --force to remove anyway[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗ Error removing entity type: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@entities_group.command(name='list-types')
def list_entity_types():
    """List all entity types (core + user-defined)"""
    try:
        from mnemonic.entity_type_manager import EntityTypeManager
        
        db_path = get_db_path()
        
        if not Path(db_path).exists():
            console.print("[yellow]⚠[/yellow] Database not found. Store some memories first!")
            return
        
        manager = EntityTypeManager(db_path)
        
        types = manager.list_entity_types()
        
        # Core types panel
        core_text = ""
        for et in types['core']:
            core_text += f"  • [bold]{et.type_name}[/bold] ({et.entity_count} entities)\n"
        
        core_panel = Panel(
            core_text.strip() if core_text else "[dim]No core entities found yet[/dim]",
            title="🔷 Core Entity Types",
            border_style="cyan",
            box=box.ROUNDED
        )
        console.print(core_panel)
        
        # User-defined types panel
        if types['user_defined']:
            user_text = ""
            for et in types['user_defined']:
                examples = ", ".join(et.examples[:2]) if et.examples else "(no examples yet)"
                user_text += f"  • [bold green]{et.type_name}[/bold green]\n"
                user_text += f"    {et.entity_count} entities, {et.memory_count} memories\n"
                user_text += f"    Examples: [dim]{examples}[/dim]\n\n"
            
            user_panel = Panel(
                user_text.strip(),
                title=f"🟢 User-Defined Types ({len(types['user_defined'])})",
                border_style="green",
                box=box.ROUNDED
            )
            console.print(user_panel)
        else:
            console.print("\n[dim]No user-defined entity types yet.[/dim]")
            console.print("[dim]💡 Add types with: [bold]mnemonic entities add-type <name>[/bold][/dim]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Error listing entity types: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@entities_group.command(name='status')
@click.option('--recent', '-r', default=10, help='Number of recent jobs to show')
def show_extraction_status(recent):
    """Show re-extraction queue status"""
    try:
        from mnemonic.reextraction_queue import ReextractionQueue
        
        db_path = get_db_path()
        
        if not Path(db_path).exists():
            console.print("[yellow]⚠[/yellow] Database not found. Store some memories first!")
            return
        
        queue = ReextractionQueue(db_path)
        
        # Queue overview
        status = queue.get_queue_status()
        total = sum(status.values())
        
        overview_text = f"""
[cyan]Total Jobs:[/cyan] {total}
[yellow]Pending:[/yellow] {status['pending']}
[blue]Processing:[/blue] {status['processing']}
[green]Completed:[/green] {status['completed']}
[red]Failed:[/red] {status['failed']}
        """
        
        panel = Panel(
            overview_text.strip(),
            title="📊 Re-extraction Queue Status",
            border_style="cyan",
            box=box.DOUBLE
        )
        console.print(panel)
        
        # Recent jobs
        jobs = queue.get_recent_jobs(limit=recent)
        
        if jobs:
            console.print(f"\n[bold]Recent Jobs:[/bold]\n")
            
            table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
            table.add_column("ID", style="dim", width=5)
            table.add_column("Type", style="cyan", width=15)
            table.add_column("Status", width=12)
            table.add_column("Progress", width=15)
            table.add_column("Entities", style="green", width=10)
            
            for job in jobs:
                status_colored = {
                    'pending': f"[yellow]{job.status}[/yellow]",
                    'processing': f"[blue]{job.status}[/blue]",
                    'completed': f"[green]{job.status}[/green]",
                    'failed': f"[red]{job.status}[/red]"
                }.get(job.status, job.status)
                
                if job.status == 'processing' and job.memories_total > 0:
                    progress_pct = job.progress_percent
                    progress_str = f"{progress_pct:.0f}% ({job.memories_processed}/{job.memories_total})"
                elif job.status == 'completed':
                    progress_str = "100%"
                else:
                    progress_str = "-"
                
                entities_str = str(job.entities_found) if job.entities_found > 0 else "-"
                
                table.add_row(
                    str(job.id),
                    job.type_name,
                    status_colored,
                    progress_str,
                    entities_str
                )
            
            console.print(table)
            
            if status['pending'] > 0:
                console.print(f"\n[dim]💡 Process pending jobs with: [bold]mnemonic entities reextract --worker[/bold][/dim]")
        else:
            console.print("\n[dim]No re-extraction jobs yet.[/dim]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Error getting status: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@entities_group.command(name='rediscover')
@click.option('--days', '-d', default=90, help='Days since last mention')
def rediscover_entities(days):
    """Discover entities you haven't mentioned recently"""
    from mnemonic.entity_type_manager import EntityTypeManager
    from mnemonic.config import DB_PATH
    
    manager = EntityTypeManager(DB_PATH)
    suggestions = manager.get_rediscovery_suggestions(days_ago=days, limit=5)
    
    if not suggestions:
        console.print("[yellow]No rediscovery suggestions found[/yellow]")
        console.print("\n[dim](You need entities with frequency >= 3 not seen in 90+ days)[/dim]\n")
        return
    
    console.print(f"\n💭 [bold]Remember These?[/bold] (not mentioned in {days}+ days)\n")
    
    for item in suggestions:
        console.print(f"• [cyan]{item['text']}[/cyan]")
        console.print(f"  Mentioned {item['frequency']} times")
        console.print(f"  Last seen: {item['last_mention']} ({item['days_ago']} days ago)\n")


@entities_group.command(name='reextract')
@click.option('--worker', is_flag=True, help='Run as background worker')
@click.option('--max-jobs', '-n', type=int, help='Maximum jobs to process')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def run_reextraction(worker, max_jobs, verbose):
    """Run background re-extraction worker"""
    try:
        from mnemonic.reextraction_worker import ReextractionWorker
        from mnemonic.config import DB_PATH
        
        if not Path(DB_PATH).exists():
            console.print("[red]✗ Database not found. Store some memories first![/red]")
            return
        
        console.print("\n[bold]Background Re-extraction Worker[/bold]")
        console.print("-" * 70)
        
        console.print("Initializing worker...")
        worker_instance = ReextractionWorker(DB_PATH, verbose=verbose)
        console.print("[green]✓[/green] Worker initialized\n")
        
        stats = worker_instance.get_worker_stats()
        queue_status = stats['queue_status']
        
        console.print("Queue Status:")
        console.print(f"  [yellow]Pending:[/yellow] {queue_status['pending']}")
        console.print(f"  [blue]Processing:[/blue] {queue_status['processing']}")
        console.print(f"  [green]Completed:[/green] {queue_status['completed']}")
        console.print(f"  [red]Failed:[/red] {queue_status['failed']}")
        
        if queue_status['pending'] == 0:
            console.print("\n[dim]No pending jobs to process.[/dim]\n")
            return
        
        console.print(f"\n[bold]Processing {queue_status['pending']} pending job(s)...[/bold]\n")
        
        results = worker_instance.process_pending_jobs(max_jobs=max_jobs)
        
        console.print("\n" + "-" * 70)
        console.print("[bold]Processing Complete[/bold]")
        console.print(f"  Processed: {results['processed']}")
        console.print(f"  [green]Succeeded: {results['succeeded']}[/green]")
        console.print(f"  [red]Failed: {results['failed']}[/red]")
        console.print()
        
    except ImportError as e:
        console.print("[red]✗ Error: Required module not found[/red]")
        console.print(f"[dim]GLiNER may not be installed: {e}[/dim]")
    except Exception as e:
        console.print(f"[red]✗ Error running worker: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@entities_group.command(name='cluster')
@click.option('--threshold', '-t', type=float, default=0.8, help='Similarity threshold (0.0-1.0)')
@click.option('--type', 'entity_type', help='Only cluster entities of this type')
@click.option('--dry-run', is_flag=True, help='Preview clusters without updating database')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cluster_entities(threshold, entity_type, dry_run, verbose):
    """Cluster similar entities using fuzzy matching"""
    try:
        from mnemonic.entity_clustering import EntityClusterer
        from mnemonic.config import DB_PATH
        
        if not Path(DB_PATH).exists():
            console.print("[red]✗ Database not found. Store some memories first![/red]")
            return
        
        console.print("\n[bold]Entity Clustering[/bold]")
        console.print("-" * 70)
        console.print(f"Similarity threshold: {threshold:.0%}")
        if entity_type:
            console.print(f"Entity type filter: {entity_type}")
        if dry_run:
            console.print("[yellow]DRY RUN MODE (no database changes)[/yellow]")
        console.print()
        
        console.print("Initializing clusterer...")
        clusterer = EntityClusterer(DB_PATH, verbose=verbose)
        console.print("[green]✓[/green] Clusterer initialized\n")
        
        console.print("Clustering entities...")
        clusters = clusterer.cluster_entities(
            threshold=threshold,
            entity_type=entity_type,
            dry_run=dry_run
        )
        
        if not clusters:
            console.print("\n[yellow]No clusters found.[/yellow]")
            console.print("[dim]Try lowering the threshold or add more similar entities.[/dim]\n")
            return
        
        console.print(f"\n[green]✓[/green] Found {len(clusters)} cluster(s)\n")
        
        for cluster in clusters[:10]:
            console.print(f"[bold cyan]Cluster {cluster.cluster_id}[/bold cyan]")
            console.print(f"  Representative: [green]{cluster.representative}[/green]")
            console.print(f"  Total frequency: {cluster.total_frequency}")
            console.print(f"  Similarity: {cluster.similarity_score:.0%}")
            console.print(f"  Entities ({len(cluster.entities)}):")
            for entity in cluster.entities[:5]:
                console.print(f"    • {entity['text']} (freq: {entity['frequency']})")
            if len(cluster.entities) > 5:
                console.print(f"    ... and {len(cluster.entities) - 5} more")
            console.print()
        
        if len(clusters) > 10:
            console.print(f"[dim]... and {len(clusters) - 10} more clusters[/dim]\n")
        
        stats = clusterer.get_cluster_stats()
        
        console.print("-" * 70)
        console.print("[bold]Clustering Statistics[/bold]")
        console.print(f"  Total entities: {stats['total_entities']}")
        console.print(f"  Clustered: {stats['clustered_entities']} ({stats['clustering_percentage']:.1f}%)")
        console.print(f"  Total clusters: {stats['total_clusters']}")
        console.print(f"  Avg cluster size: {stats['avg_cluster_size']:.1f}")
        
        if not dry_run:
            console.print("\n[green]✓[/green] Database updated with cluster assignments")
        
        console.print()
        
    except Exception as e:
        console.print(f"[red]✗ Error clustering entities: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


# ============================================================================
# TIMELINE ANALYSIS COMMANDS (NEW - Week 4 Day 3)
# ============================================================================

@entities_group.command(name='timeline-trending')
@click.option('--limit', '-n', default=10, help='Number of entities to show')
@click.option('--trend', '-t', help='Filter by trend type (increasing/burst/stable/declining/dormant)')
def timeline_trending(limit, trend):
    """Show trending entities based on activity score"""
    try:
        from mnemonic.entity_timeline import EntityTimelineAnalyzer
        from mnemonic.config import DB_PATH
        
        if not Path(DB_PATH).exists():
            console.print("[red]✗ Database not found. Store some memories first![/red]")
            return
        
        console.print(f"\n📈 [bold]Trending Entities[/bold]")
        if trend:
            console.print(f"   Filter: {trend}")
        console.print()
        
        analyzer = EntityTimelineAnalyzer(DB_PATH)
        trending = analyzer.get_trending_entities(limit=limit, trend_type=trend)
        
        if not trending:
            console.print("[yellow]No trending entities found.[/yellow]\n")
            return
        
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("Rank", style="dim", width=4)
        table.add_column("Entity", style="bold green", width=25)
        table.add_column("Type", style="cyan", width=15)
        table.add_column("Trend", width=12)
        table.add_column("Activity", style="yellow", width=10)
        table.add_column("Frequency", style="white", width=10)
        
        for i, timeline in enumerate(trending, 1):
            emoji = analyzer._trend_emoji(timeline.trend)
            trend_str = f"{emoji} {timeline.trend}"
            activity_str = f"{timeline.activity_score:.0f}/100"
            
            table.add_row(
                str(i),
                timeline.entity_text,
                timeline.entity_type or "untyped",
                trend_str,
                activity_str,
                str(timeline.frequency)
            )
        
        console.print(table)
        console.print(f"\n[dim]💡 View timeline: [bold]mnemonic entities timeline-show <entity>[/bold][/dim]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Error getting trending entities: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@entities_group.command(name='timeline-dormant')
@click.option('--limit', '-n', default=10, help='Number of entities to show')
@click.option('--days', '-d', default=90, help='Minimum days since last mention')
def timeline_dormant(limit, days):
    """Find dormant entities (rediscovery suggestions)"""
    try:
        from mnemonic.entity_timeline import EntityTimelineAnalyzer
        from mnemonic.config import DB_PATH
        
        if not Path(DB_PATH).exists():
            console.print("[red]✗ Database not found. Store some memories first![/red]")
            return
        
        console.print(f"\n💤 [bold]Dormant Entities[/bold] (not mentioned in {days}+ days)\n")
        
        analyzer = EntityTimelineAnalyzer(DB_PATH)
        dormant = analyzer.get_dormant_entities(limit=limit, min_frequency=3)
        
        if not dormant:
            console.print("[yellow]No dormant entities found.[/yellow]")
            console.print(f"[dim](Need entities with frequency >= 3 not seen in {days}+ days)[/dim]\n")
            return
        
        for i, timeline in enumerate(dormant, 1):
            console.print(f"{i}. [cyan]{timeline.entity_text}[/cyan] ({timeline.entity_type or 'untyped'})")
            console.print(f"   Mentioned {timeline.frequency} times")
            console.print(f"   Last seen: {timeline.days_since_last} days ago")
            console.print(f"   First mentioned: {timeline.days_since_first} days ago")
            console.print()
        
        console.print(f"[dim]💡 View timeline: [bold]mnemonic entities timeline-show <entity>[/bold][/dim]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Error getting dormant entities: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@entities_group.command(name='timeline-show')
@click.argument('entity_name')
@click.option('--granularity', '-g', default='month', help='Time granularity (day/week/month/quarter/year)')
def timeline_show(entity_name, granularity):
    """Show timeline visualization for an entity"""
    try:
        from mnemonic.entity_timeline import EntityTimelineAnalyzer
        from mnemonic.config import DB_PATH
        
        if not Path(DB_PATH).exists():
            console.print("[red]✗ Database not found. Store some memories first![/red]")
            return
        
        analyzer = EntityTimelineAnalyzer(DB_PATH)
        
        # Get and display timeline
        timeline = analyzer.get_entity_timeline(entity_name)
        
        if not timeline:
            console.print(f"[red]✗ Entity '{entity_name}' not found.[/red]\n")
            return
        
        # Show visualization
        viz = analyzer.visualize_timeline(entity_name, granularity=granularity)
        console.print(viz)
        
        # Show details
        emoji = analyzer._trend_emoji(timeline.trend)
        console.print(f"[bold]Details:[/bold]")
        console.print(f"  Type: {timeline.entity_type or 'untyped'}")
        console.print(f"  Trend: {emoji} {timeline.trend}")
        console.print(f"  Activity Score: {timeline.activity_score}/100")
        console.print(f"  Total Mentions: {timeline.frequency}")
        console.print(f"  First Mention: {timeline.days_since_first} days ago")
        console.print(f"  Last Mention: {timeline.days_since_last} days ago")
        console.print()
        
    except Exception as e:
        console.print(f"[red]✗ Error showing timeline: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@entities_group.command(name='timeline-summary')
@click.option('--period', '-p', default='month', help='Period (day/week/month/quarter/year)')
@click.option('--limit', '-n', default=6, help='Number of periods to show')
def timeline_summary(period, limit):
    """Show activity summary by time period"""
    try:
        from mnemonic.entity_timeline import EntityTimelineAnalyzer
        from mnemonic.config import DB_PATH
        
        if not Path(DB_PATH).exists():
            console.print("[red]✗ Database not found. Store some memories first![/red]")
            return
        
        console.print(f"\n📊 [bold]Activity Summary by {period.capitalize()}[/bold]\n")
        
        analyzer = EntityTimelineAnalyzer(DB_PATH)
        summary = analyzer.get_activity_summary(period=period, limit=limit)
        
        if not summary:
            console.print("[yellow]No activity data found.[/yellow]\n")
            return
        
        for period_data in summary:
            console.print(f"[bold cyan]{period_data.period}[/bold cyan]")
            console.print(f"  Entities: {period_data.entity_count} | Mentions: {period_data.total_mentions}")
            
            if period_data.top_entities:
                top_3 = period_data.top_entities[:3]
                console.print(f"  Top: ", end="")
                for i, (entity, count) in enumerate(top_3):
                    if i > 0:
                        console.print(", ", end="")
                    console.print(f"[green]{entity}[/green] ({count})", end="")
                console.print()
            
            console.print()
        
    except Exception as e:
        console.print(f"[red]✗ Error getting activity summary: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


# For testing
if __name__ == "__main__":
    entities_group()