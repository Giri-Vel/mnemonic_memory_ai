Context: Building Mnemonic - a personal AI memory system
Timeline: 6 months (Oct 2024 - April 2025)
Goal: Production-grade project + 250k USD remote job

Repo: https://github.com/Giri-Vel/mnemonic_memory_ai/tree/main
Roadmap: https://github.com/Giri-Vel/mnemonic_memory_ai/blob/main/ROADMAP.md

## Status: Week 2 Day 6 COMPLETE ✅ (1 day ahead of schedule)

### Where We Started Day 6
- Week 1 complete (hybrid search, CLI, 62 tests passing)
- ChromaDB + SQLite architecture working
- ~40% test coverage

### What We Built on Day 6

**1. Entity Extraction Core**
- GLiNER zero-shot NER (person, organization, location, date)
- spaCy noun phrase extraction (untyped entities)
- Tag-to-entity conversion (user tags + auto-inferred)
- Files: `mnemonic/entity_extractor.py` (~350 LOC)
- Performance: ~100-120ms per memory

**2. Entity Storage System**
- Two-table design: tentative (freq=1) → confirmed (freq≥2)
- Automatic promotion logic on second occurrence
- Case-insensitive entity matching
- Files: `mnemonic/entity_storage.py` (~400 LOC)
- Tables: `tentative_entities`, `entities`

**3. Checkpointing System**
- Pre-computes noun phrases + context for fast re-extraction
- 50x speedup: 100ms → 2ms per memory
- Version tracking for extraction algorithm changes
- Files: `mnemonic/checkpointing.py` (~300 LOC)
- Storage: ~2KB per memory checkpoint

**4. Database Migrations**
- Migration 001: Base memory tables
- Migration 002: Entity extraction tables (4 new tables)
- Migration runner: `migrate.py`
- Tables: `entities`, `tentative_entities`, `entity_extraction_checkpoints`, `user_entity_types`

**5. Test Suite**
- 19 new tests for entity system
- All tests passing ✅
- Files: `tests/test_entity_system.py`

### Where We Are Now
- **Tests:** 62 → 81 total (19 new entity tests passing)
- **Coverage:** ~40% → ~24% (denominator increased with new code)
- **Entity System:** Fully functional but not integrated into memory_system.py yet
- **Performance:** Entity extraction <150ms, re-extraction <5ms with checkpoints

### Current Architecture
```
Memory Input
    ↓
ChromaDB (vector search) ← [Week 1]
    +
SQLite (entity storage) ← [Week 2 Day 6 - NEW]
    ↓
Hybrid Search Results
```

**Note:** Entity system built but NOT yet integrated into `memory_system.py` - integration planned for end of Week 2

### Next: Day 7-8 - Dynamic Entity Type Management

**Day 7 Goals:**
- Entity type suggestion system (analyze patterns in memories)
- User entity type CRUD (add/remove/list types)
- CLI commands: `mnemonic entities suggest`, `add-type`, `list-types`
- Pattern detection: tag frequency, noun phrase emergence

**Day 8 Goals:**
- Background re-extraction when new types added
- Checkpoint-based fast re-extraction (use stored noun phrases)
- Progress tracking and batch processing
- Handle 10,000+ memories efficiently

### Key Decisions Made (Day 6)
- **Hybrid entity approach:** Core (always) + User-defined (dynamic) + Untyped (noun phrases) + Tags
- **Two-table promotion:** Tentative → Confirmed on second occurrence (reduces noise)
- **Synchronous checkpointing:** +20ms overhead but ensures fast future re-extraction
- **Zero-shot NER:** GLiNER for flexibility vs fixed spaCy models
- **Case-insensitive matching:** "Sarah" == "sarah" for entity resolution

### Technical Stack (Updated)
- Python 3.11, macOS, pyproject.toml
- ChromaDB 1.2.1 (vector search)
- SQLite (entity graph storage)
- GLiNER 0.2.0+ (zero-shot entity extraction)
- spaCy 3.7.0+ with en_core_web_sm (noun phrases)
- PyTorch CPU-only (~500MB install)

### Entity Extraction Performance
| Operation | Time | Notes |
|-----------|------|-------|
| Entity extraction | 100-120ms | GLiNER + spaCy + checkpointing |
| Storage (tentative) | <1ms | First occurrence |
| Storage (promotion) | <2ms | Second occurrence |
| Checkpoint creation | ~20ms | Noun phrase extraction |
| Re-extraction (with checkpoint) | 2ms | 50x faster than full extraction |

### Files Created Day 6
```
migrations/
├── M001_initial_schema.py
└── M002_add_entity_tables.py

mnemonic/
├── entity_extractor.py      # ~350 LOC
├── entity_storage.py         # ~400 LOC
└── checkpointing.py          # ~300 LOC

tests/
└── test_entity_system.py     # 19 tests

migrate.py                     # Migration runner
test_day6_complete.py         # Comprehensive test suite
```

### Known Issues/Deferred
- Old tests (Week 1) failing - expected, need integration into memory_system.py
- Integration planned for end of Week 2 (after clustering + relationships built)
- No entity type suggestions yet (Day 7 feature)
- No graph relationships yet (Day 8-9 feature)

### What's Working Right Now
✅ Entity extraction from text (core + noun phrases + tags)
✅ Entity storage with frequency tracking
✅ Tentative → confirmed promotion
✅ Checkpointing for fast re-extraction
✅ 19 entity tests passing
❌ Not integrated into main memory_system.py yet (planned)

---

**Starting Day 7:** Dynamic entity type management - let system learn YOUR domain!