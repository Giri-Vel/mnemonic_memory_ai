Context: Building Mnemonic - a personal AI memory system
Timeline: 6 months (Oct 2024 - April 2025)
Goal: Production-grade project + 250k USD remote job

Repo: https://github.com/Giri-Vel/mnemonic_memory_ai/tree/main
Roadmap: https://github.com/Giri-Vel/mnemonic_memory_ai/blob/main/ROADMAP.md

## Status: Week 1 COMPLETE ✅ (2 days ahead of schedule)

### Where We Started Day 5
- ChromaDB semantic search working (Day 4 complete)
- 47 tests passing, ~24% coverage
- Basic CLI functional

### What We Built Today

**1. Tags Migration**
- ChromaDB 1.2.1 doesn't support list metadata
- Solution: JSON serialization (`'["work", "ai"]'`)
- Migration script executed successfully

**2. Custom Embedding Service**
- `all-MiniLM-L6-v2` with disk caching (diskcache)
- Replaces ChromaDB default embeddings
- Files: `mnemonic/embedding_service.py`, `tests/test_embedding_service.py`
- Dependencies: `sentence-transformers`, `diskcache`

**3. Hybrid Search (85/15)**
- 85% semantic + 15% keyword weighting
- Normalized score fusion (industry standard)
- No user toggles - system decides automatically
- Excels at: proper nouns, dates, IDs, acronyms
- Files: Updated `memory_system.py`, `cli.py`

**4. CLI Tests**
- 15 smoke tests added (`tests/test_cli.py`)
- CLI coverage: 0% → ~50%

### Where We Are Now
- **Tests:** 47 → 62 (+32%)
- **Coverage:** ~24% → ~40%
- **Search:** Intelligent hybrid as default
- **Quality:** Production-ready

### Next: Week 2 - Structured Memory
**Goal:** SQLite graph layer for entity relationships

**Plan:**
- SQLite schema (entities, relationships, facts tables)
- Entity extraction (people, projects, dates)
- Hybrid retrieval: vector (ChromaDB) + graph (SQLite)
- Query: "What do I know about X?" pulls both

**Tech:** SQLite, custom entity extraction

### Key Decisions Made
- Dictionary returns (JSON-ready for future API)
- No user search mode toggles
- JSON serialization for ChromaDB compatibility
- 85/15 semantic/keyword balance

### Technical Notes
- Python 3.11, macOS, pyproject.toml
- ChromaDB 1.2.1 (lists need JSON serialization)
- All search methods return: `[{"memory": {...}, "score": ...}]`