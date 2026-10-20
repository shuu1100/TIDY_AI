"""SQLite database configuration and schema initialization for TidyAI."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from backend.app.config import settings


def get_db_path() -> Path:
    """Resolve database path relative to backend root if not absolute."""
    path = Path(settings.database_path)
    if not path.is_absolute():
        # Place relative db files within backend/ directory
        backend_dir = Path(__file__).resolve().parent.parent
        return backend_dir / path
    return path


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager providing a SQLite database connection with row factory."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_db_connection() -> bool:
    """Verify that SQLite can open and perform a read query."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            return cursor.fetchone() is not None
    except Exception:
        return False


def init_db() -> None:
    """Initialize minimal schema for audit history and operations ledger."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Approved roots table (persists user-approved directory boundaries)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approved_roots (
                id TEXT PRIMARY KEY,
                canonical_path TEXT UNIQUE NOT NULL,
                label TEXT NOT NULL,
                added_at TEXT NOT NULL
            )
        """)

        # Operation batches ledger (persists plan executions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operation_batches (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                approved_root TEXT NOT NULL,
                total_items INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                is_dry_run INTEGER NOT NULL DEFAULT 1
            )
        """)
        
        # Individual operation items (tracks per-file move/rename for safe undo)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operation_items (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                source_rel_path TEXT NOT NULL,
                target_rel_path TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                executed_at TEXT,
                FOREIGN KEY (batch_id) REFERENCES operation_batches (id)
            )
        """)
