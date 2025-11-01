"""
CLI Commands for Entity Type Management (Day 7)

New commands:
- mnemonic entities suggest
- mnemonic entities add-type <n>
- mnemonic entities remove-type <n>
- mnemonic entities list-types
- mnemonic entities status
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


@entities_group.command(name='suggest')
@click.option('--limit', '-n', default=10, help='Number of suggestions to show')
def suggest_entities(limit):
    """Suggest new entity types based on patterns in your memories"""
    try:
        # Import here to avoid issues if migration not run yet
        from mnemonic.entity_type_manager import EntityTypeManager
        
        db_path = get_db_path()
        
        # Check if database exists
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
        
        # Create suggestions table
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
            console.print(f"[dim]💡 Check status with: [bold]mnemonic entities status[/bold][/dim]\n")
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
                # Color status
                status_colored = {
                    'pending': f"[yellow]{job.status}[/yellow]",
                    'processing': f"[blue]{job.status}[/blue]",
                    'completed': f"[green]{job.status}[/green]",
                    'failed': f"[red]{job.status}[/red]"
                }.get(job.status, job.status)
                
                # Progress bar
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
        else:
            console.print("\n[dim]No re-extraction jobs yet.[/dim]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Error getting status: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


# For testing
if __name__ == "__main__":
    entities_group()