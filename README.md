# Mnemonic: A Personal AI Memory System

Building an AI that actually remembers you.

## The Problem
Current AI assistants have amnesia. Every conversation starts from zero. 
Mnemonic changes that.

## What I'm Building
A local-first, personal AI context engine that:
- Remembers every interaction
- Learns your patterns and preferences
- Connects knowledge across conversations
- Runs on your machine (privacy-first)
- Gets smarter over time


**Status:** Week 1 - Foundation

## Tech Stack
- Python 3.11+
- ChromaDB (vector storage)
- SQLite (graph relationships)
- [More as I build]

## Mnemonic.cli Usage
- Store a memory - python -m mnemonic.cli store "Your memory here"
- Search memories - python -m mnemonic.cli search "keyword"
- List recent memories - python -m mnemonic.cli list
- View statistics - python -m mnemonic.cli stats

---
## Progress

### ✅ Day 1 (Oct 15)
- Repository setup
- Project structure
- Initial README

### ✅ Day 2 (Oct 16)
- Core memory system implemented
- JSON persistence working
- Basic search functionality
- Test suite passing