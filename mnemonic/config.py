"""
Mnemonic configuration
"""
from pathlib import Path
import os

# Project root - can be overridden with environment variable
PROJECT_ROOT = Path(os.environ.get('MNEMONIC_ROOT', Path.home() / 'Mnemonic'))

# Data directory
DATA_DIR = PROJECT_ROOT / ".mnemonic"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database paths
DB_PATH = str(DATA_DIR / "mnemonic.db")
VECTOR_STORE_PATH = str(DATA_DIR / "chroma")
JSON_PATH = str(DATA_DIR / "memories.json")