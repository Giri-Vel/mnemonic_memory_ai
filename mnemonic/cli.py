"""
Command-line interface for Mnemonic memory system.
Enhanced with semantic search capabilities.
"""
import click
import logging
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from mnemonic.memory_system import MemorySystem


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rich console for pretty output
console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    Mnemonic - Personal AI Memory System
    
    A local-first memory system that learns and remembers.
    """
    pass



# @cli.command()
# @click.argument("content")
# @click.option("--tags", "-t", multiple=True, help="Tags for categorization")
# def store(content: str, tags: tuple):
#     """Store a new memory."""
#     try:
#         memory_system = MemorySystem()
#         memory = memory_system.add(
#             content=content,
#             tags=list(tags) if tags else None
#         )
        
#         console.print(f"[green]✓[/green] Memory stored: {memory.id[:8]}...")
#         if tags:
#             console.print(f"  Tags: {', '.join(tags)}")
#     except Exception as e:
#         console.print(f"[red]✗[/red] Error storing memory: {e}", style="red")
#         logger.error(f"Error in store command: {e}", exc_info=True)


@cli.command()
@click.argument("content")
@click.option("--tags", "-t", multiple=True, help="Tags for categorization")
def store(content: str, tags: tuple):
    """Store a new memory."""
    import builtins  # Import at function level
    
    try:
        memory_system = MemorySystem()
        memory = memory_system.add(
            content=content,
            tags=builtins.list(tags) if tags else None  # Use builtins.list!
        )
        
        console.print(f"[green]✓[/green] Memory stored: {memory.id[:8]}...")
        if tags:
            console.print(f"  Tags: {', '.join(tags)}")
    except Exception as e:
        console.print(f"[red]✗[/red] Error storing memory: {e}", style="red")
        logger.error(f"Error in store command: {e}", exc_info=True)


@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=5, help="Number of results to return")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
def search(query: str, limit: int, tags: tuple):
    """Search memories using intelligent hybrid search (85% semantic + 15% keyword)."""
    try:
        memory_system = MemorySystem()
        
        # Use hybrid search
        results = memory_system.hybrid_search(
            query=query,
            n_results=limit,
            tags=list(tags) if tags else None
        )
        
        # Check for empty results FIRST
        if not results:
            console.print(f"[yellow]No memories found for: '{query}'[/yellow]")
            return
        
        # Display results in a table
        table = Table(
            title=f"🔍 Search Results for: '{query}'",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("Score", style="green", width=8)
        table.add_column("Content", style="white", width=60)
        table.add_column("Tags", style="magenta", width=20)
        table.add_column("Match", style="dim", width=15)
        
        for result in results:
            memory = result["memory"]
            hybrid_score = result.get("hybrid_score", 0)
            score_pct = f"{hybrid_score * 100:.0f}%"
            
            # Determine match type
            sources = result.get("sources", [])
            
            if len(sources) == 2:
                match_type = "Both"
            elif "semantic" in sources:
                match_type = "Concept"
            else:
                match_type = "Keyword"
            
            content_preview = memory["content"][:100] + "..." if len(memory["content"]) > 100 else memory["content"]
            tags_str = ", ".join(memory.get("tags", []))
            
            table.add_row(score_pct, content_preview, tags_str, match_type)
        
        console.print(table)
        console.print(f"\n[dim]Search powered by hybrid algorithm (85% semantic, 15% keyword)[/dim]")
        
    except Exception as e:
        console.print(f"[red]✗[/red] Error searching memories: {e}", style="red")
        logger.error(f"Error in search command: {e}", exc_info=True)


# @cli.command()
# @click.option("--limit", "-n", default=10, help="Number of memories to show")
# def list(limit: int):
@cli.command(name="recent")  # Change the command name
@click.option("--limit", "-n", default=10, help="Number of memories to show")
def list_memories(limit: int):  # Rename the function
    """List recent memories."""
    try:
        memory_system = MemorySystem()
        memories = memory_system.list_recent(n=limit)
        
        if not memories:
            console.print("[yellow]No memories stored yet[/yellow]")
            return
        
        table = Table(
            title=f"Recent Memories (Last {len(memories)})",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("ID", style="dim", width=12)
        table.add_column("Content", style="white", width=60)
        table.add_column("Tags", style="magenta", width=20)
        table.add_column("Date", style="dim", width=12)
        
        for memory in memories:
            mem_dict = memory.to_dict()
            content_preview = mem_dict["content"][:100] + "..." if len(mem_dict["content"]) > 100 else mem_dict["content"]
            tags_str = ", ".join(mem_dict.get("tags", []))
            date = mem_dict["timestamp"][:10]  # Just the date part
            
            table.add_row(mem_dict["id"][:12], content_preview, tags_str, date)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]✗[/red] Error listing memories: {e}", style="red")
        logger.error(f"Error in list command: {e}", exc_info=True)


@cli.command()
def stats():
    """Show memory system statistics."""
    try:
        memory_system = MemorySystem()
        stats = memory_system.get_stats()
        
        # Create a styled panel
        stats_text = f"""
[cyan]Total Memories:[/cyan] {stats['total_memories']}
[cyan]Unique Tags:[/cyan] {stats['unique_tags']}
[cyan]JSON Storage:[/cyan] {stats['json_path']}
[cyan]Vector Store:[/cyan] {stats['vector_store']['persist_directory']}
[cyan]Vector Collection:[/cyan] {stats['vector_store']['collection_name']}
        """
        
        panel = Panel(
            stats_text.strip(),
            title="📊 Mnemonic Statistics",
            border_style="cyan",
            box=box.DOUBLE
        )
        
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]✗[/red] Error getting stats: {e}", style="red")
        logger.error(f"Error in stats command: {e}", exc_info=True)


@cli.command()
@click.argument("memory_id")
def get(memory_id: str):
    """Get a specific memory by ID."""
    try:
        memory_system = MemorySystem()
        memory = memory_system.get(memory_id)
        
        if not memory:
            console.print(f"[red]✗[/red] Memory not found: {memory_id}", style="red")
            return
        
        mem_dict = memory.to_dict()
        
        # Display in a styled panel
        content = f"""
[cyan]ID:[/cyan] {mem_dict['id']}
[cyan]Content:[/cyan] {mem_dict['content']}
[cyan]Tags:[/cyan] {', '.join(mem_dict.get('tags', [])) or 'None'}
[cyan]Created:[/cyan] {mem_dict['timestamp']}
        """
        
        if "updated_at" in mem_dict["metadata"]:
            content += f"\n[cyan]Updated:[/cyan] {mem_dict['metadata']['updated_at']}"
        
        panel = Panel(
            content.strip(),
            title="📝 Memory Details",
            border_style="cyan",
            box=box.ROUNDED
        )
        
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]✗[/red] Error getting memory: {e}", style="red")
        logger.error(f"Error in get command: {e}", exc_info=True)


@cli.command()
@click.argument("memory_id")
@click.confirmation_option(prompt="Are you sure you want to delete this memory?")
def delete(memory_id: str):
    """Delete a memory by ID."""
    try:
        memory_system = MemorySystem()
        success = memory_system.delete(memory_id)
        
        if success:
            console.print(f"[green]✓[/green] Memory deleted: {memory_id}")
        else:
            console.print(f"[red]✗[/red] Memory not found: {memory_id}", style="red")
            
    except Exception as e:
        console.print(f"[red]✗[/red] Error deleting memory: {e}", style="red")
        logger.error(f"Error in delete command: {e}", exc_info=True)


@cli.command()
@click.confirmation_option(prompt="Are you sure you want to reset all memories?")
def reset():
    """Reset the entire memory system (delete all data)."""
    try:
        memory_system = MemorySystem()
        memory_system.reset()
        console.print("[green]✓[/green] Memory system reset successfully")
    except Exception as e:
        console.print(f"[red]✗[/red] Error resetting memory system: {e}", style="red")
        logger.error(f"Error in reset command: {e}", exc_info=True)



from mnemonic.cli_entities import entities_group
cli.add_command(entities_group, name='entities')

# if __name__ == "__main__":
#     cli()