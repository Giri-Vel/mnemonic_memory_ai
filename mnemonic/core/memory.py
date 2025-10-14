"""
Mnemonic Core - Simplest possible memory system
Goal: Store text, retrieve text, prove the concept
"""

from datetime import datetime
from typing import List, Dict
import json
import os

class SimpleMemory:
    def __init__(self, storage_path: str = "./memory.json"):
        self.storage_path = storage_path
        self.memories = self._load()
    
    def _load(self) -> List[Dict]:
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        return []
    
    def _save(self):
        with open(self.storage_path, 'w') as f:
            json.dump(self.memories, f, indent=2)
    
    def store(self, content: str, metadata: Dict = None):
        """Store a memory"""
        memory = {
            "id": len(self.memories),
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.memories.append(memory)
        self._save()
        return memory["id"]
    
    def retrieve_all(self) -> List[Dict]:
        """Get all memories"""
        return self.memories
    
    def search(self, query: str) -> List[Dict]:
        """Dumb search - just substring matching for now"""
        query_lower = query.lower()
        return [m for m in self.memories if query_lower in m["content"].lower()]

# Test it
if __name__ == "__main__":
    mem = SimpleMemory()
    
    # Store some memories
    mem.store("I am working on a personal AI memory system")
    mem.store("My goal is to get a 250k USD remote job")
    mem.store("I am getting married in June 2025")
    
    # Retrieve
    print("All memories:", len(mem.retrieve_all()))
    print("\nSearch 'job':", mem.search("job"))