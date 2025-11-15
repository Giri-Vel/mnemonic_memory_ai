#!/usr/bin/env python3
"""Generate compact project structure for Mnemonic."""

import os
from pathlib import Path

def get_structure(root_path="."):
    """Get project structure focusing on Python files and key directories."""
    
    ignore_dirs = {
        '__pycache__', '.git', '.pytest_cache', 'venv', 'env', 
        '.venv', 'node_modules', '.idea', '.vscode', 'dist', 
        'build', '*.egg-info', '.eggs', '.tox'
    }
    
    structure = []
    root = Path(root_path)
    
    # Get all Python files
    py_files = []
    for path in sorted(root.rglob('*.py')):
        # Skip ignored directories
        if any(ignore in path.parts for ignore in ignore_dirs):
            continue
        rel_path = path.relative_to(root)
        py_files.append(str(rel_path))
    
    # Get key config files
    config_files = [
        'pyproject.toml', 'requirements.txt', '.env.example', 
        'README.md', 'setup.py', 'setup.cfg'
    ]
    
    other_files = []
    for config in config_files:
        config_path = root / config
        if config_path.exists():
            other_files.append(config)
    
    # Print structure
    print("=" * 60)
    print("MNEMONIC PROJECT STRUCTURE")
    print("=" * 60)
    
    print("\n📁 Python Files:")
    print("-" * 60)
    for f in py_files:
        print(f"  {f}")
    
    print("\n📄 Config Files:")
    print("-" * 60)
    for f in other_files:
        print(f"  {f}")
    
    print("\n" + "=" * 60)
    print(f"Total Python files: {len(py_files)}")
    print("=" * 60)
    
    # Also output just the directory tree
    print("\n📂 Directory Tree:")
    print("-" * 60)
    dirs = set()
    for f in py_files:
        parts = Path(f).parts
        for i in range(len(parts)):
            dirs.add('/'.join(parts[:i+1]))
    
    for d in sorted(dirs):
        depth = d.count('/')
        indent = "  " * depth
        name = Path(d).name
        if d.endswith('.py'):
            print(f"{indent}├── {name}")
        else:
            print(f"{indent}└── {name}/")

if __name__ == '__main__':
    get_structure()