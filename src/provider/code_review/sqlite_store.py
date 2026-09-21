"""SQLite backing store for code review database.

Provides robust, concurrent, atomic persistence for code review sessions,
file review statuses, inline comments, and review findings using SQLite.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional

from model.code_review import (
    CommentModel,
    FileReviewStatus,
    FileStateModel,
    ReviewSessionModel,
    ReviewSeverity,
    ReviewStatus,
)


class SQLiteReviewStore:
    """SQLite persistence engine for the code review workstation."""

    def __init__(self, db_path: Path) -> None:
        """Initialize SQLite review store.

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

                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    notes TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS comments (
                    id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    body TEXT NOT NULL,
                    author TEXT NOT NULL DEFAULT 'Reviewer',
                    code_snippet TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    resolved INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_comments_file_path ON comments(file_path);
                CREATE INDEX IF NOT EXISTS idx_comments_severity ON comments(severity);
                CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
                """
            )

    def load_session(self) -> Optional[ReviewSessionModel]:
        """Load full review session model from SQLite.

        Returns:
            ReviewSessionModel if records exist, otherwise None.
        """
        with self._get_connection() as conn:
            # Check if metadata exists
            meta_rows = conn.execute("SELECT key, value FROM metadata").fetchall()
            if not meta_rows:
                return None

            meta: Dict[str, str] = {row["key"]: row["value"] for row in meta_rows}
            title = meta.get("title", "Code Review")
            summary = meta.get("summary", "")
            verdict_str = meta.get("verdict", ReviewStatus.IN_REVIEW.value)
            try:
                verdict = ReviewStatus(verdict_str)
            except ValueError:
                verdict = ReviewStatus.IN_REVIEW

            repo_name = meta.get("repo_name", "hardware")
            revs_raw = meta.get("revisions", "[]")
            try:
                revisions = json.loads(revs_raw) if revs_raw else []
            except (json.JSONDecodeError, TypeError):
                revisions = []

            created_at = meta.get("created_at", "")
            updated_at = meta.get("updated_at", "")

            # Load file states
            file_rows = conn.execute("SELECT path, status, notes FROM files ORDER BY path ASC").fetchall()
            files: Dict[str, FileStateModel] = {}
            for row in file_rows:
                stat_str = row["status"]
                try:
                    f_stat = FileReviewStatus(stat_str)
                except ValueError:
                    f_stat = FileReviewStatus.PENDING
                files[row["path"]] = FileStateModel(
                    path=row["path"],
                    status=f_stat,
                    notes=row["notes"] or "",
                )

            # Load comments
            comment_rows = conn.execute(
                "SELECT id, file_path, start_line, end_line, severity, body, author, "
                "code_snippet, created_at, resolved FROM comments ORDER BY created_at ASC"
            ).fetchall()
            comments: List[CommentModel] = []
            for row in comment_rows:
                sev_str = row["severity"]
                try:
                    sev = ReviewSeverity(sev_str)
                except ValueError:
                    sev = ReviewSeverity.MUST_FIX

                comment = CommentModel(
                    id=row["id"],
                    file_path=row["file_path"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    severity=sev,
                    body=row["body"],
                    author=row["author"] or "Reviewer",
                    code_snippet=row["code_snippet"] or "",
                    created_at=row["created_at"] or "",
                    resolved=bool(row["resolved"]),
                )
                comments.append(comment)

            return ReviewSessionModel(
                title=title,
                summary=summary,
                verdict=verdict,
                repo_name=repo_name,
                revisions=revisions,
                files=files,
                comments=comments,
                created_at=created_at,
                updated_at=updated_at,
            )

    def save_session(self, session: ReviewSessionModel) -> None:
        """Atomically persist entire ReviewSessionModel into SQLite.

        Args:
            session: The review session model to store.
        """
        with self._get_connection() as conn:
            # 1. Update metadata
            revs_json = json.dumps(session.revisions)
            meta_entries = [
                ("title", session.title),
                ("summary", session.summary),
                ("verdict", session.verdict.value),
                ("repo_name", session.repo_name),
                ("revisions", revs_json),
                ("created_at", session.created_at),
                ("updated_at", session.updated_at),
            ]
            for key, val in meta_entries:
                conn.execute(
                    "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, val),
                )

            # 2. Sync files
            current_paths = set(session.files.keys())
            if current_paths:
                placeholders = ",".join("?" for _ in current_paths)
                conn.execute(f"DELETE FROM files WHERE path NOT IN ({placeholders})", list(current_paths))
            else:
                conn.execute("DELETE FROM files")

            for f_state in session.files.values():
                conn.execute(
                    "INSERT INTO files (path, status, notes) VALUES (?, ?, ?) "
                    "ON CONFLICT(path) DO UPDATE SET status=excluded.status, notes=excluded.notes",
                    (f_state.path, f_state.status.value, f_state.notes),
                )

            # 3. Sync comments
            current_cids = {c.id for c in session.comments}
            if current_cids:
                placeholders = ",".join("?" for _ in current_cids)
                conn.execute(f"DELETE FROM comments WHERE id NOT IN ({placeholders})", list(current_cids))
            else:
                conn.execute("DELETE FROM comments")

            for c in session.comments:
                self._upsert_comment_in_conn(conn, c)

    def save_comment(self, comment: CommentModel) -> None:
        """Upsert a single review comment.

        Args:
            comment: The comment model to save.
        """
        with self._get_connection() as conn:
            self._upsert_comment_in_conn(conn, comment)

    def _upsert_comment_in_conn(self, conn: sqlite3.Connection, comment: CommentModel) -> None:
        """Upsert a single comment in an active database connection."""
        conn.execute(
            """
            INSERT INTO comments (
                id, file_path, start_line, end_line, severity, body,
                author, code_snippet, created_at, resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                file_path=excluded.file_path,
                start_line=excluded.start_line,
                end_line=excluded.end_line,
                severity=excluded.severity,
                body=excluded.body,
                author=excluded.author,
                code_snippet=excluded.code_snippet,
                created_at=excluded.created_at,
                resolved=excluded.resolved
            """,
            (
                comment.id,
                comment.file_path,
                comment.start_line,
                comment.end_line,
                comment.severity.value,
                comment.body,
                comment.author,
                comment.code_snippet,
                comment.created_at,
                1 if comment.resolved else 0,
            ),
        )

    def delete_comment(self, comment_id: str) -> None:
        """Delete a comment by its unique ID.

        Args:
            comment_id: Unique comment identifier.
        """
        with self._get_connection() as conn:
            conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))

    def save_file_state(self, file_state: FileStateModel) -> None:
        """Upsert a single file review state.

        Args:
            file_state: The file state model to save.
        """
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO files (path, status, notes) VALUES (?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET status=excluded.status, notes=excluded.notes",
                (file_state.path, file_state.status.value, file_state.notes),
            )

    def update_verdict(self, verdict: ReviewStatus, summary: Optional[str] = None) -> None:
        """Update review verdict and optional summary in metadata.

        Args:
            verdict: The review status verdict.
            summary: Optional executive summary text.
        """
        with self._get_connection() as conn:
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('verdict', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (verdict.value,),
            )
            conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('updated_at', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (now_iso,),
            )
            if summary is not None:
                conn.execute(
                    "INSERT INTO metadata (key, value) VALUES ('summary', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (summary,),
                )

    def import_from_json(self, json_path: Path) -> ReviewSessionModel:
        """Import review session from a JSON state file into SQLite.

        Args:
            json_path: Path to the JSON state file.

        Returns:
            The loaded and imported ReviewSessionModel.
        """
        if not json_path.exists():
            raise FileNotFoundError(f"State file not found at {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        session = ReviewSessionModel.model_validate(data)
        self.save_session(session)
        return session

    def export_to_json(self, json_path: Path) -> None:
        """Export SQLite contents to a JSON state file.

        Args:
            json_path: Path to write the JSON state file.
        """
        session = self.load_session()
        if session is None:
            return
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(session.model_dump(mode="json"), f, indent=2)
