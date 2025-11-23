"""
CLI Commands for Session Management

Commands:
- mnemonic sessions list      # List recent conversation sessions
- mnemonic sessions view <id> # View details of a specific session
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from pathlib import Path
from datetime import datetime

console = Console()


def get_db_path():
    """Get the database path"""
    from mnemonic.config import DB_PATH
    return DB_PATH


@click.group(name='sessions')
def sessions_group():
    """Manage conversation sessions"""
    pass


@sessions_group.command(name='list')
@click.option('--limit', '-n', default=10, help='Number of sessions to show')
def list_sessions(limit):
    """List recent conversation sessions"""
    try:
        from mnemonic.memory_system import MemorySystem
        
        db_path = get_db_path()
        
        if not Path(db_path).exists():
            console.print("[yellow]⚠[/yellow] Database not found. Store some memories first!")
            return
        
        memory_system = MemorySystem()
        sessions = memory_system.get_sessions(limit=limit)
        
        if not sessions:
            console.print("[yellow]No sessions found yet.[/yellow]")
            console.print("\n[dim]Sessions are created automatically when you store memories.[/dim]\n")
            return
        
        # Create table
        table = Table(
            title=f"📅 Recent Conversation Sessions",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("ID", style="dim", width=10)
        table.add_column("Date Range", style="white", width=25)
        table.add_column("Memories", style="yellow", width=10)
        table.add_column("Summary", style="green", width=50)
        
        for session in sessions:
            session_id = session['id'][:8]
            
            # Format date range
            start_date = datetime.fromisoformat(session['start_time']).strftime("%b %d, %H:%M")
            
            # Handle active sessions (end_time is None)
            if session['end_time']:
                end_date = datetime.fromisoformat(session['end_time']).strftime("%b %d, %H:%M")
                date_range = f"{start_date} - {end_date}"
            else:
                date_range = f"{start_date} - (active)"
            
            memory_count = str(session['memory_count'])
            
            # Truncate summary (handle None)
            summary = session.get('summary') or '(No summary)'
            if len(summary) > 50:
                summary = summary[:47] + "..."
            
            table.add_row(session_id, date_range, memory_count, summary)
        
        console.print(table)
        console.print(f"\n[dim]💡 View session details: [bold]mnemonic sessions view <id>[/bold][/dim]\n")
        
    except Exception as e:
        console.print(f"[red]✗ Error listing sessions: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


@sessions_group.command(name='view')
@click.argument('session_id')
def view_session(session_id):
    """View detailed information about a specific session"""
    try:
        from mnemonic.memory_system import MemorySystem
        
        db_path = get_db_path()
        
        if not Path(db_path).exists():
            console.print("[red]✗ Database not found. Store some memories first![/red]")
            return
        
        memory_system = MemorySystem()
        session_details = memory_system.get_session_details(session_id)
        
        if not session_details:
            console.print(f"[red]✗ Session not found: {session_id}[/red]")
            console.print("[dim]💡 Use 'mnemonic sessions list' to see available sessions[/dim]\n")
            return
        
        # Session overview panel
        start_time = datetime.fromisoformat(session_details['start_time']).strftime("%b %d, %Y %H:%M")
        
        # Handle active sessions
        if session_details['end_time']:
            end_time = datetime.fromisoformat(session_details['end_time']).strftime("%b %d, %Y %H:%M")
            time_range = f"{start_time} to {end_time}"
        else:
            time_range = f"{start_time} to (active)"
        
        overview_text = f"""
[cyan]Session ID:[/cyan] {session_details['id'][:8]}
[cyan]Date Range:[/cyan] {time_range}
[cyan]Total Memories:[/cyan] {session_details['memory_count']}
        """
        
        panel = Panel(
            overview_text.strip(),
            title="📅 Session Overview",
            border_style="cyan",
            box=box.ROUNDED
        )
        console.print(panel)
        
        # Summary panel (handle None)
        summary = session_details.get('summary') or '(No summary)'
        summary_panel = Panel(
            summary,
            title="📝 Summary",
            border_style="green",
            box=box.ROUNDED
        )
        console.print(summary_panel)
        
        # Entity highlights (if available)
        entity_highlights = session_details.get('entity_highlights')
        if entity_highlights:
            highlights_text = ", ".join(entity_highlights)
            highlights_panel = Panel(
                highlights_text,
                title="🏷️  Entity Highlights",
                border_style="magenta",
                box=box.ROUNDED
            )
            console.print(highlights_panel)
        
        # Memories in this session
        memories = session_details.get('memories', [])
        if memories:
            console.print(f"\n[bold]Memories in Session ({len(memories)}):[/bold]\n")
            
            table = Table(
                box=box.SIMPLE,
                show_header=True,
                header_style="bold"
            )
            table.add_column("Time", style="dim", width=12)
            table.add_column("Content", style="white", width=70)
            
            for memory in memories:
                timestamp = datetime.fromisoformat(memory['timestamp']).strftime("%H:%M:%S")
                content = memory['content']
                if len(content) > 70:
                    content = content[:67] + "..."
                
                table.add_row(timestamp, content)
            
            console.print(table)
        
        console.print()
        
    except Exception as e:
        console.print(f"[red]✗ Error viewing session: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


if __name__ == "__main__":
    sessions_group()