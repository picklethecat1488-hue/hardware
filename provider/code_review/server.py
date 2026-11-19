"""HTTP server and REST API for interactive code review web UI.

Serves the Quake-themed code review dashboard and handles JSON API endpoints
for file diffs, commit inspection, inline commenting, review status updates,
and automated Markdown persistence.
"""

from datetime import datetime, timezone
import json
import mimetypes
import os
from pathlib import Path
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
import uuid

import jinja2

from model.code_review import (
    CommentModel,
    CommentStatus,
    FileReviewStatus,
    ReviewSessionModel,
    ReviewSeverity,
    ReviewStatus,
)
from provider.vcs.git_engine import (
    GitEngine,
    extract_line_snippet,
    get_git_root,
)
from provider.code_review.markdown_exporter import MarkdownReviewExporter, comment_matches_revisions
from provider.code_review.sqlite_store import SQLiteReviewStore
from provider.sanitizer import elide_personal_info, get_author_blacklist


class ReviewRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler dispatching review API endpoints and dashboard UI."""

    server: "ReviewServer"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Suppress default HTTP server logging to preserve clean console output."""
        return

    def do_GET(self) -> None:  # noqa: N802
        """Route GET requests for UI dashboard and data query endpoints."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/js/") or path.startswith("/static/"):
            self._handle_serve_static(path)
            return

        if path in ("/favicon.ico", "/favicon.svg"):
            self._handle_serve_static("/static/favicon.svg")
            return

        now = time.time()
        if now - getattr(self.server, "_last_watch_check", 0.0) >= 2.0:
            self.server._last_watch_check = now
            self.server.check_file_watch()

        match path:
            case "/":
                self._handle_serve_ui()
            case "/api/session":
                self._send_json(self.server.session.model_dump(mode="json"))
            case "/api/commits":
                commits = self.server.git_engine.get_commits(rev_args=self.server.session.revisions)
                self._send_json([c.model_dump(mode="json") for c in commits])
            case "/api/files":
                commit = query.get("commit", ["working"])[0]
                files = self.server.git_engine.get_changed_files(commit)
                self._send_json(files)
            case "/api/diff":
                commit = query.get("commit", ["working"])[0]
                file_path = query.get("file", [""])[0]
                if not file_path:
                    self._send_json({"error": "Missing file parameter"}, status=400)
                    return
                diff_model = self.server.git_engine.get_file_diff(commit, file_path)
                self._send_json(diff_model.model_dump(mode="json"))
            case "/api/search":
                q = query.get("q", [""])[0]
                commit = query.get("commit", ["working"])[0]
                current_file = query.get("file", [""])[0]
                results = self.server.git_engine.search_code(q, commit=commit, current_file=current_file)
                self._send_json({"query": q, "commit": commit, "current_file": current_file, "results": results})
            case "/api/raw":
                commit = query.get("commit", ["working"])[0]
                file_path = query.get("file", [""])[0]
                side = query.get("side", ["new"])[0]
                if not file_path:
                    self._send_json({"error": "Missing file parameter"}, status=400)
                    return
                parent = side == "old"
                raw_bytes = self.server.git_engine.get_file_bytes(commit, file_path, parent=parent)
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(raw_bytes)))
                filename = Path(file_path).name
                self.send_header("Content-Disposition", f'inline; filename="{filename}"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(raw_bytes)
            case _:
                self.send_error(404, "Endpoint not found")

    def do_POST(self) -> None:  # noqa: N802
        """Route POST requests for state modifications and Markdown exports."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        match path:
            case "/api/comment":
                if "id" in data and "body" in data and not data.get("file_path"):
                    self._handle_edit_comment(data)
                else:
                    self._handle_add_comment(data)
            case "/api/comment/edit":
                self._handle_edit_comment(data)
            case "/api/comment/status" | "/api/review/comment/status":
                self._handle_update_comment_status(data)
            case "/api/file_status":
                self._handle_update_file_status(data)
            case "/api/verdict":
                self._handle_update_verdict(data)
            case "/api/export":
                self._handle_export()
            case "/api/sync_feedback":
                res = self.server.sync_feedback()
                self._send_json(res)
            case "/api/commit_update":
                self._handle_commit_update(data)
            case "/api/commit_reviewed":
                query = urllib.parse.parse_qs(parsed.query)
                commit = query.get("commit", [""])[0] or (data.get("commit", "") if isinstance(data, dict) else "")
                short_rev = commit[:8] if commit else "current"
                print(
                    f"\n[CodeReview] ✨ All changed files reviewed for commit {short_rev}! Ready to move to the next commit.\n",
                    flush=True,
                )
                self._send_json({"status": "ok", "commit": commit})
            case _:
                self.send_error(404, "Endpoint not found")

    def do_DELETE(self) -> None:  # noqa: N802
        """Route DELETE requests for removing comments."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        match path:
            case "/api/comment":
                cid = query.get("id", [""])[0]
                if not cid:
                    self._send_json({"error": "Missing id parameter"}, status=400)
                    return
                self.server.session.comments = [c for c in self.server.session.comments if c.id != cid]
                self.server.save_and_sync()
                self._send_json({"status": "ok", "deleted": cid})
            case _:
                self.send_error(404, "Endpoint not found")

    def _handle_serve_ui(self) -> None:
        """Render and return Jinja2 review dashboard template."""
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        template = env.get_template("code_review.html.j2")
        if hasattr(self.server, "session") and self.server.session:
            if not self.server.session.author_blacklist:
                self.server.session.author_blacklist = get_author_blacklist()
        html_out = template.render(session=self.server.session)

        encoded = html_out.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _handle_serve_static(self, path: str) -> None:
        """Serve ES modules from js/ and static assets from js/static/."""
        from provider.http_static import get_hardware_js_root, serve_static_asset

        serve_static_asset(self, path, js_root=get_hardware_js_root(), cache_control="no-cache")

    def _handle_add_comment(self, data: dict) -> None:
        """Create and append a new line comment to the review session."""
        file_path = data.get("file_path", "")
        start_line = int(data.get("start_line", 1))
        end_line = int(data.get("end_line", start_line))
        sev_raw = str(data.get("severity", "MUST_FIX")).strip().upper().replace(" ", "_").replace("-", "_")
        match sev_raw:
            case "MUST_FIX" | "MUSTFIX" | "FIX" | "MF":
                severity = ReviewSeverity.MUST_FIX
            case "PROPOSAL" | "PROP":
                severity = ReviewSeverity.PROPOSAL
            case "NIT":
                severity = ReviewSeverity.NIT
            case _:
                severity = ReviewSeverity.MUST_FIX
        body = data.get("body", "").strip()
        author = data.get("author", "Reviewer").strip() or "Reviewer"

        if not file_path or not body:
            self._send_json({"error": "Missing file_path or comment body"}, status=400)
            return

        snippet = data.get("code_snippet")
        if not snippet:
            commit = data.get("commit", "working")
            snippet = extract_line_snippet(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                commit=commit,
                repo_root=self.server.repo_root,
            )

        commit = data.get("commit", self.server.session.commit_hash or "working")
        c_uuid = str(data.get("uuid") or uuid.uuid4())
        cid = str(data.get("id") or c_uuid[:8])
        comment = CommentModel(
            id=cid,
            uuid=c_uuid,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            severity=severity,
            body=body,
            author=author,
            code_snippet=snippet,
            created_at=datetime.now(timezone.utc).isoformat(),
            commit=commit,
        )

        self.server.session.comments.append(comment)
        self.server.session.auto_update_status_on_comment()
        self.server.save_and_sync()
        self._send_json(
            {"status": "ok", "comment": comment.model_dump(mode="json"), "verdict": self.server.session.verdict.value}
        )

    def _handle_edit_comment(self, data: dict) -> None:
        """Edit body and optional severity or status of an existing comment."""
        cid = data.get("id", "").strip()
        new_body = elide_personal_info(data.get("body", "").strip())
        if not cid or not new_body:
            self._send_json({"error": "Missing id or body"}, status=400)
            return

        for comment in self.server.session.comments:
            if comment.id == cid:
                comment.body = new_body
                if "severity" in data:
                    sev_raw = str(data["severity"]).strip().upper().replace(" ", "_").replace("-", "_")
                    match sev_raw:
                        case "MUST_FIX" | "MUSTFIX" | "FIX" | "MF":
                            comment.severity = ReviewSeverity.MUST_FIX
                        case "PROPOSAL" | "PROP":
                            comment.severity = ReviewSeverity.PROPOSAL
                        case "NIT":
                            comment.severity = ReviewSeverity.NIT
                if "status" in data:
                    try:
                        comment.set_status(CommentStatus(str(data["status"]).strip().upper()))
                    except ValueError:
                        pass
                elif "resolved" in data:
                    comment.set_status(CommentStatus.RESOLVED if data["resolved"] else CommentStatus.OPEN)
                self.server.save_and_sync()
                self._send_json({"status": "ok", "comment": comment.model_dump(mode="json")})
                return

        self._send_json({"error": f"Comment {cid} not found"}, status=404)

    def _handle_update_comment_status(self, data: dict) -> None:
        """Transition a review comment between OPEN, RESOLVED, and CLOSED states."""
        cid = str(data.get("id", "")).strip()
        status_raw = str(data.get("status", "")).strip().upper()
        notes = data.get("notes")
        if not cid or not status_raw:
            self._send_json({"error": "Missing id or status parameter"}, status=400)
            return
        try:
            target_status = CommentStatus(status_raw)
        except ValueError:
            self._send_json({"error": f"Invalid comment status: {status_raw}"}, status=400)
            return

        updated = self.server.update_comment_status(cid, target_status, notes=notes)
        if updated is None:
            self._send_json({"error": f"Comment {cid} not found"}, status=404)
            return
        self._send_json(
            {
                "status": "ok",
                "comment": updated.model_dump(mode="json"),
                "verdict": self.server.session.verdict.value,
            }
        )

    def _handle_update_file_status(self, data: dict) -> None:
        """Update reviewed status and optional notes for a file."""
        file_path = data.get("path", "")
        status_str = data.get("status", "PENDING").upper()
        notes = data.get("notes", "")

        if not file_path:
            self._send_json({"error": "Missing path parameter"}, status=400)
            return

        file_state = self.server.session.get_file_state(file_path)
        file_state.status = getattr(FileReviewStatus, status_str, FileReviewStatus.PENDING)
        if notes:
            file_state.notes = notes

        self.server.save_and_sync()
        self._send_json({"status": "ok", "file": file_state.model_dump(mode="json")})

    def _handle_update_verdict(self, data: dict) -> None:
        """Update overall review verdict, persist markdown report, and handle termination."""
        verdict_str = data.get("verdict", "IN_REVIEW").upper()
        self.server.session.verdict = getattr(ReviewStatus, verdict_str, ReviewStatus.IN_REVIEW)
        if "summary" in data:
            self.server.session.summary = data["summary"]

        out_path = self.server.save_and_sync()

        # Termination conditions: APPROVE or REQUEST CHANGES
        terminating = data.get(
            "terminate",
            self.server.session.verdict in (ReviewStatus.APPROVED, ReviewStatus.CHANGES_REQUESTED),
        )

        self._send_json(
            {
                "status": "ok",
                "session": self.server.session.model_dump(mode="json"),
                "exported_to": str(out_path),
                "terminating": terminating,
            }
        )

        if terminating:
            self.server.trigger_shutdown()

    def _handle_export(self) -> None:
        """Force Markdown file export and return path."""
        out_path = self.server.save_and_sync()
        self._send_json({"status": "ok", "path": str(out_path)})

    def _handle_commit_update(self, data: dict) -> None:
        """Handle commit update event (rebase, merge, amend, etc.)."""
        orig_commit = data.get("original_commit", "")
        curr_commit = data.get("current_commit", "")
        action = data.get("action", "update")
        notes = data.get("notes", "")
        update = self.server.session.record_commit_update(
            original_commit=orig_commit,
            current_commit=curr_commit,
            action=action,
            notes=notes,
        )
        self.server.save_and_sync()
        self._send_json({"status": "ok", "update": update.model_dump(mode="json")})

    def _send_json(self, payload: dict | list, status: int = 200) -> None:
        """Serialize and send JSON response."""
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(content)
        self.close_connection = True


class ReviewServer(ThreadingHTTPServer):
    """Multi-threaded HTTP review server with embedded state persistence."""

    allow_reuse_address = True
    daemon_threads = True

    def get_request(self) -> Any:
        """Accept incoming connection and set socket timeout to prevent lingering sockets."""
        sock, addr = super().get_request()
        sock.settimeout(10.0)
        return sock, addr

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        repo_root: Optional[Path] = None,
        markdown_output: Optional[Path] = None,
        feedback_dir: Optional[Path] = None,
        state_file: Optional[Path] = None,
        sqlite_file: Optional[Path] = None,
        revisions: Optional[list[str]] = None,
        fresh: bool = False,
        bind_and_activate: bool = True,
    ) -> None:
        """Initialize review HTTP server with config and persistent paths."""
        self.repo_root = repo_root or get_git_root()
        self.git_engine = GitEngine(repo_root=self.repo_root)
        self.exporter = MarkdownReviewExporter(repo_root=self.repo_root)

        self.markdown_output = markdown_output or (self.repo_root / "build" / "CR.md")
        ws_root = self.repo_root.resolve()
        try:
            ws_root = get_git_root().resolve()
        except Exception:
            pass

        if feedback_dir is not None:
            self.feedback_dir = feedback_dir
        elif markdown_output is not None and markdown_output.parent.name not in ("build", "target"):
            self.feedback_dir = markdown_output.parent
        elif sqlite_file is not None and sqlite_file.parent.name not in ("build", "target"):
            self.feedback_dir = sqlite_file.parent / "feedback"
        elif os.environ.get("FEEDBACK_DIR") and (self.repo_root.resolve() == ws_root):
            self.feedback_dir = Path(os.environ["FEEDBACK_DIR"]).resolve()
        else:
            self.feedback_dir = self.repo_root / "feedback"
        if self.feedback_dir != self.repo_root / "feedback":
            try:
                self.feedback_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        self.state_file = state_file or (self.repo_root / "build" / "cr_feedback.json")
        if sqlite_file is not None:
            self.sqlite_file = sqlite_file
        elif state_file is not None:
            self.sqlite_file = state_file.with_suffix(".sqlite")
        else:
            self.sqlite_file = self.repo_root / "build" / "code_review.sqlite"
        self.sqlite_store = SQLiteReviewStore(self.sqlite_file)
        self.is_serving = False
        self.bind_and_activate = bind_and_activate

        resolved_revisions = self.git_engine.resolve_revisions(revisions) if revisions else None

        # Load or initialize session: check SQLite first, fallback to JSON state file
        loaded_session = None
        if not fresh:
            if self.sqlite_file.exists():
                candidate = self.sqlite_store.load_session()
                if candidate is not None and candidate.verdict != ReviewStatus.APPROVED:
                    loaded_session = candidate

            if loaded_session is None and self.state_file.exists():
                candidate = self.exporter.load_session_json(self.state_file)
                if candidate is not None and candidate.verdict != ReviewStatus.APPROVED:
                    loaded_session = candidate
                    self.sqlite_store.save_session(candidate)

        if loaded_session is not None:
            self.session = loaded_session
            self.session.repo_root = str(self.repo_root)
            if resolved_revisions is not None:
                self.session.revisions = resolved_revisions
        else:
            self.session = ReviewSessionModel(
                title=f"Code Review: {self.repo_root.name}",
                repo_name=self.repo_root.name,
                repo_root=str(self.repo_root),
                revisions=resolved_revisions or [],
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self.sqlite_store.save_session(self.session)

        # Ensure commit hash is set
        head_commit = self.git_engine.get_head_commit()
        if not self.session.commit_hash:
            self.session.commit_hash = head_commit

        # Requirement 7: Auto merge CR feedback if CR files exist in feedback_dir
        if self.feedback_dir.exists():
            all_session = self.session.model_copy(deep=True)
            for cr_file in sorted(self.feedback_dir.glob("CR_*.md")):
                all_session = self.exporter.merge_commit_feedback(all_session, cr_file)
            if (self.feedback_dir / "CR.md").exists():
                all_session = self.exporter.merge_commit_feedback(all_session, self.feedback_dir / "CR.md")
            for c in all_session.comments:
                self.sqlite_store.save_comment(c)
            if resolved_revisions:
                self.session.comments = [
                    c for c in all_session.comments if comment_matches_revisions(c, resolved_revisions)
                ]
            else:
                self.session.title = all_session.title
                self.session.created_at = all_session.created_at
                self.session.comments = list(all_session.comments)

        # Attempt port binding if bind_and_activate is enabled
        self.host = host
        if bind_and_activate:
            bound_port = port
            while True:
                try:
                    super().__init__((host, bound_port), ReviewRequestHandler)
                    break
                except OSError as err:
                    if bound_port == 0 or bound_port > port + 50:
                        raise err
                    bound_port += 1
            self.actual_port = self.server_port
        else:
            self.actual_port = port

        self._lock = threading.RLock()
        self._is_internal_saving = False
        self.feedback_mtime = self._get_feedback_dir_mtime()

    def server_close(self) -> None:
        """Close socket if bound."""
        if hasattr(self, "socket"):
            super().server_close()

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        """Handle requests until graceful shutdown is triggered."""
        self.is_serving = True
        try:
            super().serve_forever(poll_interval=poll_interval)
        finally:
            self.is_serving = False

    def trigger_shutdown(self, delay: float = 0.2) -> None:
        """Trigger graceful server shutdown in a background daemon thread."""

        def _delayed_shutdown() -> None:
            time.sleep(delay)
            if self.is_serving:
                self.shutdown()

        threading.Thread(target=_delayed_shutdown, daemon=True).start()

    def _get_feedback_dir_mtime(self) -> float:
        """Compute the maximum mtime across all CR markdown files in feedback_dir."""
        if not self.feedback_dir.exists():
            return 0.0
        try:
            max_mtime = self.feedback_dir.stat().st_mtime
            with os.scandir(self.feedback_dir) as it:
                for entry in it:
                    if entry.is_file() and entry.name.startswith("CR") and entry.name.endswith(".md"):
                        try:
                            mtime = entry.stat().st_mtime
                            if mtime > max_mtime:
                                max_mtime = mtime
                        except OSError:
                            pass
            return max_mtime
        except OSError:
            return 0.0

    def check_file_watch(self) -> bool:
        """Check if feedback_dir was modified externally and reload state."""
        with self._lock:
            if self._is_internal_saving:
                return False
            curr_fb_mtime = self._get_feedback_dir_mtime()
            if curr_fb_mtime > self.feedback_mtime + 0.001:
                self.sync_feedback()
                self.feedback_mtime = self._get_feedback_dir_mtime()
                return True
            return False

    def sync_feedback(self) -> dict:
        """Scan feedback/ directory for CR_*.md files and merge feedback into SQLite without cross-commit leakage."""
        merged_count = 0
        loaded_all = self.sqlite_store.load_session() if self.sqlite_store else None
        all_session = loaded_all if loaded_all is not None else self.session.model_copy(deep=True)

        existing_by_id = {c.id: c for c in all_session.comments}
        for c in self.session.comments:
            existing_by_id[c.id] = c
        all_session.comments = list(existing_by_id.values())

        if self.feedback_dir.exists():
            for cr_file in sorted(self.feedback_dir.glob("CR_*.md")):
                all_session = self.exporter.merge_commit_feedback(all_session, cr_file)
                merged_count += 1
            if (self.feedback_dir / "CR.md").exists():
                all_session = self.exporter.merge_commit_feedback(all_session, self.feedback_dir / "CR.md")

        if self.sqlite_store:
            for c in all_session.comments:
                self.sqlite_store.save_comment(c)

        if self.session.revisions:
            self.session.comments = [
                c for c in all_session.comments if comment_matches_revisions(c, self.session.revisions)
            ]
        else:
            self.session.title = all_session.title
            self.session.created_at = all_session.created_at
            self.session.comments = list(all_session.comments)

        self.save_and_sync()
        return {"status": "ok", "merged_files": merged_count, "total_comments": len(all_session.comments)}

    def update_comment_status(
        self,
        comment_id: str,
        new_status: CommentStatus,
        notes: Optional[str] = None,
    ) -> Optional[CommentModel]:
        """Transition a review comment's status in session and SQLite, then sync Markdown reports.

        Args:
            comment_id: Short ID or UUID of the target comment.
            new_status: Target CommentStatus (OPEN, RESOLVED, or CLOSED).
            notes: Optional resolution or acceptance/reopen note.

        Returns:
            Updated CommentModel if found, otherwise None.
        """
        with self._lock:
            clean_notes = elide_personal_info(notes.strip()) if isinstance(notes, str) else None
            target_comment: Optional[CommentModel] = None
            for comment in self.session.comments:
                if comment.id == comment_id or comment.uuid == comment_id:
                    target_comment = comment
                    break

            in_active_session = target_comment is not None
            if target_comment is None and self.sqlite_store:
                target_comment = self.sqlite_store.get_comment_by_id(comment_id)

            if target_comment is None:
                return None

            target_comment.set_status(new_status, notes=clean_notes)
            if new_status == CommentStatus.OPEN:
                self.session.auto_update_status_on_comment()

            if self.sqlite_store:
                self.sqlite_store.save_comment(target_comment)

            self.save_and_sync()

            if not in_active_session and target_comment.commit and self.sqlite_store:
                all_session = self.sqlite_store.load_session()
                if all_session is not None:
                    try:
                        commit_files = len(self.git_engine.get_changed_files(target_comment.commit))
                        self.exporter.export_commit_markdown(
                            all_session,
                            target_comment.commit,
                            self.feedback_dir,
                            total_repo_files=commit_files,
                        )
                    except OSError:
                        pass

            return target_comment

    def update_commit_hash(self, orig_commit: str, new_commit: str) -> None:
        """Update review session and comments from orig_commit to new_commit.

        Args:
            orig_commit: Original commit hash or 'working'.
            new_commit: New commit hash to re-key comments to.
        """
        with self._lock:
            if self.session.commit_hash == orig_commit or (not self.session.commit_hash and orig_commit == "working"):
                self.session.commit_hash = new_commit
            if orig_commit in self.session.revisions:
                self.session.revisions = [new_commit if r == orig_commit else r for r in self.session.revisions]
            for comment in self.session.comments:
                if comment.commit == orig_commit or (not comment.commit and orig_commit == "working"):
                    comment.commit = new_commit
            if self.sqlite_store:
                self.sqlite_store.update_comment_commit_hash(orig_commit, new_commit)
            self.save_and_sync()

    def save_and_sync(self) -> Path:
        """Persist session to SQLite, export JSON, and render updated Markdown report."""
        with self._lock:
            self._is_internal_saving = True
            try:
                self.session.updated_at = datetime.now(timezone.utc).isoformat()
                self.sqlite_store.save_session(self.session)
                self.exporter.save_session_json(self.session, self.state_file)
                total_files = len(self.git_engine.get_changed_files("working"))

                is_feedback_dir = self.markdown_output.resolve().parent.name == "feedback"
                if self.session.comments or not is_feedback_dir:
                    res = self.exporter.export_markdown(
                        self.session,
                        self.markdown_output,
                        total_repo_files=total_files,
                    )
                else:
                    if self.markdown_output.exists():
                        try:
                            self.markdown_output.unlink()
                        except OSError:
                            pass
                    res = self.markdown_output

                # Export commit-specific CR_<commit>.md for all relevant commits
                commits_to_export = {c.commit for c in self.session.comments if c.commit}
                commit_sha = self.session.commit_hash or self.git_engine.get_head_commit()
                if commit_sha:
                    commits_to_export.add(commit_sha)
                if (self.feedback_dir / "CR_working.md").exists():
                    commits_to_export.add("working")

                for c_sha in commits_to_export:
                    try:
                        commit_files = len(self.git_engine.get_changed_files(c_sha))
                        self.exporter.export_commit_markdown(
                            self.session, c_sha, self.feedback_dir, total_repo_files=commit_files
                        )
                    except OSError:
                        pass

                cr_md = self.repo_root / "build" / "CR.md"
                if cr_md.parent.exists() and self.markdown_output.resolve() != cr_md.resolve():
                    if self.session.comments:
                        try:
                            self.exporter.export_markdown(self.session, cr_md, total_repo_files=total_files)
                        except OSError:
                            pass
                    elif cr_md.exists():
                        try:
                            cr_md.unlink()
                        except OSError:
                            pass
                self.feedback_mtime = self._get_feedback_dir_mtime()
                return res
            finally:
                self._is_internal_saving = False

    def get_url(self) -> str:
        """Return the browser URL for accessing the review dashboard."""
        return f"http://{self.host}:{self.actual_port}/"
