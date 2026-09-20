"""HTTP server and REST API for interactive Bug Report dashboard.

Serves the engineering bug report workstation UI and handles JSON API endpoints
for bug creation, triage, reproduction steps, log and screenshot attachments,
and automated Markdown persistence (build/BUGS.md).
"""

import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import urllib.parse
import uuid

import jinja2

from model.bug_report import (
    BugAttachmentModel,
    BugCategory,
    BugDatabaseModel,
    BugReportModel,
    BugSeverity,
    BugStatus,
)
from provider.bug_report.markdown_exporter import MarkdownBugExporter


class BugReportRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler dispatching bug report UI and REST API endpoints."""

    server: "BugReportServer"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Suppress default HTTP server logging to preserve clean console output."""
        return

    def do_GET(self) -> None:  # noqa: N802
        """Route GET requests for UI dashboard and data query endpoints."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/attachments/"):
            self._handle_serve_attachment(path)
            return

        match path:
            case "/":
                self._handle_serve_ui()
            case "/api/database":
                self._send_json(self.server.database.model_dump(mode="json"))
            case "/api/bugs":
                bugs_data = [b.model_dump(mode="json") for b in self.server.database.bugs]
                self._send_json(bugs_data)
            case "/api/metadata":
                self._send_json(
                    {
                        "statuses": [s.value for s in BugStatus],
                        "severities": [s.value for s in BugSeverity],
                        "categories": [c.value for c in BugCategory],
                        "counts_status": self.server.database.count_by_status(),
                        "counts_severity": self.server.database.count_by_severity(),
                        "counts_category": self.server.database.count_by_category(),
                    }
                )
            case "/api/files":
                files = self._list_reference_files()
                self._send_json(files)
            case _:
                self.send_error(404, "Endpoint not found")

    def do_POST(self) -> None:  # noqa: N802
        """Route POST requests for bug creation, updates, uploads, and export."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        match path:
            case "/api/bugs":
                self._handle_save_bug(data)
            case "/api/bugs/status":
                self._handle_update_status(data)
            case "/api/bugs/delete":
                self._handle_delete_bug(data)
            case "/api/upload":
                self._handle_file_upload(data)
            case "/api/export":
                out_path = self.server.save_and_sync()
                self._send_json({"status": "exported", "path": str(out_path)})
            case _:
                self.send_error(404, "Endpoint not found")

    def _handle_serve_ui(self) -> None:
        """Render and serve the bug reporting HTML dashboard via Jinja2."""
        template_dir = Path(__file__).resolve().parent.parent / "templates"
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template("bug_report.html.j2")
        db_dump = self.server.database.model_dump(mode="json")
        html_content = template.render(
            database=self.server.database,
            database_json=json.dumps(db_dump),
            statuses=[s.value for s in BugStatus],
            severities=[s.value for s in BugSeverity],
            categories=[c.value for c in BugCategory],
            server_port=self.server.port,
        )

        encoded = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _handle_serve_attachment(self, path: str) -> None:
        """Serve uploaded file attachments from attachments directory."""
        rel_name = path[len("/attachments/") :]
        file_path = self.server.attachments_dir / rel_name
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, f"Attachment '{rel_name}' not found")
            return

        content = file_path.read_bytes()
        suffix = file_path.suffix.lower()
        content_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".txt": "text/plain",
            ".log": "text/plain",
            ".json": "application/json",
            ".yaml": "text/yaml",
            ".yml": "text/yaml",
        }.get(suffix, "application/octet-stream")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_save_bug(self, data: Dict[str, Any]) -> None:
        """Create or update a bug report and persist to storage."""
        bug_id = data.get("id") or self.server.database.generate_bug_id()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        existing = self.server.database.get_bug(bug_id)
        created_at = existing.created_at if existing else now_str

        # Parse attachments
        attachments: List[BugAttachmentModel] = []
        for att_data in data.get("attachments", []):
            attachments.append(BugAttachmentModel.model_validate(att_data))

        # Parse reproduction steps
        raw_steps = data.get("reproduction_steps", [])
        if isinstance(raw_steps, str):
            steps = [s.strip() for s in raw_steps.splitlines() if s.strip()]
        else:
            steps = [str(s).strip() for s in raw_steps if str(s).strip()]

        status_val = data.get("status", BugStatus.OPEN.value)
        status = BugStatus(status_val) if status_val in [s.value for s in BugStatus] else BugStatus.OPEN

        resolved_at = existing.resolved_at if existing else None
        if status in (BugStatus.RESOLVED, BugStatus.CLOSED) and not resolved_at:
            resolved_at = now_str
        elif status in (BugStatus.OPEN, BugStatus.IN_PROGRESS):
            resolved_at = None

        bug = BugReportModel(
            id=bug_id,
            title=data.get("title", "Untitled Bug"),
            status=status,
            severity=BugSeverity(data.get("severity", BugSeverity.MEDIUM.value)),
            category=BugCategory(data.get("category", BugCategory.PCB.value)),
            component=data.get("component", ""),
            description=data.get("description", ""),
            reproduction_steps=steps,
            expected_behavior=data.get("expected_behavior", ""),
            actual_behavior=data.get("actual_behavior", ""),
            logs=data.get("logs", ""),
            attachments=attachments,
            created_at=created_at,
            updated_at=now_str,
            resolved_at=resolved_at,
            resolution_notes=data.get("resolution_notes", ""),
        )

        self.server.database.add_or_update(bug)
        self.server.save_and_sync()
        self._send_json(bug.model_dump(mode="json"))

    def _handle_update_status(self, data: Dict[str, Any]) -> None:
        """Update lifecycle status and resolution notes for a bug."""
        bug_id = data.get("id")
        new_status_str = data.get("status")
        notes = data.get("resolution_notes")

        bug = self.server.database.get_bug(bug_id)
        if not bug:
            self._send_json({"error": f"Bug {bug_id} not found"}, status=404)
            return

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if new_status_str and new_status_str in [s.value for s in BugStatus]:
            bug.status = BugStatus(new_status_str)
            if bug.status in (BugStatus.RESOLVED, BugStatus.CLOSED):
                bug.resolved_at = now_str
            else:
                bug.resolved_at = None

        if notes is not None:
            bug.resolution_notes = notes

        bug.updated_at = now_str
        self.server.save_and_sync()
        self._send_json(bug.model_dump(mode="json"))

    def _handle_delete_bug(self, data: Dict[str, Any]) -> None:
        """Delete a bug report by ID."""
        bug_id = data.get("id")
        self.server.database.bugs = [b for b in self.server.database.bugs if b.id != bug_id]
        self.server.save_and_sync()
        self._send_json({"status": "deleted", "id": bug_id})

    def _handle_file_upload(self, data: Dict[str, Any]) -> None:
        """Save base64 encoded file upload or log string to attachments directory."""
        filename = data.get("filename", f"attachment_{uuid.uuid4().hex[:8]}.txt")
        file_type = data.get("file_type", "reference")
        desc = data.get("description", "")
        b64_content = data.get("content_base64", "")
        text_content = data.get("content_text", "")

        self.server.attachments_dir.mkdir(parents=True, exist_ok=True)
        dest_path = self.server.attachments_dir / filename

        if b64_content:
            file_bytes = base64.b64decode(b64_content)
            dest_path.write_bytes(file_bytes)
        elif text_content:
            file_bytes = text_content.encode("utf-8")
            dest_path.write_bytes(file_bytes)
        else:
            file_bytes = b""
            dest_path.write_bytes(file_bytes)

        rel_path = (
            dest_path.relative_to(self.server.repo_root)
            if dest_path.is_relative_to(self.server.repo_root)
            else dest_path
        )

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        att = BugAttachmentModel(
            id=uuid.uuid4().hex[:8],
            filename=filename,
            file_type=file_type,
            file_path=str(rel_path),
            size_bytes=len(file_bytes),
            description=desc,
            created_at=now_str,
        )
        self._send_json(att.model_dump(mode="json"))

    def _list_reference_files(self) -> List[Dict[str, str]]:
        """List relevant preview screenshots, logs, and artifacts in workspace."""
        results: List[Dict[str, str]] = []
        # Scan build/ directory for images and markdown
        build_dir = self.server.repo_root / "build"
        if build_dir.exists():
            for p in build_dir.glob("*.png"):
                results.append(
                    {"name": p.name, "path": str(p.relative_to(self.server.repo_root)), "type": "screenshot"}
                )
        # Scan recordings/previews
        rec_dir = self.server.repo_root / "recordings" / "previews"
        if rec_dir.exists():
            for p in rec_dir.glob("*.png"):
                results.append(
                    {"name": p.name, "path": str(p.relative_to(self.server.repo_root)), "type": "screenshot"}
                )
        return results

    def _generate_bug_id(self) -> str:
        """Generate next sequential bug ID (e.g. BUG-001, BUG-002)."""
        max_idx = 0
        for b in self.server.database.bugs:
            if b.id.startswith("BUG-"):
                try:
                    idx = int(b.id[4:])
                    if idx > max_idx:
                        max_idx = idx
                except ValueError:
                    pass
        return f"BUG-{max_idx + 1:03d}"

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send JSON HTTP response payload."""
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class BugReportServer(ThreadingHTTPServer):
    """Threaded HTTP server hosting Bug Report workstation."""

    allow_reuse_address = True

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8766,
        repo_root: Optional[Path] = None,
        markdown_output: Optional[Path] = None,
        state_file: Optional[Path] = None,
        attachments_dir: Optional[Path] = None,
        fresh: bool = False,
    ) -> None:
        """Initialize server with persistent storage paths."""
        self.host = host
        self.port = port
        self.repo_root = repo_root or Path.cwd()
        self.markdown_output = markdown_output or (self.repo_root / "build" / "BUGS.md")
        self.state_file = state_file or (self.repo_root / "build" / "bugs_state.json")
        self.attachments_dir = attachments_dir or (self.repo_root / "build" / "attachments")
        self.fresh = fresh

        self.exporter = MarkdownBugExporter(repo_root=self.repo_root)
        self.database = self._initialize_database()

        super().__init__((host, port), BugReportRequestHandler)

    def _initialize_database(self) -> BugDatabaseModel:
        """Load existing database state or initialize fresh database."""
        if not self.fresh and self.state_file.exists():
            loaded = self.exporter.load_state_json(self.state_file)
            if loaded:
                return loaded

        db = BugDatabaseModel(
            title="Hardware Bug Tracker",
            summary="Hardware engineering defects, PCB layout issues, and reproduction tracking.",
        )
        return db

    def save_and_sync(self) -> Path:
        """Persist bug database to JSON state file and export to Markdown."""
        self.database.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.exporter.export_state_json(self.database, self.state_file)
        return self.exporter.export_markdown(self.database, self.markdown_output)

    def get_url(self) -> str:
        """Return reachable HTTP URL for browser."""
        return f"http://{self.host}:{self.port}"
