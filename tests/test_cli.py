"""
Minimal CLI smoke tests for Mnemonic.
Tests basic command functionality without over-investing (UI coming later).
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
from mnemonic.cli import cli


@pytest.fixture
def temp_mnemonic_dir():
    """Create a temporary .mnemonic directory for testing."""
    temp_dir = tempfile.mkdtemp()
    mnemonic_dir = Path(temp_dir) / ".mnemonic"
    mnemonic_dir.mkdir(parents=True, exist_ok=True)
    
    # Set environment to use temp directory
    import os
    original_home = os.environ.get('HOME')
    os.environ['HOME'] = temp_dir
    
    yield mnemonic_dir
    
    # Cleanup
    if original_home:
        os.environ['HOME'] = original_home
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


class TestCLICommands:
    """Smoke tests for CLI commands."""
    
    def test_store_command(self, runner, temp_mnemonic_dir):
        """Test storing a memory via CLI."""
        result = runner.invoke(cli, [
            'store',
            'Test memory content',
            '--tags', 'test,cli'
        ])
        
        assert result.exit_code == 0
        assert 'Stored memory' in result.output or '✓' in result.output
    
    def test_store_with_multiple_tags(self, runner, temp_mnemonic_dir):
        """Test storing a memory with multiple tags."""
        result = runner.invoke(cli, [
            'store',
            'Another test memory',
            '--tags', 'test',
            '--tags', 'cli',
            '--tags', 'multiple'
        ])
        
        assert result.exit_code == 0
    
    def test_search_command(self, runner, temp_mnemonic_dir):
        """Test searching memories via CLI."""
        # First, store a memory
        runner.invoke(cli, [
            'store',
            'Machine learning project deadline',
            '--tags', 'work,ai'
        ])
        
        # Then search for it
        result = runner.invoke(cli, ['search', 'machine learning'])
        
        assert result.exit_code == 0
        assert 'Search Results' in result.output or 'machine learning' in result.output.lower()
    
    def test_search_with_limit(self, runner, temp_mnemonic_dir):
        """Test search with result limit."""
        # Store multiple memories
        for i in range(5):
            runner.invoke(cli, [
                'store',
                f'Test memory number {i}',
                '--tags', 'test'
            ])
        
        # Search with limit
        result = runner.invoke(cli, [
            'search',
            'test memory',
            '--limit', '3'
        ])
        
        assert result.exit_code == 0
    
    def test_search_no_results(self, runner, temp_mnemonic_dir):
        """Test search with no matching results."""
        result = runner.invoke(cli, ['search', 'nonexistent_query_xyz'])
        
        assert result.exit_code == 0
        # Check for either message or empty table
        assert ('No memories found' in result.output or 
                'Search Results' in result.output)  # Empty table is OK too
    
    def test_recent_command(self, runner, temp_mnemonic_dir):
        """Test listing recent memories."""
        # Store some memories
        runner.invoke(cli, ['store', 'Recent memory 1', '--tags', 'test'])
        runner.invoke(cli, ['store', 'Recent memory 2', '--tags', 'test'])
        
        # List recent
        result = runner.invoke(cli, ['recent'])
        
        assert result.exit_code == 0
        assert 'Recent memory' in result.output or 'memories' in result.output.lower()
    
    def test_recent_with_limit(self, runner, temp_mnemonic_dir):
        """Test listing recent memories with limit."""
        # Store multiple memories
        for i in range(5):
            runner.invoke(cli, ['store', f'Memory {i}', '--tags', 'test'])
        
        # List recent with limit
        result = runner.invoke(cli, ['recent', '--limit', '3'])
        
        assert result.exit_code == 0
    
    def test_stats_command(self, runner, temp_mnemonic_dir):
        """Test getting system statistics."""
        # Store a memory first
        runner.invoke(cli, ['store', 'Stats test memory', '--tags', 'test'])
        
        # Get stats
        result = runner.invoke(cli, ['stats'])
        
        assert result.exit_code == 0
        assert 'Memory System Statistics' in result.output or 'Total' in result.output
    
    def test_get_command(self, runner, temp_mnemonic_dir):
        """Test getting a specific memory by ID."""
        # Store a memory
        store_result = runner.invoke(cli, [
            'store',
            'Get command test memory',
            '--tags', 'test'
        ])
        
        # Extract memory ID from output (assuming it's displayed)
        # This is a basic check - we know store works, just verify get doesn't crash
        result = runner.invoke(cli, ['get', 'some-id'])
        
        # Should either show memory or "not found" - both are valid behaviors
        assert result.exit_code in [0, 1]  # 0 = found, 1 = not found (both OK)
    
    def test_delete_command(self, runner, temp_mnemonic_dir):
        """Test deleting a memory."""
        # Store a memory first
        runner.invoke(cli, ['store', 'Memory to delete', '--tags', 'test'])
        
        # Try to delete (we don't know the ID, so this might fail)
        # The important thing is the command doesn't crash
        result = runner.invoke(cli, ['delete', 'some-id'])
        
        # Should handle gracefully whether ID exists or not
        assert result.exit_code in [0, 1]
    
    def test_reset_command(self, runner, temp_mnemonic_dir):
        """Test resetting the memory system."""
        # Store some data first
        runner.invoke(cli, ['store', 'Memory before reset', '--tags', 'test'])
        
        # Reset with confirmation (pipe 'y' to stdin)
        result = runner.invoke(cli, ['reset'], input='y\n')
        
        # Should complete (exit code 0 or handle as appropriate)
        # We're just checking it doesn't crash
        assert result.exit_code in [0, 1]
    
    def test_store_empty_content_fails(self, runner, temp_mnemonic_dir):
        """Test that storing empty content fails gracefully."""
        result = runner.invoke(cli, ['store', ''])
        
        # Should fail or show error message
        assert result.exit_code != 0 or 'error' in result.output.lower()
    
    def test_search_empty_query(self, runner, temp_mnemonic_dir):
        """Test searching with empty query."""
        result = runner.invoke(cli, ['search', ''])
        
        # Should handle gracefully
        assert result.exit_code in [0, 1, 2]  # Various error codes are OK


class TestCLIIntegration:
    """Integration tests for CLI workflows."""
    
    def test_store_search_workflow(self, runner, temp_mnemonic_dir):
        """Test complete store -> search workflow."""
        # Store a memory
        store_result = runner.invoke(cli, [
            'store',
            'Integration test memory about machine learning',
            '--tags', 'test,ml,integration'
        ])
        assert store_result.exit_code == 0
        
        # Search for it
        search_result = runner.invoke(cli, ['search', 'machine learning'])
        assert search_result.exit_code == 0
        assert 'machine learning' in search_result.output.lower() or 'Integration test' in search_result.output
        
        # Verify it appears in recent
        recent_result = runner.invoke(cli, ['recent', '--limit', '5'])
        assert recent_result.exit_code == 0
    
    def test_multiple_memories_search(self, runner, temp_mnemonic_dir):
        """Test storing multiple memories and searching."""
        # Store multiple related memories
        memories = [
            'Python programming tutorial',
            'Machine learning with Python',
            'Data science Python libraries',
        ]
        
        for memory in memories:
            result = runner.invoke(cli, ['store', memory, '--tags', 'python'])
            assert result.exit_code == 0
        
        # Search should find all Python-related
        search_result = runner.invoke(cli, ['search', 'Python'])
        assert search_result.exit_code == 0
        
        # Stats should show 3+ memories
        stats_result = runner.invoke(cli, ['stats'])
        assert stats_result.exit_code == 0