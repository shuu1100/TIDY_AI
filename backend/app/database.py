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


_db_initialized: bool = False


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager providing a SQLite database connection with row factory."""
    global _db_initialized
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if not _db_initialized:
        _db_initialized = True
        _run_init(conn)
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


def _run_init(conn: sqlite3.Connection) -> None:
    """Run table creation and column migrations on an active connection."""
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
            is_dry_run INTEGER NOT NULL DEFAULT 1,
            root_id TEXT,
            undone_at TEXT
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
            is_undone INTEGER DEFAULT 0,
            undone_at TEXT,
            FOREIGN KEY (batch_id) REFERENCES operation_batches (id)
        )
    """)

    # Schema evolution for operation_batches
    try:
        cursor.execute("ALTER TABLE operation_batches ADD COLUMN root_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE operation_batches ADD COLUMN undone_at TEXT")
    except sqlite3.OperationalError:
        pass

    # Schema evolution for operation_items
    try:
        cursor.execute("ALTER TABLE operation_items ADD COLUMN is_undone INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE operation_items ADD COLUMN undone_at TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def init_db() -> None:
    """Initialize minimal schema for audit history and operations ledger."""
    with get_db_connection() as conn:
        _run_init(conn)



# ==============================================================================
# Operations Ledger Database Queries
# ==============================================================================

def record_batch(
    batch_id: str,
    created_at: str,
    approved_root: str,
    total_items: int,
    status: str,
    is_dry_run: bool,
    root_id: str = "",
) -> None:
    """Insert a new operation batch record into the ledger."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO operation_batches (
                id, created_at, approved_root, total_items, status, is_dry_run, root_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                created_at,
                approved_root,
                total_items,
                status,
                1 if is_dry_run else 0,
                root_id,
            ),
        )


def record_batch_items(
    items: list,
) -> None:
    """Insert multiple operation item records into the ledger."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO operation_items (
                id, batch_id, source_rel_path, target_rel_path,
                operation_type, status, error_message, executed_at, is_undone, undone_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["id"],
                    item["batch_id"],
                    item["source_rel_path"],
                    item["target_rel_path"],
                    item["operation_type"],
                    item["status"],
                    item.get("error_message"),
                    item.get("executed_at"),
                    1 if item.get("is_undone") else 0,
                    item.get("undone_at"),
                )
                for item in items
            ],
        )


def get_batches(
    root_path: str = "",
    limit: int = 50,
) -> list:
    """Fetch operation batches ordered by creation timestamp descending."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if root_path:
            cursor.execute(
                """
                SELECT * FROM operation_batches
                WHERE approved_root = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (root_path, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM operation_batches
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [dict(row) for row in cursor.fetchall()]


def get_batch_by_id(batch_id: str) -> dict | None:
    """Retrieve an operation batch by its ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM operation_batches WHERE id = ?",
            (batch_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_items_by_batch_id(batch_id: str) -> list:
    """Retrieve all operation items for a given batch ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM operation_items
            WHERE batch_id = ?
            ORDER BY executed_at ASC
            """,
            (batch_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def update_batch_undo_status(
    batch_id: str,
    status: str,
    undone_at: str,
) -> None:
    """Update status and undone timestamp for a batch."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE operation_batches
            SET status = ?, undone_at = ?
            WHERE id = ?
            """,
            (status, undone_at, batch_id),
        )


def update_item_undo_status(
    item_id: str,
    status: str,
    is_undone: bool,
    error_message: str | None,
    undone_at: str,
) -> None:
    """Update undo status for an individual operation item."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE operation_items
            SET status = ?, is_undone = ?, error_message = ?, undone_at = ?
            WHERE id = ?
            """,
            (status, 1 if is_undone else 0, error_message, undone_at, item_id),
        )

