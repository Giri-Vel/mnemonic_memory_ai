"""
Re-extraction Queue Manager

Manages the queue of re-extraction jobs when new entity types are added.

Day 7: Queue infrastructure (add, query, status)
Day 8: Background processing (worker, progress tracking)
"""

import sqlite3
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ReextractionJob:
    """Represents a re-extraction job in the queue"""
    id: int
    type_name: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    queued_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    memories_processed: int = 0
    memories_total: int = 0
    entities_found: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage"""
        if self.memories_total == 0:
            return 0.0
        return (self.memories_processed / self.memories_total) * 100


class ReextractionQueue:
    """
    Manages re-extraction queue operations
    
    Responsibilities:
    - Queue new re-extraction jobs
    - Query job status
    - Update job progress (Day 8)
    - Retrieve pending jobs for processing (Day 8)
    """
    
    def __init__(self, db_path: str):
        """
        Initialize queue manager
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def add_job(self, type_name: str) -> int:
        """
        Add a new re-extraction job to the queue
        
        Args:
            type_name: Entity type to re-extract
        
        Returns:
            Job ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO reextraction_queue (type_name, status)
                VALUES (?, 'pending')
            """, (type_name,))
            
            job_id = cursor.lastrowid
            conn.commit()
            
            return job_id
            
        finally:
            conn.close()
    
    def get_job(self, job_id: int) -> Optional[ReextractionJob]:
        """
        Get a specific job by ID
        
        Args:
            job_id: Job identifier
        
        Returns:
            ReextractionJob object or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM reextraction_queue
            WHERE id = ?
        """, (job_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return ReextractionJob(
            id=row['id'],
            type_name=row['type_name'],
            status=row['status'],
            queued_at=row['queued_at'],
            started_at=row['started_at'],
            completed_at=row['completed_at'],
            memories_processed=row['memories_processed'],
            memories_total=row['memories_total'],
            entities_found=row['entities_found'],
            error_message=row['error_message']
        )
    
    def get_pending_jobs(self) -> List[ReextractionJob]:
        """
        Get all pending jobs (for Day 8 background worker)
        
        Returns:
            List of pending ReextractionJob objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM reextraction_queue
            WHERE status = 'pending'
            ORDER BY queued_at ASC
        """)
        
        jobs = []
        for row in cursor.fetchall():
            jobs.append(ReextractionJob(
                id=row['id'],
                type_name=row['type_name'],
                status=row['status'],
                queued_at=row['queued_at'],
                started_at=row['started_at'],
                completed_at=row['completed_at'],
                memories_processed=row['memories_processed'],
                memories_total=row['memories_total'],
                entities_found=row['entities_found'],
                error_message=row['error_message']
            ))
        
        conn.close()
        return jobs
    
    def get_queue_status(self) -> Dict[str, int]:
        """
        Get overview of queue status
        
        Returns:
            Dictionary with counts by status
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM reextraction_queue
            GROUP BY status
        """)
        
        status_counts = {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0
        }
        
        for row in cursor.fetchall():
            status_counts[row['status']] = row['count']
        
        conn.close()
        return status_counts
    
    def get_recent_jobs(self, limit: int = 10) -> List[ReextractionJob]:
        """
        Get recent jobs (for display)
        
        Args:
            limit: Number of jobs to return
        
        Returns:
            List of recent ReextractionJob objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM reextraction_queue
            ORDER BY queued_at DESC
            LIMIT ?
        """, (limit,))
        
        jobs = []
        for row in cursor.fetchall():
            jobs.append(ReextractionJob(
                id=row['id'],
                type_name=row['type_name'],
                status=row['status'],
                queued_at=row['queued_at'],
                started_at=row['started_at'],
                completed_at=row['completed_at'],
                memories_processed=row['memories_processed'],
                memories_total=row['memories_total'],
                entities_found=row['entities_found'],
                error_message=row['error_message']
            ))
        
        conn.close()
        return jobs
    
    # Day 8 methods (infrastructure ready, will be used by background worker)
    
    def start_job(self, job_id: int, memories_total: int) -> bool:
        """
        Mark a job as started (Day 8)
        
        Args:
            job_id: Job identifier
            memories_total: Total number of memories to process
        
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE reextraction_queue
                SET status = 'processing',
                    started_at = CURRENT_TIMESTAMP,
                    memories_total = ?
                WHERE id = ?
            """, (memories_total, job_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"✗ Failed to start job {job_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def update_progress(self, job_id: int, memories_processed: int, entities_found: int) -> bool:
        """
        Update job progress (Day 8)
        
        Args:
            job_id: Job identifier
            memories_processed: Number of memories processed so far
            entities_found: Number of entities found so far
        
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE reextraction_queue
                SET memories_processed = ?,
                    entities_found = ?
                WHERE id = ?
            """, (memories_processed, entities_found, job_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"✗ Failed to update progress for job {job_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def complete_job(self, job_id: int, entities_found: int) -> bool:
        """
        Mark a job as completed (Day 8)
        
        Args:
            job_id: Job identifier
            entities_found: Total entities found
        
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE reextraction_queue
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    entities_found = ?
                WHERE id = ?
            """, (entities_found, job_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"✗ Failed to complete job {job_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def fail_job(self, job_id: int, error_message: str) -> bool:
        """
        Mark a job as failed (Day 8)
        
        Args:
            job_id: Job identifier
            error_message: Error description
        
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE reextraction_queue
                SET status = 'failed',
                    completed_at = CURRENT_TIMESTAMP,
                    error_message = ?
                WHERE id = ?
            """, (error_message, job_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"✗ Failed to mark job {job_id} as failed: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


def main():
    """Test re-extraction queue"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python reextraction_queue.py <db_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    print(f"\n{'='*60}")
    print("RE-EXTRACTION QUEUE TEST")
    print(f"{'='*60}\n")
    
    queue = ReextractionQueue(db_path)
    
    # Test adding a job
    print("Adding test job...")
    job_id = queue.add_job("anime")
    print(f"✓ Job added with ID: {job_id}\n")
    
    # Test getting job
    print("Retrieving job...")
    job = queue.get_job(job_id)
    if job:
        print(f"✓ Job retrieved:")
        print(f"  ID: {job.id}")
        print(f"  Type: {job.type_name}")
        print(f"  Status: {job.status}")
        print(f"  Queued: {job.queued_at}\n")
    
    # Test queue status
    print("Queue status:")
    status = queue.get_queue_status()
    for stat, count in status.items():
        print(f"  {stat}: {count}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()