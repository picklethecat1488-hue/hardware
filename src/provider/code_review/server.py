"""HTTP server and REST API for interactive code review web UI.

Serves the Quake-themed code review dashboard and handles JSON API endpoints
for file diffs, commit inspection, inline commenting, review status updates,
and automated Markdown persistence.
"""

from datetime import datetime, timezone
import json
import mimetypes
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
from provider.code_review.markdown_exporter import MarkdownReviewExporter
from provider.code_review.sqlite_store import SQLiteReviewStore


class ReviewRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler dispatching review API endpoints and dashboard UI."""

    server: "ReviewServer"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Suppress default HTTP server logging to preserve clean console output."""
        return

    def do_GET(self) -> None:  # noqa: N802
        """Route GET requests for UI dashboard and data query endpoints."""
        self.server.check_file_watch()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/static/"):
            self._handle_serve_static(path)
            return

        if path in ("/favicon.ico", "/favicon.svg"):
            self._handle_serve_static("/static/favicon.svg")
            return

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
                results = self.server.git_engine.search_code(q, commit=commit)
                self._send_json({"query": q, "commit": commit, "results": results})
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
        html_out = template.render(session=self.server.session)

        encoded = html_out.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _handle_serve_static(self, path: str) -> None:
        """Serve static files such as JavaScript vendor bundles and CSS."""
        static_dir = Path(__file__).resolve().parent / "static"
        filename = path.removeprefix("/static/").strip("/")
        file_target = (static_dir / filename).resolve()

        if not str(file_target).startswith(str(static_dir)) or not file_target.is_file():
            self.send_error(404, "Static asset not found")
            return

        if file_target.suffix == ".js":
            content_type = "application/javascript"
        elif file_target.suffix == ".svg":
            content_type = "image/svg+xml"
        else:
            content_type = "text/css"
        data = file_target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

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
        """Edit body and optional severity of an existing comment."""
        cid = data.get("id", "").strip()
        new_body = data.get("body", "").strip()
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
                self.server.save_and_sync()
                self._send_json({"status": "ok", "comment": comment.model_dump(mode="json")})
                return

        self._send_json({"error": f"Comment {cid} not found"}, status=404)

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
        if feedback_dir is not None:
            self.feedback_dir = feedback_dir
        elif markdown_output is not None and markdown_output.parent.name != "build":
            self.feedback_dir = markdown_output.parent
        else:
            self.feedback_dir = self.repo_root / "feedback"
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
            for cr_file in sorted(self.feedback_dir.glob("CR_*.md")):
                self.session = self.exporter.merge_commit_feedback(self.session, cr_file)
            if (self.feedback_dir / "CR.md").exists():
                self.session = self.exporter.merge_commit_feedback(self.session, self.feedback_dir / "CR.md")
            if self.session.comments:
                self.sqlite_store.save_session(self.session)

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
            for f in self.feedback_dir.glob("CR*.md"):
                try:
                    mtime = f.stat().st_mtime
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
        """Scan feedback/ directory for CR_*.md files and merge feedback into SQLite."""
        merged_count = 0
        if self.feedback_dir.exists():
            for cr_file in sorted(self.feedback_dir.glob("CR_*.md")):
                self.session = self.exporter.merge_commit_feedback(self.session, cr_file)
                merged_count += 1
            if (self.feedback_dir / "CR.md").exists():
                self.session = self.exporter.merge_commit_feedback(self.session, self.feedback_dir / "CR.md")
        self.save_and_sync()
        return {"status": "ok", "merged_files": merged_count, "total_comments": len(self.session.comments)}

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

                # Export commit-specific CR_<commit>.md ONLY if there are comments for this commit
                commit_sha = self.session.commit_hash or self.git_engine.get_head_commit()
                if commit_sha:
                    try:
                        commit_files = len(self.git_engine.get_changed_files(commit_sha))
                        self.exporter.export_commit_markdown(
                            self.session, commit_sha, self.feedback_dir, total_repo_files=commit_files
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
