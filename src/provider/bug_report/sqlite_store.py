"""SQLite backing store for bug report database.

Provides robust, concurrent, atomic persistence for bug reports,
reproduction steps, attachments, and tracker metadata using SQLite.
"""

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from model.bug_report import (
    BugAttachmentModel,
    BugCategory,
    BugDatabaseModel,
    BugReportModel,
    BugSeverity,
    BugStatus,
)


class SQLiteBugStore:
    """SQLite persistence engine for the bug workstation."""

    def __init__(self, db_path: Path) -> None:
        """Initialize SQLite bug store.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection with foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_schema(self) -> None:
        """Initialize tables and indices if they do not already exist."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bugs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    component TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    reproduction_steps TEXT NOT NULL DEFAULT '[]',
                    expected_behavior TEXT NOT NULL DEFAULT '',
                    actual_behavior TEXT NOT NULL DEFAULT '',
                    logs TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    resolved_at TEXT,
                    resolution_notes TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    bug_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL DEFAULT 'reference',
                    file_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (bug_id) REFERENCES bugs(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_attachments_bug_id ON attachments(bug_id);
                CREATE INDEX IF NOT EXISTS idx_bugs_status ON bugs(status);
                CREATE INDEX IF NOT EXISTS idx_bugs_severity ON bugs(severity);
                """
            )

    def load_database(self) -> BugDatabaseModel:
        """Load full bug database model from SQLite.

        Returns:
            BugDatabaseModel populated with all bugs, attachments, and metadata.
        """
        with self._get_connection() as conn:
            # Load metadata
            meta_rows = conn.execute("SELECT key, value FROM metadata").fetchall()
            meta: Dict[str, str] = {row["key"]: row["value"] for row in meta_rows}
            title = meta.get("title", "Hardware Engineering Bug Tracker")
            summary = meta.get("summary", "")
            updated_at = meta.get("updated_at", "")

            # Load attachments grouped by bug_id
            att_rows = conn.execute(
                "SELECT id, bug_id, filename, file_type, file_path, size_bytes, description, created_at "
                "FROM attachments ORDER BY created_at ASC"
            ).fetchall()
            attachments_by_bug: Dict[str, List[BugAttachmentModel]] = {}
            for row in att_rows:
                att = BugAttachmentModel(
                    id=row["id"],
                    filename=row["filename"],
                    file_type=row["file_type"],
                    file_path=row["file_path"],
                    size_bytes=row["size_bytes"],
                    description=row["description"],
                    created_at=row["created_at"],
                )
                attachments_by_bug.setdefault(row["bug_id"], []).append(att)

            # Load bugs
            bug_rows = conn.execute(
                "SELECT id, title, status, severity, category, component, description, "
                "reproduction_steps, expected_behavior, actual_behavior, logs, created_at, "
                "updated_at, resolved_at, resolution_notes FROM bugs"
            ).fetchall()

            def _sort_key(r: sqlite3.Row) -> int:
                b_id = r["id"]
                if b_id.startswith("BUG-"):
                    try:
                        return int(b_id[4:])
                    except ValueError:
                        pass
                return 999999

            sorted_bug_rows = sorted(bug_rows, key=_sort_key)

            bugs: List[BugReportModel] = []
            for row in sorted_bug_rows:
                steps_raw = row["reproduction_steps"]
                try:
                    steps = json.loads(steps_raw) if steps_raw else []
                except (json.JSONDecodeError, TypeError):
                    steps = []

                bug = BugReportModel(
                    id=row["id"],
                    title=row["title"],
                    status=BugStatus(row["status"]),
                    severity=BugSeverity(row["severity"]),
                    category=BugCategory(row["category"]),
                    component=row["component"] or "",
                    description=row["description"] or "",
                    reproduction_steps=steps,
                    expected_behavior=row["expected_behavior"] or "",
                    actual_behavior=row["actual_behavior"] or "",
                    logs=row["logs"] or "",
                    attachments=attachments_by_bug.get(row["id"], []),
                    created_at=row["created_at"] or "",
                    updated_at=row["updated_at"] or "",
                    resolved_at=row["resolved_at"],
                    resolution_notes=row["resolution_notes"] or "",
                )
                bugs.append(bug)

            return BugDatabaseModel(
                title=title,
                summary=summary,
                bugs=bugs,
                updated_at=updated_at,
            )

    def save_database(self, database: BugDatabaseModel) -> None:
        """Atomically persist entire BugDatabaseModel into SQLite.

        Args:
            database: The bug database model to store.
        """
        with self._get_connection() as conn:
            # 1. Update metadata
            conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('title', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (database.title,),
            )
            conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('summary', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (database.summary,),
            )
            conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('updated_at', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (database.updated_at,),
            )

            # 2. Track existing bug IDs to purge removed bugs
            current_ids = {b.id for b in database.bugs}
            placeholders = ",".join("?" for _ in current_ids) if current_ids else "''"
            conn.execute(f"DELETE FROM bugs WHERE id NOT IN ({placeholders})", list(current_ids))

            # 3. Upsert bugs and attachments
            for bug in database.bugs:
                self._upsert_bug_in_conn(conn, bug)

    def save_bug(self, bug: BugReportModel) -> None:
        """Upsert a single bug report and its attachments.

        Args:
            bug: The bug report model to save.
        """
        with self._get_connection() as conn:
            self._upsert_bug_in_conn(conn, bug)

    def _upsert_bug_in_conn(self, conn: sqlite3.Connection, bug: BugReportModel) -> None:
        """Upsert a single bug in an active database connection."""
        steps_json = json.dumps(bug.reproduction_steps)
        conn.execute(
            """
            INSERT INTO bugs (
                id, title, status, severity, category, component, description,
                reproduction_steps, expected_behavior, actual_behavior, logs,
                created_at, updated_at, resolved_at, resolution_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                status=excluded.status,
                severity=excluded.severity,
                category=excluded.category,
                component=excluded.component,
                description=excluded.description,
                reproduction_steps=excluded.reproduction_steps,
                expected_behavior=excluded.expected_behavior,
                actual_behavior=excluded.actual_behavior,
                logs=excluded.logs,
                created_at=excluded.created_at,
                updated_at=excluded.updated_at,
                resolved_at=excluded.resolved_at,
                resolution_notes=excluded.resolution_notes
            """,
            (
                bug.id,
                bug.title,
                bug.status.value,
                bug.severity.value,
                bug.category.value,
                bug.component,
                bug.description,
                steps_json,
                bug.expected_behavior,
                bug.actual_behavior,
                bug.logs,
                bug.created_at,
                bug.updated_at,
                bug.resolved_at,
                bug.resolution_notes,
            ),
        )

        # Sync attachments
        conn.execute("DELETE FROM attachments WHERE bug_id = ?", (bug.id,))
        for att in bug.attachments:
            conn.execute(
                """
                INSERT INTO attachments (
                    id, bug_id, filename, file_type, file_path, size_bytes, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    att.id,
                    bug.id,
                    att.filename,
                    att.file_type,
                    att.file_path,
                    att.size_bytes,
                    att.description,
                    att.created_at,
                ),
            )

    def delete_bug(self, bug_id: str) -> None:
        """Delete a bug and its associated attachments.

        Args:
            bug_id: Unique bug identifier.
        """
        with self._get_connection() as conn:
            conn.execute("DELETE FROM bugs WHERE id = ?", (bug_id,))

    def import_from_json(self, json_path: Path) -> BugDatabaseModel:
        """Import database from a JSON state file into SQLite.

        Args:
            json_path: Path to the JSON state file.

        Returns:
            The loaded and imported BugDatabaseModel.
        """
        if not json_path.exists():
            raise FileNotFoundError(f"State file not found at {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        db = BugDatabaseModel.model_validate(data)
        self.save_database(db)
        return db

    def export_to_json(self, json_path: Path) -> None:
        """Export SQLite contents to a JSON state file.

        Args:
            json_path: Path to write the JSON state file.
        """
        db = self.load_database()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(db.model_dump(mode="json"), f, indent=2)
