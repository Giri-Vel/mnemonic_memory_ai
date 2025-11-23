"""
Session management for conversation memory grouping.

Handles:
- Session creation and lifecycle
- Memory-to-session association
- LLM-based summary generation
- Session retrieval and search
"""

import sqlite3
import uuid
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

try:
    from mnemonic.llm_providers import LLMProvider
except ImportError:
    from llm_providers import LLMProvider

logger = logging.getLogger(__name__)


class ConversationSession:
    """Represents a conversation session."""
    
    # Session limits
    SOFT_LIMIT = 30  # Warn user
    HARD_LIMIT = 100  # Force finalize
    
    def __init__(
        self,
        session_id: str,
        start_time: datetime,
        topic: Optional[str] = None,
        summary: Optional[str] = None,
        memory_count: int = 0,
        is_active: bool = True,
        end_time: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a conversation session.
        
        Args:
            session_id: Unique session identifier
            start_time: When session started
            topic: Session topic (optional, can be LLM-suggested)
            summary: LLM-generated summary (populated when finalized)
            memory_count: Number of memories in session
            is_active: Whether session is still accepting memories
            end_time: When session was finalized
            metadata: Additional metadata (JSON)
        """
        self.id = session_id
        self.start_time = start_time
        self.topic = topic
        self.summary = summary
        self.memory_count = memory_count
        self.is_active = is_active
        self.end_time = end_time
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "id": self.id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "topic": self.topic,
            "summary": self.summary,
            "memory_count": self.memory_count,
            "is_active": self.is_active,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        """Create session from dictionary."""
        return cls(
            session_id=data["id"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            topic=data.get("topic"),
            summary=data.get("summary"),
            memory_count=data.get("memory_count", 0),
            is_active=bool(data.get("is_active", True)),
            metadata=data.get("metadata", {})
        )


class SessionStore:
    """Manages session persistence in SQLite."""
    
    def __init__(self, db_path: str):
        """
        Initialize session store.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def create_session(
        self,
        topic: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationSession:
        """
        Create a new active session.
        
        Args:
            topic: Optional topic for the session
            metadata: Optional metadata
        
        Returns:
            Created session
        """
        session = ConversationSession(
            session_id=str(uuid.uuid4()),
            start_time=datetime.now(),
            topic=topic,
            metadata=metadata
        )
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO sessions (
                    id, start_time, topic, is_active, metadata
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                session.id,
                session.start_time.isoformat(),
                session.topic,
                1,  # is_active = True
                json.dumps(session.metadata) if session.metadata else None
            ))
            
            conn.commit()
            logger.info(f"Created session {session.id}" + 
                       (f" (topic: {session.topic})" if session.topic else ""))
            
            return session
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create session: {e}")
            raise
        finally:
            conn.close()
    
    def add_memory_to_session(
        self,
        session_id: str,
        memory_id: int,
        sequence_number: int
    ) -> None:
        """
        Associate a memory with a session.
        
        Args:
            session_id: Session UUID
            memory_id: Memory SQLite row ID
            sequence_number: Order in session
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Add to junction table
            cursor.execute("""
                INSERT INTO session_memories (
                    session_id, memory_id, sequence_number
                ) VALUES (?, ?, ?)
            """, (session_id, memory_id, sequence_number))
            
            # Update session memory count
            cursor.execute("""
                UPDATE sessions
                SET memory_count = memory_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (session_id,))
            
            conn.commit()
            logger.debug(f"Added memory {memory_id} to session {session_id} (seq={sequence_number})")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to add memory to session: {e}")
            raise
        finally:
            conn.close()
    
    def finalize_session(
        self,
        session_id: str,
        summary: str
    ) -> None:
        """
        Finalize a session (mark as inactive, add summary).
        
        Args:
            session_id: Session to finalize
            summary: LLM-generated summary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE sessions
                SET is_active = 0,
                    end_time = ?,
                    summary = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                summary,
                session_id
            ))
            
            conn.commit()
            logger.info(f"Finalized session {session_id}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to finalize session: {e}")
            raise
        finally:
            conn.close()
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session UUID
        
        Returns:
            Session or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, start_time, end_time, topic, summary,
                       memory_count, is_active, metadata
                FROM sessions
                WHERE id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return ConversationSession(
                session_id=row[0],
                start_time=datetime.fromisoformat(row[1]),
                end_time=datetime.fromisoformat(row[2]) if row[2] else None,
                topic=row[3],
                summary=row[4],
                memory_count=row[5],
                is_active=bool(row[6]),
                metadata=json.loads(row[7]) if row[7] else {}
            )
            
        finally:
            conn.close()
    
    def get_active_session(self) -> Optional[ConversationSession]:
        """
        Get the currently active session.
        
        Returns:
            Active session or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, start_time, end_time, topic, summary,
                       memory_count, is_active, metadata
                FROM sessions
                WHERE is_active = 1
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return ConversationSession(
                session_id=row[0],
                start_time=datetime.fromisoformat(row[1]),
                end_time=datetime.fromisoformat(row[2]) if row[2] else None,
                topic=row[3],
                summary=row[4],
                memory_count=row[5],
                is_active=bool(row[6]),
                metadata=json.loads(row[7]) if row[7] else {}
            )
            
        finally:
            conn.close()
    
    def get_session_memories(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get memories for a session in sequence order.
        
        Args:
            session_id: Session UUID
            limit: Optional limit on number of memories (for context)
        
        Returns:
            List of memory dictionaries with content and metadata
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT m.id, m.uuid, m.content, m.created_at, sm.sequence_number
                FROM memories m
                JOIN session_memories sm ON m.id = sm.memory_id
                WHERE sm.session_id = ?
                ORDER BY sm.sequence_number ASC
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, (session_id,))
            
            memories = []
            for row in cursor.fetchall():
                memories.append({
                    "sqlite_id": row[0],
                    "uuid": row[1],
                    "content": row[2],
                    "created_at": row[3],
                    "sequence_number": row[4]
                })
            
            return memories
            
        finally:
            conn.close()
    
    def get_recent_sessions(self, n: int = 10) -> List[ConversationSession]:
        """
        Get recent sessions (active and finalized).
        
        Args:
            n: Number of sessions to retrieve
        
        Returns:
            List of sessions ordered by most recent first
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, start_time, end_time, topic, summary,
                       memory_count, is_active, metadata
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
            """, (n,))
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append(ConversationSession(
                    session_id=row[0],
                    start_time=datetime.fromisoformat(row[1]),
                    end_time=datetime.fromisoformat(row[2]) if row[2] else None,
                    topic=row[3],
                    summary=row[4],
                    memory_count=row[5],
                    is_active=bool(row[6]),
                    metadata=json.loads(row[7]) if row[7] else {}
                ))
            
            return sessions
            
        finally:
            conn.close()
    
    def find_sessions_by_topic(self, topic_query: str) -> List[ConversationSession]:
        """
        Find sessions matching a topic query.
        
        Args:
            topic_query: Topic search string
        
        Returns:
            Matching sessions
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, start_time, end_time, topic, summary,
                       memory_count, is_active, metadata
                FROM sessions
                WHERE topic LIKE ? OR summary LIKE ?
                ORDER BY updated_at DESC
            """, (f"%{topic_query}%", f"%{topic_query}%"))
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append(ConversationSession(
                    session_id=row[0],
                    start_time=datetime.fromisoformat(row[1]),
                    end_time=datetime.fromisoformat(row[2]) if row[2] else None,
                    topic=row[3],
                    summary=row[4],
                    memory_count=row[5],
                    is_active=bool(row[6]),
                    metadata=json.loads(row[7]) if row[7] else {}
                ))
            
            return sessions
            
        finally:
            conn.close()