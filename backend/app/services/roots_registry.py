"""Registry for user-approved directory roots in TidyAI.

Enforces that file scans and subsequent operations are strictly limited to
user-approved directory boundaries.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from backend.app.database import get_db_connection
from backend.app.schemas import ApprovedRoot
from backend.app.services.security import validate_and_canonicalize_root


class RootsRegistry:
    """Manages approved directory roots stored in SQLite."""

    def approve_root(self, raw_path: str, label: Optional[str] = None) -> ApprovedRoot:
        """Validate, canonicalize, and register a new approved root."""
        canonical_path = validate_and_canonicalize_root(raw_path)
        canonical_str = str(canonical_path)

        display_label = (
            label.strip() if label and label.strip() else canonical_path.name or canonical_str
        )

        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Check if this exact canonical path is already registered
            cursor.execute(
                "SELECT id, canonical_path, label, added_at FROM approved_roots WHERE canonical_path = ?",
                (canonical_str,),
            )
            row = cursor.fetchone()
            if row:
                return ApprovedRoot(
                    id=row["id"],
                    canonical_path=row["canonical_path"],
                    label=row["label"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                )

            # Insert new approved root
            root_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            cursor.execute(
                "INSERT INTO approved_roots (id, canonical_path, label, added_at) VALUES (?, ?, ?, ?)",
                (root_id, canonical_str, display_label, now.isoformat()),
            )

            return ApprovedRoot(
                id=root_id,
                canonical_path=canonical_str,
                label=display_label,
                added_at=now,
            )

    def get_root(self, root_id: str) -> Optional[ApprovedRoot]:
        """Retrieve an approved root by its ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, canonical_path, label, added_at FROM approved_roots WHERE id = ?",
                (root_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ApprovedRoot(
                id=row["id"],
                canonical_path=row["canonical_path"],
                label=row["label"],
                added_at=datetime.fromisoformat(row["added_at"]),
            )

    def list_roots(self) -> List[ApprovedRoot]:
        """List all currently approved directory roots."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, canonical_path, label, added_at FROM approved_roots ORDER BY added_at DESC"
            )
            rows = cursor.fetchall()
            return [
                ApprovedRoot(
                    id=r["id"],
                    canonical_path=r["canonical_path"],
                    label=r["label"],
                    added_at=datetime.fromisoformat(r["added_at"]),
                )
                for r in rows
            ]

    def remove_root(self, root_id: str) -> bool:
        """Unregister an approved root by its ID."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM approved_roots WHERE id = ?", (root_id,))
            return cursor.rowcount > 0

    def clear_all(self) -> None:
        """Clear all approved roots (primarily for test fixture cleanup)."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM approved_roots")


roots_registry = RootsRegistry()
