"""HTTP server and REST API for interactive code review web UI.

Serves the Quake-themed code review dashboard and handles JSON API endpoints
for file diffs, commit inspection, inline commenting, review status updates,
and automated Markdown persistence.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
import uuid

import jinja2

from model.code_review import (
    CommentModel,
    FileReviewStatus,
    ReviewSessionModel,
    ReviewSeverity,
    ReviewStatus,
)
from provider.code_review.git_utils import (
    GitReviewEngine,
    extract_line_snippet,
    get_git_root,
)
from provider.code_review.markdown_exporter import MarkdownReviewExporter


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

        if path.startswith("/static/"):
            self._handle_serve_static(path)
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
                self._handle_add_comment(data)
            case "/api/file_status":
                self._handle_update_file_status(data)
            case "/api/verdict":
                self._handle_update_verdict(data)
            case "/api/export":
                self._handle_export()
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

        content_type = "application/javascript" if file_target.suffix == ".js" else "text/css"
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

        snippet = extract_line_snippet(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            commit="working",
            repo_root=self.server.repo_root,
        )

        comment = CommentModel(
            id=uuid.uuid4().hex[:12],
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            severity=severity,
            body=body,
            author=author,
            code_snippet=snippet,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self.server.session.comments.append(comment)
        self.server.session.auto_update_status_on_comment()
        self.server.save_and_sync()
        self._send_json(
            {"status": "ok", "comment": comment.model_dump(mode="json"), "verdict": self.server.session.verdict.value}
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

    def _send_json(self, payload: dict | list, status: int = 200) -> None:
        """Serialize and send JSON response."""
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


class ReviewServer(ThreadingHTTPServer):
    """Multi-threaded HTTP review server with embedded state persistence."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        repo_root: Optional[Path] = None,
        markdown_output: Optional[Path] = None,
        state_file: Optional[Path] = None,
        revisions: Optional[list[str]] = None,
    ) -> None:
        """Initialize review HTTP server with config and persistent paths."""
        self.repo_root = repo_root or get_git_root()
        self.git_engine = GitReviewEngine(repo_root=self.repo_root)
        self.exporter = MarkdownReviewExporter(repo_root=self.repo_root)

        self.markdown_output = markdown_output or (self.repo_root / "build" / "CR.md")
        self.state_file = state_file or (self.repo_root / "build" / "cr_feedback.json")
        self.is_serving = False

        # Load or initialize session
        loaded_session = self.exporter.load_session_json(self.state_file)
        if loaded_session is not None:
            self.session = loaded_session
            if revisions:
                self.session.revisions = revisions
        else:
            self.session = ReviewSessionModel(
                title=f"Code Review: {self.repo_root.name}",
                repo_name=self.repo_root.name,
                revisions=revisions or [],
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )

        # Attempt port binding, fall back to next available port if requested port is taken
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
        self.host = host

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

    def save_and_sync(self) -> Path:
        """Persist session JSON and render updated Markdown report."""
        self.exporter.save_session_json(self.session, self.state_file)
        total_files = len(self.git_engine.get_changed_files("working"))
        return self.exporter.export_markdown(
            self.session,
            self.markdown_output,
            total_repo_files=total_files,
        )

    def get_url(self) -> str:
        """Return the browser URL for accessing the review dashboard."""
        return f"http://{self.host}:{self.actual_port}/"
