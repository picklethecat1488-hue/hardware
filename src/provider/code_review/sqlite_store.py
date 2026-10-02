"""SQLite backing store for code review database.

Provides robust, concurrent, atomic persistence for code review sessions,
file review statuses, inline comments, and review findings using SQLite.
"""

import contextlib
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Dict, Generator, List, Optional
import uuid as uuid_pkg

from model.code_review import (
    CommentModel,
    CommitUpdateModel,
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

    @contextlib.contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Create, configure, and safely close a SQLite connection with foreign keys enabled."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        self._ensure_schema(conn)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        """Ensure schema tables and indices exist in connection."""
        cursor = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='commit_updates'")
        if not cursor.fetchone():
            self._init_schema_with_conn(conn)
            return
        cursor = conn.execute("PRAGMA table_info(comments)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "uuid" not in cols or "commit_hash" not in cols:
            self._init_schema_with_conn(conn)

    def _init_schema(self) -> None:
        """Initialize tables and indices if they do not already exist."""
        with self._get_connection():
            pass

    def _init_schema_with_conn(self, conn: sqlite3.Connection) -> None:
        """Execute table creation and migrations on connection."""
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
                uuid TEXT,
                commit_hash TEXT NOT NULL DEFAULT '',
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

            CREATE TABLE IF NOT EXISTS commit_updates (
                id TEXT PRIMARY KEY,
                session_uuid TEXT NOT NULL,
                original_commit TEXT NOT NULL,
                current_commit TEXT NOT NULL,
                action TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_comments_file_path ON comments(file_path);
            CREATE INDEX IF NOT EXISTS idx_comments_severity ON comments(severity);
            CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
            CREATE INDEX IF NOT EXISTS idx_commit_updates_session ON commit_updates(session_uuid);
            """
        )
        # Ensure uuid and commit_hash columns exist on preexisting comments table
        cursor = conn.execute("PRAGMA table_info(comments)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "uuid" not in cols:
            conn.execute("ALTER TABLE comments ADD COLUMN uuid TEXT")
        if "commit_hash" not in cols:
            conn.execute("ALTER TABLE comments ADD COLUMN commit_hash TEXT NOT NULL DEFAULT ''")

        # Backfill missing UUIDs on comments
        null_uuid_rows = conn.execute("SELECT id FROM comments WHERE uuid IS NULL OR uuid = ''").fetchall()
        for r in null_uuid_rows:
            conn.execute("UPDATE comments SET uuid = ? WHERE id = ?", (str(uuid_pkg.uuid4()), r["id"]))

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_comments_uuid ON comments(uuid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_commit ON comments(commit_hash)")

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
            session_uuid = meta.get("uuid", str(uuid_pkg.uuid4()))
            commit_hash = meta.get("commit_hash")
            original_commit = meta.get("original_commit")
            update_action = meta.get("update_action")
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

            # Load commit updates
            update_rows = conn.execute(
                "SELECT id, session_uuid, original_commit, current_commit, action, notes, timestamp "
                "FROM commit_updates ORDER BY timestamp ASC"
            ).fetchall()
            commit_history: List[CommitUpdateModel] = [
                CommitUpdateModel(
                    id=ur["id"],
                    session_uuid=ur["session_uuid"],
                    original_commit=ur["original_commit"],
                    current_commit=ur["current_commit"],
                    action=ur["action"],
                    notes=ur["notes"] or "",
                    timestamp=ur["timestamp"],
                )
                for ur in update_rows
            ]

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
                "SELECT id, uuid, commit_hash, file_path, start_line, end_line, severity, body, author, "
                "code_snippet, created_at, resolved FROM comments ORDER BY created_at ASC"
            ).fetchall()
            comments: List[CommentModel] = []
            for row in comment_rows:
                sev_str = row["severity"]
                try:
                    sev = ReviewSeverity(sev_str)
                except ValueError:
                    sev = ReviewSeverity.MUST_FIX

                c_uuid = row["uuid"] if ("uuid" in row.keys() and row["uuid"]) else str(uuid_pkg.uuid4())
                c_commit = row["commit_hash"] if ("commit_hash" in row.keys() and row["commit_hash"]) else ""
                comment = CommentModel(
                    id=row["id"],
                    uuid=c_uuid,
                    file_path=row["file_path"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    severity=sev,
                    body=row["body"],
                    author=row["author"] or "Reviewer",
                    code_snippet=row["code_snippet"] or "",
                    created_at=row["created_at"] or "",
                    resolved=bool(row["resolved"]),
                    commit=c_commit,
                )
                comments.append(comment)

            return ReviewSessionModel(
                title=title,
                uuid=session_uuid,
                commit_hash=commit_hash,
                original_commit=original_commit,
                update_action=update_action,
                commit_history=commit_history,
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
                ("uuid", session.uuid),
                ("commit_hash", session.commit_hash or ""),
                ("original_commit", session.original_commit or ""),
                ("update_action", session.update_action or ""),
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

            # 2. Sync commit updates
            for upd in session.commit_history:
                conn.execute(
                    """
                    INSERT INTO commit_updates (id, session_uuid, original_commit, current_commit, action, notes, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        original_commit=excluded.original_commit,
                        current_commit=excluded.current_commit,
                        action=excluded.action,
                        notes=excluded.notes,
                        timestamp=excluded.timestamp
                    """,
                    (
                        upd.id,
                        upd.session_uuid or session.uuid,
                        upd.original_commit,
                        upd.current_commit,
                        upd.action,
                        upd.notes,
                        upd.timestamp,
                    ),
                )

            # 3. Sync files
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

            # 4. Sync comments: scope deletion to session's revisions or commit to avoid deleting other commits' comments (BUG-236)
            current_cids = {c.id for c in session.comments}
            scope_commits = list(session.revisions) if session.revisions else []
            if session.commit_hash and session.commit_hash not in scope_commits:
                scope_commits.append(session.commit_hash)

            if scope_commits:
                commit_placeholders = ",".join("?" for _ in scope_commits)
                if current_cids:
                    placeholders = ",".join("?" for _ in current_cids)
                    conn.execute(
                        f"DELETE FROM comments WHERE (commit_hash IN ({commit_placeholders}) OR commit_hash = '') AND id NOT IN ({placeholders})",
                        scope_commits + list(current_cids),
                    )
                else:
                    conn.execute(
                        f"DELETE FROM comments WHERE commit_hash IN ({commit_placeholders}) OR commit_hash = ''",
                        scope_commits,
                    )
            else:
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
        c_uuid = comment.uuid or str(uuid_pkg.uuid4())
        existing = conn.execute(
            "SELECT id, uuid FROM comments WHERE uuid = ? OR id = ?",
            (c_uuid, comment.id),
        ).fetchone()

        if existing:
            target_id = existing["id"]
            if comment.id and comment.id != target_id:
                id_conflict = conn.execute(
                    "SELECT 1 FROM comments WHERE id = ? AND id != ?",
                    (comment.id, target_id),
                ).fetchone()
                if not id_conflict:
                    target_id = comment.id

            conn.execute(
                """
                UPDATE comments SET
                    id = ?,
                    uuid = ?,
                    commit_hash = ?,
                    file_path = ?,
                    start_line = ?,
                    end_line = ?,
                    severity = ?,
                    body = ?,
                    author = ?,
                    code_snippet = ?,
                    created_at = ?,
                    resolved = ?
                WHERE id = ?
                """,
                (
                    target_id,
                    c_uuid,
                    comment.commit or "",
                    comment.file_path,
                    comment.start_line,
                    comment.end_line,
                    comment.severity.value,
                    comment.body,
                    comment.author,
                    comment.code_snippet,
                    comment.created_at,
                    1 if comment.resolved else 0,
                    existing["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO comments (
                    id, uuid, commit_hash, file_path, start_line, end_line, severity, body,
                    author, code_snippet, created_at, resolved
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comment.id,
                    c_uuid,
                    comment.commit or "",
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

    def record_commit_update(
        self,
        session_uuid: str,
        original_commit: str,
        current_commit: str,
        action: str,
        notes: str = "",
    ) -> CommitUpdateModel:
        """Record and persist a commit update event (rebase, merge, amend, etc.).

        Args:
            session_uuid: UUID of the associated review session.
            original_commit: Pre-update commit hash or reference.
            current_commit: Post-update commit hash or reference.
            action: Update action performed (e.g. 'rebase', 'merge', 'update').
            notes: Optional explanatory notes.

        Returns:
            The created and persisted CommitUpdateModel.
        """
        update = CommitUpdateModel(
            session_uuid=session_uuid,
            original_commit=original_commit,
            current_commit=current_commit,
            action=action,
            notes=notes,
        )
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO commit_updates (id, session_uuid, original_commit, current_commit, action, notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    original_commit=excluded.original_commit,
                    current_commit=excluded.current_commit,
                    action=excluded.action,
                    notes=excluded.notes,
                    timestamp=excluded.timestamp
                """,
                (
                    update.id,
                    update.session_uuid,
                    update.original_commit,
                    update.current_commit,
                    update.action,
                    update.notes,
                    update.timestamp,
                ),
            )
            # Also update session metadata
            conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('commit_hash', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (current_commit,),
            )
            conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('original_commit', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (original_commit,),
            )
            conn.execute(
                "INSERT INTO metadata (key, value) VALUES ('update_action', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (action,),
            )
        return update

    def get_commit_history(self, session_uuid: Optional[str] = None) -> List[CommitUpdateModel]:
        """Query stored commit updates, optionally filtered by session UUID.

        Args:
            session_uuid: Optional session UUID to filter records.

        Returns:
            List of CommitUpdateModel objects ordered chronologically.
        """
        with self._get_connection() as conn:
            if session_uuid:
                rows = conn.execute(
                    "SELECT id, session_uuid, original_commit, current_commit, action, notes, timestamp "
                    "FROM commit_updates WHERE session_uuid = ? ORDER BY timestamp ASC",
                    (session_uuid,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, session_uuid, original_commit, current_commit, action, notes, timestamp "
                    "FROM commit_updates ORDER BY timestamp ASC"
                ).fetchall()
            return [
                CommitUpdateModel(
                    id=r["id"],
                    session_uuid=r["session_uuid"],
                    original_commit=r["original_commit"],
                    current_commit=r["current_commit"],
                    action=r["action"],
                    notes=r["notes"] or "",
                    timestamp=r["timestamp"],
                )
                for r in rows
            ]

    def get_comment_by_uuid(self, comment_uuid: str) -> Optional[CommentModel]:
        """Find a comment by its unique UUID in SQLite.

        Args:
            comment_uuid: Unique UUID of comment to find.

        Returns:
            CommentModel if found, else None.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id, uuid, commit_hash, file_path, start_line, end_line, severity, body, author, "
                "code_snippet, created_at, resolved FROM comments WHERE uuid = ?",
                (comment_uuid,),
            ).fetchone()
            if not row:
                return None
            try:
                sev = ReviewSeverity(row["severity"])
            except ValueError:
                sev = ReviewSeverity.MUST_FIX
            c_commit = row["commit_hash"] if ("commit_hash" in row.keys() and row["commit_hash"]) else ""
            return CommentModel(
                id=row["id"],
                uuid=row["uuid"] or comment_uuid,
                file_path=row["file_path"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                severity=sev,
                body=row["body"],
                author=row["author"] or "Reviewer",
                code_snippet=row["code_snippet"] or "",
                created_at=row["created_at"] or "",
                resolved=bool(row["resolved"]),
                commit=c_commit,
            )
