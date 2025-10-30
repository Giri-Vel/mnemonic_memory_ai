"""
Entity Extraction System

Extracts entities from memory text using:
1. GLiNER (zero-shot NER) for core + user-defined entities
2. spaCy for noun phrase extraction (untyped entities)
3. Tag conversion for user-provided and auto-inferred tags
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Set
import sqlite3
import json

try:
    from gliner import GLiNER
    GLINER_AVAILABLE = True
except ImportError:
    GLINER_AVAILABLE = False
    print("Warning: GLiNER not available. Install with: pip install gliner")

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("Warning: spaCy not available. Install with: pip install spacy")


# Constants
CHECKPOINT_VERSION = 1
CORE_LABELS = ["person", "organization", "location", "date"]
CONFIDENCE_THRESHOLD = 0.7


@dataclass
class Entity:
    """Represents an extracted entity"""
    text: str
    type: Optional[str]
    type_source: str  # "core" / "user_defined" / "noun_phrase" / "tag"
    confidence: float
    context: Optional[str] = None
    span: Optional[tuple] = None
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    def __hash__(self):
        """Make Entity hashable for set operations"""
        return hash((self.text.lower(), self.type))
    
    def __eq__(self, other):
        """Equality based on text and type"""
        if not isinstance(other, Entity):
            return False
        return self.text.lower() == other.text.lower() and self.type == other.type


class EntityExtractor:
    """
    Main entity extraction engine
    
    Handles extraction from text using multiple strategies:
    - Core entities (person, org, location, date) via GLiNER
    - User-defined entities (learned types) via GLiNER
    - Noun phrases (untyped) via spaCy
    - Tag entities (from user input + auto-inference)
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.gliner_model = None
        self.nlp = None
        self.user_labels = []
        
        # Initialize models
        self._init_gliner()
        self._init_spacy()
        self._load_user_labels()
    
    def _init_gliner(self):
        """Initialize GLiNER model"""
        if not GLINER_AVAILABLE:
            print("⚠ GLiNER not available - core entity extraction disabled")
            return
        
        try:
            print("Loading GLiNER model...")
            self.gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
            print("✓ GLiNER model loaded")
        except Exception as e:
            print(f"✗ Failed to load GLiNER: {e}")
            self.gliner_model = None
    
    def _init_spacy(self):
        """Initialize spaCy model"""
        if not SPACY_AVAILABLE:
            print("⚠ spaCy not available - noun phrase extraction disabled")
            return
        
        try:
            print("Loading spaCy model...")
            self.nlp = spacy.load("en_core_web_sm")
            print("✓ spaCy model loaded")
        except OSError:
            print("✗ spaCy model not found. Download with: python -m spacy download en_core_web_sm")
            self.nlp = None
        except Exception as e:
            print(f"✗ Failed to load spaCy: {e}")
            self.nlp = None
    
    def _load_user_labels(self):
        """Load user-defined entity types from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT type_name FROM user_entity_types")
            self.user_labels = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if self.user_labels:
                print(f"✓ Loaded {len(self.user_labels)} user-defined entity types")
        except sqlite3.OperationalError:
            # Table doesn't exist yet (first run)
            self.user_labels = []
    
    def reload_user_labels(self):
        """Reload user labels from database (call after adding new types)"""
        self._load_user_labels()
    
    def extract(self, text: str, user_tags: List[str] = None) -> List[Entity]:
        """
        Extract all entities from text
        
        Args:
            text: Memory text to extract entities from
            user_tags: User-provided tags (optional)
        
        Returns:
            List of Entity objects
        """
        user_tags = user_tags or []
        entities = []
        
        # 1. Core + user-defined entities via GLiNER
        if self.gliner_model:
            gliner_entities = self._extract_with_gliner(text)
            entities.extend(gliner_entities)
        
        # 2. Noun phrases (untyped entities)
        if self.nlp:
            noun_phrase_entities = self._extract_noun_phrases(text, entities)
            entities.extend(noun_phrase_entities)
        
        # 3. Tag-derived entities (user-provided)
        tag_entities = self._tags_to_entities(user_tags)
        entities.extend(tag_entities)
        
        # 4. Auto-infer additional tags
        inferred_tags = self._infer_tags(text, entities)
        inferred_entities = self._tags_to_entities(inferred_tags)
        entities.extend(inferred_entities)
        
        # Deduplicate entities (same text + type)
        entities = list(set(entities))
        
        return entities
    
    def _extract_with_gliner(self, text: str) -> List[Entity]:
        """
        Extract entities using GLiNER
        
        Args:
            text: Text to extract from
        
        Returns:
            List of Entity objects with types from core + user labels
        """
        if not self.gliner_model:
            return []
        
        # Combine core and user-defined labels
        all_labels = CORE_LABELS + self.user_labels
        
        if not all_labels:
            return []
        
        try:
            results = self.gliner_model.predict_entities(text, all_labels)
        except Exception as e:
            print(f"⚠ GLiNER extraction failed: {e}")
            return []
        
        entities = []
        for result in results:
            # Filter by confidence threshold
            if result.get("score", 0) >= CONFIDENCE_THRESHOLD:
                # Determine source
                type_source = "core" if result["label"] in CORE_LABELS else "user_defined"
                
                entities.append(Entity(
                    text=result["text"],
                    type=result["label"],
                    type_source=type_source,
                    confidence=result["score"]
                ))
        
        return entities
    
    def _extract_noun_phrases(self, text: str, existing_entities: List[Entity]) -> List[Entity]:
        """
        Extract noun phrases as untyped entities
        
        Args:
            text: Text to extract from
            existing_entities: Already extracted entities (to avoid duplicates)
        
        Returns:
            List of Entity objects (untyped)
        """
        if not self.nlp:
            return []
        
        # Build set of existing entity texts for fast lookup
        existing_texts = {e.text.lower() for e in existing_entities}
        
        try:
            doc = self.nlp(text)
        except Exception as e:
            print(f"⚠ spaCy processing failed: {e}")
            return []
        
        entities = []
        
        for chunk in doc.noun_chunks:
            chunk_text = chunk.text.strip()
            
            # Skip if empty or already captured
            if not chunk_text or chunk_text.lower() in existing_texts:
                continue
            
            # Skip single-character or very short phrases
            if len(chunk_text) <= 2:
                continue
            
            # Get context (10 chars before/after)
            start_idx = max(0, chunk.start_char - 10)
            end_idx = min(len(text), chunk.end_char + 10)
            context = text[start_idx:end_idx]
            
            entities.append(Entity(
                text=chunk_text,
                type=None,
                type_source="noun_phrase",
                confidence=0.5,  # Lower confidence for untyped
                context=context,
                span=(chunk.start_char, chunk.end_char)
            ))
        
        return entities
    
    def _tags_to_entities(self, tags: List[str]) -> List[Entity]:
        """
        Convert tags to tag-type entities
        
        Args:
            tags: List of tag strings
        
        Returns:
            List of Entity objects with type="tag"
        """
        return [
            Entity(
                text=tag.strip(),
                type="tag",
                type_source="tag",
                confidence=1.0
            )
            for tag in tags if tag.strip()
        ]
    
    def _infer_tags(self, text: str, entities: List[Entity]) -> List[str]:
        """
        Auto-infer tags from content and entities
        
        Strategy 1: Use user-defined entity types as tags
        Strategy 2: Keyword extraction (TODO: implement later)
        
        Args:
            text: Original text
            entities: Extracted entities
        
        Returns:
            List of inferred tag strings
        """
        inferred = []
        
        # Strategy 1: User-defined entity types become tags
        for entity in entities:
            if entity.type_source == "user_defined" and entity.type:
                inferred.append(entity.type)
        
        # Strategy 2: Keyword extraction
        # TODO: Implement TF-IDF or similar in Day 7
        
        # Deduplicate
        return list(set(inferred))
    
    def get_extraction_stats(self) -> dict:
        """
        Get statistics about entity extraction
        
        Returns:
            Dictionary with stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Tentative entities count
        cursor.execute("SELECT COUNT(*) FROM tentative_entities WHERE status = 'pending'")
        stats["tentative_count"] = cursor.fetchone()[0]
        
        # Confirmed entities count
        cursor.execute("SELECT COUNT(*) FROM entities")
        stats["confirmed_count"] = cursor.fetchone()[0]
        
        # Entities by type
        cursor.execute("""
            SELECT type, COUNT(*) as count 
            FROM entities 
            GROUP BY type 
            ORDER BY count DESC
        """)
        stats["by_type"] = {row[0] or "untyped": row[1] for row in cursor.fetchall()}
        
        # User-defined types
        stats["user_defined_types"] = self.user_labels
        
        conn.close()
        
        return stats


def main():
    """Test entity extraction"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python entity_extractor.py <db_path> [test_text]")
        sys.exit(1)
    
    db_path = sys.argv[1]
    test_text = sys.argv[2] if len(sys.argv) > 2 else "Met Sarah at the AI conference in Tokyo. She sent me a paper on transformers."
    
    print(f"\n{'='*60}")
    print("ENTITY EXTRACTOR TEST")
    print(f"{'='*60}\n")
    
    extractor = EntityExtractor(db_path)
    
    print(f"Text: {test_text}\n")
    print("Extracting entities...\n")
    
    entities = extractor.extract(test_text, user_tags=["ai", "research"])
    
    print(f"Found {len(entities)} entities:\n")
    
    # Group by type source
    by_source = {}
    for entity in entities:
        source = entity.type_source
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(entity)
    
    for source, ents in by_source.items():
        print(f"{source.upper()}:")
        for ent in ents:
            type_str = f" ({ent.type})" if ent.type else ""
            conf_str = f" [{ent.confidence:.2f}]"
            print(f"  - {ent.text}{type_str}{conf_str}")
        print()
    
    # Show stats
    print(f"{'='*60}")
    stats = extractor.get_extraction_stats()
    print("EXTRACTION STATS:")
    print(f"  Tentative entities: {stats['tentative_count']}")
    print(f"  Confirmed entities: {stats['confirmed_count']}")
    print(f"  User-defined types: {len(stats['user_defined_types'])}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()