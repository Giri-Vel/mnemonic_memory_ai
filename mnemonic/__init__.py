"""
Mnemonic - Personal AI Memory System

A local-first memory system that learns and remembers.
"""

__version__ = "0.1.0"
__author__ = "Giri Vel"

from mnemonic.memory_system import Memory, MemorySystem
from mnemonic.vector_store import VectorStore

__all__ = ["Memory", "MemorySystem", "VectorStore"]