"""
Database module for storing and querying DQ violations.
"""
import sqlite3
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ViolationsDatabase:
    """SQLite database for storing data quality violations."""
    
    def __init__(self, db_path: str = "/data/violations.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database and create tables."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Create violations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS violations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id TEXT UNIQUE NOT NULL,
                        timestamp TEXT NOT NULL,
                        hour_bucket TEXT NOT NULL,
                        domain TEXT NOT NULL,
                        field TEXT NOT NULL,
                        rule_name TEXT NOT NULL,
                        violation_type TEXT,
                        message TEXT,
                        value TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better query performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_violations_domain 
                    ON violations(domain)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_violations_hour_bucket 
                    ON violations(hour_bucket)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_violations_rule_name 
                    ON violations(rule_name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_violations_timestamp 
                    ON violations(timestamp)
                """)
                
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def insert_violation(self, violation: Dict[str, Any]) -> bool:
        """
        Insert a violation record into the database.
        Uses INSERT OR IGNORE for idempotency.
        
        Args:
            violation: Violation event dictionary
            
        Returns:
            True if inserted, False if duplicate
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR IGNORE INTO violations (
                        message_id, timestamp, hour_bucket, domain, 
                        field, rule_name, violation_type, message, value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    violation.get('message_id'),
                    violation.get('timestamp'),
                    violation.get('hour_bucket'),
                    violation.get('domain'),
                    violation.get('field'),
                    violation.get('rule_name'),
                    violation.get('violation_type'),
                    violation.get('message'),
                    violation.get('value')
                ))
                
                conn.commit()
                
                # Check if row was inserted
                inserted = cursor.rowcount > 0
                
                if inserted:
                    logger.debug(f"Inserted violation: {violation.get('message_id')}")
                else:
                    logger.debug(f"Duplicate violation ignored: {violation.get('message_id')}")
                
                return inserted
                
        except Exception as e:
            logger.error(f"Failed to insert violation: {e}")
            return False
    
    def get_aggregated_report(self) -> List[Dict[str, Any]]:
        """
        Get aggregated violation counts grouped by domain, rule_name, and hour_bucket.
        
        Returns:
            List of aggregated violation records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        domain,
                        rule_name,
                        hour_bucket,
                        COUNT(*) as violation_count
                    FROM violations
                    GROUP BY domain, rule_name, hour_bucket
                    ORDER BY hour_bucket DESC, violation_count DESC
                """)
                
                rows = cursor.fetchall()
                
                return [
                    {
                        "domain": row["domain"],
                        "rule_name": row["rule_name"],
                        "hour_bucket": row["hour_bucket"],
                        "violation_count": row["violation_count"]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Failed to get aggregated report: {e}")
            return []
    
    def get_top_violations(self, hours: int = 24, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top N most frequent violations in the last X hours.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of results to return
            
        Returns:
            List of top violation records
        """
        try:
            # Calculate cutoff timestamp
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            cutoff_str = cutoff_time.isoformat() + "Z"
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        domain,
                        rule_name,
                        COUNT(*) as violation_count,
                        MIN(timestamp) as first_seen,
                        MAX(timestamp) as last_seen
                    FROM violations
                    WHERE timestamp >= ?
                    GROUP BY domain, rule_name
                    ORDER BY violation_count DESC
                    LIMIT ?
                """, (cutoff_str, limit))
                
                rows = cursor.fetchall()
                
                return [
                    {
                        "domain": row["domain"],
                        "rule_name": row["rule_name"],
                        "violation_count": row["violation_count"],
                        "first_seen": row["first_seen"],
                        "last_seen": row["last_seen"]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Failed to get top violations: {e}")
            return []
    
    def get_sample_violations(self, domain: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a sample of raw violation records for a specific domain.
        
        Args:
            domain: Domain name to filter by
            limit: Maximum number of records to return
            
        Returns:
            List of violation records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        message_id,
                        timestamp,
                        domain,
                        field,
                        rule_name,
                        violation_type,
                        message,
                        value
                    FROM violations
                    WHERE domain = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (domain, limit))
                
                rows = cursor.fetchall()
                
                return [
                    {
                        "message_id": row["message_id"],
                        "timestamp": row["timestamp"],
                        "domain": row["domain"],
                        "field": row["field"],
                        "rule_name": row["rule_name"],
                        "violation_type": row["violation_type"],
                        "message": row["message"],
                        "value": row["value"]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Failed to get sample violations: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get overall database statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total violations
                cursor.execute("SELECT COUNT(*) as total FROM violations")
                total = cursor.fetchone()["total"]
                
                # Violations by domain
                cursor.execute("""
                    SELECT domain, COUNT(*) as count 
                    FROM violations 
                    GROUP BY domain
                """)
                by_domain = {row["domain"]: row["count"] for row in cursor.fetchall()}
                
                # Latest violation timestamp
                cursor.execute("SELECT MAX(timestamp) as latest FROM violations")
                latest = cursor.fetchone()["latest"]
                
                return {
                    "total_violations": total,
                    "violations_by_domain": by_domain,
                    "latest_violation": latest
                }
                
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
