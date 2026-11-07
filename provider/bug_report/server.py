"""HTTP server and REST API for interactive Bug Report dashboard.

Serves the engineering bug report workstation UI and handles JSON API endpoints
for bug creation, triage, reproduction steps, log and screenshot attachments,
and automated Markdown persistence (build/BUGS.md).
"""

import base64
from collections.abc import Collection
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
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
    ReviewTaskModel,
    ReviewTaskStatus,
)
from provider.bug_report.markdown_exporter import MarkdownBugExporter
from provider.bug_report.sqlite_store import SQLiteBugStore

MAX_ATTACHMENT_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2 GiB (GitHub LFS maximum file limit)


class BugReportRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler dispatching bug report UI and REST API endpoints."""

    server: "BugReportServer"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Suppress default HTTP server logging to preserve clean console output."""
        return

    def handle_one_request(self) -> None:
        """Handle a single HTTP request, catching client disconnects gracefully."""
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True

    def handle(self) -> None:
        """Handle incoming requests on this connection until closed."""
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802
        """Route GET requests for UI dashboard and data query endpoints."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/static/"):
            self._handle_serve_static(path)
            return

        if path in ("/favicon.ico", "/favicon.svg"):
            self._handle_serve_static("/static/favicon.svg")
            return

        if path.startswith("/attachments/") or path.startswith("/build/attachments/"):
            self._handle_serve_attachment(path)
            return

        now = time.time()
        if now - getattr(self.server, "_last_watch_check", 0.0) >= 2.0:
            self.server._last_watch_check = now
            self.server.check_file_watch()

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
            case "/api/next_bug_id":
                self._send_json({"next_id": self.server.database.generate_bug_id()})
            case "/api/version":
                self._send_json(
                    {
                        "version": self.server.db_version,
                        "bugs_count": len(self.server.database.bugs),
                        "mtime": self.server.feedback_mtime,
                    }
                )
            case _:
                self.send_error(404, "Endpoint not found")

    def do_POST(self) -> None:  # noqa: N802
        """Route POST requests for bug creation, updates, uploads, and export."""
        now = time.time()
        if now - getattr(self.server, "_last_watch_check", 0.0) >= 2.0:
            self.server._last_watch_check = now
            self.server.check_file_watch()
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        if length >= MAX_ATTACHMENT_SIZE_BYTES:
            self.send_error(413, "Payload Too Large: Request exceeds maximum allowed size of 2 GB (GitHub LFS limit)")
            return

        try:
            body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            data = json.loads(body)
        except (MemoryError, OverflowError):
            self.send_error(413, "Payload Too Large: Insufficient memory to process request payload")
            return
        except json.JSONDecodeError:
            data = {}

        match path:
            case "/api/bugs":
                self._handle_save_bug(data)
            case "/api/bugs/status":
                self._handle_update_status(data)
            case "/api/bugs/accept":
                self._handle_accept_bug(data)
            case "/api/bugs/reject":
                self._handle_reject_bug(data)
            case "/api/bugs/attach_commit":
                self._handle_attach_commit(data)
            case "/api/bugs/add_task":
                self._handle_add_task(data)
            case "/api/bugs/update_task":
                self._handle_update_task(data)
            case "/api/bugs/run_command":
                self._handle_run_command(data)
            case "/api/bugs/delete":
                self._handle_delete_bug(data)
            case "/api/bugs/migrate_legacy":
                self._handle_migrate_legacy(data)
            case "/api/upload":
                self._handle_file_upload(data)
            case "/api/export":
                out_path = self.server.save_and_sync()
                self._send_json({"status": "exported", "path": str(out_path)})
            case "/api/sync_feedback":
                stats = self.server.sync_with_feedback_dir()
                self._send_json({"status": "ok", "stats": stats})
            case "/api/exit":
                out_path = self.server.save_and_sync()
                self._send_json({"status": "saved_and_exited", "path": str(out_path)})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
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
        components = sorted(
            {b.component.strip() for b in self.server.database.bugs if b.component and b.component.strip()}
        )
        html_content = template.render(
            database=self.server.database,
            database_json=json.dumps(db_dump),
            statuses=[s.value for s in BugStatus],
            severities=[s.value for s in BugSeverity],
            categories=[c.value for c in BugCategory],
            components=components,
            server_port=self.server.port,
        )
        self._send_html(html_content)

    def _handle_serve_attachment(self, path: str) -> None:
        """Serve uploaded file attachments from attachments directory."""
        clean_path = path.lstrip("/")
        if clean_path.startswith("build/attachments/"):
            rel_name = clean_path[len("build/attachments/") :]
        elif clean_path.startswith("attachments/"):
            rel_name = clean_path[len("attachments/") :]
        else:
            rel_name = clean_path
        file_path = self.server.attachments_dir / rel_name
        if not file_path.exists() or not file_path.is_file():
            fallback = self.server.repo_root / "build" / "attachments" / rel_name
            if fallback.exists() and fallback.is_file():
                file_path = fallback
            elif (self.server.repo_root / clean_path).is_file():
                file_path = self.server.repo_root / clean_path
            else:
                self.send_error(404, f"Attachment '{rel_name}' not found")
                return

        file_size = file_path.stat().st_size
        suffix = file_path.suffix.lower()
        content_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".log": "text/plain",
            ".json": "application/json",
            ".yaml": "text/yaml",
            ".yml": "text/yaml",
            ".md": "text/markdown",
            ".csv": "text/csv",
        }.get(suffix, "application/octet-stream")

        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Connection", "close")
            self.end_headers()
            with open(file_path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        finally:
            self.close_connection = True

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
        incoming_notes = data.get("resolution_notes", "").strip()

        resolved_at = existing.resolved_at if existing else None
        if existing and existing.status in (BugStatus.RESOLVED, BugStatus.CLOSED):
            if existing.resolution_notes.strip() and status == BugStatus.OPEN and not incoming_notes:
                status = existing.status
                resolved_at = existing.resolved_at
                incoming_notes = existing.resolution_notes

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
            resolution_notes=incoming_notes,
        )

        self.server.database.add_or_update(bug)
        self.server.save_and_sync(dirty_bug_ids=[bug.id])
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
        self.server.save_and_sync(dirty_bug_ids=[bug.id])
        self._send_json(bug.model_dump(mode="json"))

    def _handle_accept_bug(self, data: Dict[str, Any]) -> None:
        """Handle accepting a resolved bug and transitioning directly to CLOSED."""
        bug_id = data.get("id")
        notes = data.get("notes", "").strip()
        bug = self.server.database.get_bug(bug_id) if bug_id else None
        if not bug:
            self._send_json({"error": f"Bug {bug_id} not found"}, status=404)
            return

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        bug.status = BugStatus.CLOSED
        bug.accepted_at = now_str
        if notes:
            if bug.resolution_notes:
                bug.resolution_notes += f"\n\n**Acceptance Note**: {notes}"
            else:
                bug.resolution_notes = f"**Acceptance Note**: {notes}"
        bug.updated_at = now_str
        self.server.save_and_sync(dirty_bug_ids=[bug.id])
        self._send_json({"status": "ok", "bug": bug.model_dump(mode="json")})

    def _handle_reject_bug(self, data: Dict[str, Any]) -> None:
        """Handle rejecting a resolved bug and transitioning directly back to OPEN."""
        bug_id = data.get("id")
        notes = data.get("notes", "").strip()
        bug = self.server.database.get_bug(bug_id) if bug_id else None
        if not bug:
            self._send_json({"error": f"Bug {bug_id} not found"}, status=404)
            return

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        bug.status = BugStatus.OPEN
        bug.resolved_at = None
        bug.rejected_at = now_str
        bug.rejection_notes = notes
        bug.updated_at = now_str
        self.server.save_and_sync(dirty_bug_ids=[bug.id])
        self._send_json({"status": "ok", "bug": bug.model_dump(mode="json")})

    def _handle_migrate_legacy(self, data: Dict[str, Any]) -> None:
        """Handle migrating legacy resolved bugs to CLOSED status."""
        before_ts = data.get("before", "2026-11-05 14:00:00 UTC")
        migrate_all = bool(data.get("all", False))
        exclude_raw = data.get("exclude", [])
        exclude_ids = set(exclude_raw if isinstance(exclude_raw, list) else str(exclude_raw).split(","))
        dry_run = bool(data.get("dry_run", False))

        candidates = []
        for b in self.server.database.bugs:
            if b.status == BugStatus.RESOLVED and not b.accepted_at:
                if b.id.upper() in {x.upper().strip() for x in exclude_ids if x.strip()}:
                    continue
                if not migrate_all and before_ts:
                    check_ts = b.resolved_at or b.updated_at or b.created_at
                    if check_ts and check_ts > before_ts:
                        continue
                candidates.append(b)

        if dry_run:
            self._send_json(
                {
                    "status": "ok",
                    "dry_run": True,
                    "count": len(candidates),
                    "migrated_ids": [b.id for b in candidates],
                }
            )
            return

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        migrated_ids = []
        for b in candidates:
            b.status = BugStatus.CLOSED
            b.accepted_at = b.resolved_at or b.updated_at or b.created_at or now_str
            b.updated_at = now_str
            migrated_ids.append(b.id)

        if migrated_ids:
            self.server.save_and_sync(dirty_bug_ids=migrated_ids)

        self._send_json(
            {
                "status": "ok",
                "dry_run": False,
                "count": len(migrated_ids),
                "migrated_ids": migrated_ids,
            }
        )

    def _handle_attach_commit(self, data: Dict[str, Any]) -> None:
        """Attach a commit hash to a bug report."""
        bug_id = data.get("id")
        commit_id = data.get("commit_id", "").strip()
        bug = self.server.database.get_bug(bug_id) if bug_id else None
        if not bug:
            self._send_json({"error": f"Bug {bug_id} not found"}, status=404)
            return
        if not commit_id:
            self._send_json({"error": "Missing commit_id"}, status=400)
            return

        if commit_id not in bug.commit_ids:
            bug.commit_ids.append(commit_id)

        bug.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.server.save_and_sync(dirty_bug_ids=[bug.id])
        self._send_json({"status": "ok", "bug": bug.model_dump(mode="json")})

    def _handle_add_task(self, data: Dict[str, Any]) -> None:
        """Add a review task to a bug report."""
        bug_id = data.get("id")
        title = data.get("title", "").strip()
        cmd = data.get("command", "").strip()
        bug = self.server.database.get_bug(bug_id) if bug_id else None
        if not bug:
            self._send_json({"error": f"Bug {bug_id} not found"}, status=404)
            return
        if not title:
            self._send_json({"error": "Missing task title"}, status=400)
            return

        task = ReviewTaskModel(title=title, command=cmd)
        bug.review_tasks.append(task)
        bug.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.server.save_and_sync(dirty_bug_ids=[bug.id])
        self._send_json({"status": "ok", "task": task.model_dump(mode="json"), "bug": bug.model_dump(mode="json")})

    def _handle_update_task(self, data: Dict[str, Any]) -> None:
        """Update review task status or notes."""
        bug_id = data.get("id")
        task_id = data.get("task_id")
        new_status = data.get("status")
        notes = data.get("notes")
        bug = self.server.database.get_bug(bug_id) if bug_id else None
        if not bug:
            self._send_json({"error": f"Bug {bug_id} not found"}, status=404)
            return

        target_task = None
        for t in bug.review_tasks:
            if t.id == task_id:
                target_task = t
                break

        if not target_task:
            self._send_json({"error": f"Task {task_id} not found"}, status=404)
            return

        if new_status:
            try:
                target_task.status = ReviewTaskStatus(str(new_status).upper())
            except ValueError:
                target_task.status = ReviewTaskStatus.PENDING
        if notes is not None:
            target_task.notes = str(notes)

        bug.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.server.save_and_sync(dirty_bug_ids=[bug.id])
        self._send_json(
            {"status": "ok", "task": target_task.model_dump(mode="json"), "bug": bug.model_dump(mode="json")}
        )

    def _handle_run_command(self, data: Dict[str, Any]) -> None:
        """Execute a review command and return output."""
        cmd = data.get("command", "").strip()
        if not cmd:
            self._send_json({"error": "Empty command"}, status=400)
            return

        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(self.server.repo_root),
            capture_output=True,
            text=True,
        )
        self._send_json(
            {
                "status": "ok" if proc.returncode == 0 else "error",
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )

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

        raw_bug_id = str(data.get("bug_id") or data.get("bugId") or "").strip()
        if not raw_bug_id and str(data.get("id", "")).startswith("BUG-"):
            raw_bug_id = str(data.get("id")).strip()
        bug_id = Path(raw_bug_id).name if raw_bug_id else ""
        filename = Path(filename).name

        dest_dir = (self.server.attachments_dir / bug_id) if bug_id else self.server.attachments_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename

        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            counter = 1
            while (dest_dir / f"{stem}_{counter}{suffix}").exists():
                counter += 1
            filename = f"{stem}_{counter}{suffix}"
            dest_path = dest_dir / filename

        if b64_content and (len(b64_content) * 3) // 4 >= MAX_ATTACHMENT_SIZE_BYTES:
            self._send_json(
                {"error": "Payload Too Large: Attachment exceeds 2 GB limit (GitHub LFS limit)"},
                status=413,
            )
            return
        if text_content and len(text_content.encode("utf-8")) >= MAX_ATTACHMENT_SIZE_BYTES:
            self._send_json(
                {"error": "Payload Too Large: Attachment exceeds 2 GB limit (GitHub LFS limit)"},
                status=413,
            )
            return

        try:
            if b64_content:
                file_bytes = base64.b64decode(b64_content)
                if len(file_bytes) >= MAX_ATTACHMENT_SIZE_BYTES:
                    self._send_json(
                        {"error": "Payload Too Large: Attachment exceeds 2 GB limit (GitHub LFS limit)"},
                        status=413,
                    )
                    return
                dest_path.write_bytes(file_bytes)
            elif text_content:
                file_bytes = text_content.encode("utf-8")
                if len(file_bytes) >= MAX_ATTACHMENT_SIZE_BYTES:
                    self._send_json(
                        {"error": "Payload Too Large: Attachment exceeds 2 GB limit (GitHub LFS limit)"},
                        status=413,
                    )
                    return
                dest_path.write_bytes(file_bytes)
            else:
                file_bytes = b""
                dest_path.write_bytes(file_bytes)
        except (MemoryError, OverflowError):
            self._send_json(
                {"error": "Payload Too Large: Insufficient memory to decode attachment payload"},
                status=413,
            )
            return

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

    def _handle_serve_static(self, path: str) -> None:
        """Serve static assets such as favicon and vendor bundles."""
        static_dir = Path(__file__).resolve().parent.parent / "code_review" / "static"
        filename = path.removeprefix("/static/").strip("/")
        file_target = (static_dir / filename).resolve()
        if not str(file_target).startswith(str(static_dir)) or not file_target.is_file():
            self.send_error(404, "Static asset not found")
            return
        if file_target.suffix == ".svg":
            content_type = "image/svg+xml"
        elif file_target.suffix == ".js":
            content_type = "application/javascript"
        elif file_target.suffix == ".css":
            content_type = "text/css"
        else:
            content_type = "text/plain"
        data = file_target.read_bytes()
        try:
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        finally:
            self.close_connection = True

    def _send_html(self, html: str) -> None:
        """Send UTF-8 encoded HTML HTTP response payload."""
        encoded = html.encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        finally:
            self.close_connection = True

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send JSON HTTP response payload."""
        encoded = json.dumps(data, indent=2).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        finally:
            self.close_connection = True


class BugReportServer(ThreadingHTTPServer):
    """Local Threading HTTP web server hosting the interactive bug report dashboard."""

    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Handle client connection errors gracefully without printing tracebacks on client disconnects."""
        exc_type, _, _ = sys.exc_info()
        if exc_type is not None and issubclass(
            exc_type, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)
        ):
            return
        super().handle_error(request, client_address)

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8766,
        repo_root: Optional[Path] = None,
        markdown_output: Optional[Path] = None,
        feedback_dir: Optional[Path] = None,
        state_file: Optional[Path] = None,
        sqlite_file: Optional[Path] = None,
        attachments_dir: Optional[Path] = None,
        fresh: bool = False,
        bind_and_activate: bool = True,
    ) -> None:
        """Initialize server with persistent storage paths."""
        self.host = host
        self.port = port
        self.repo_root = repo_root or Path.cwd()
        if sqlite_file is not None and sqlite_file.parent.name not in ("build", "target"):
            self.markdown_output = markdown_output or (sqlite_file.parent / "BUGS.md")
            self.state_file = state_file or (sqlite_file.parent / "bugs_state.json")
            self.feedback_dir = feedback_dir or (sqlite_file.parent / "feedback")
        else:
            self.markdown_output = markdown_output or (self.repo_root / "build" / "BUGS.md")
            self.state_file = state_file or (self.repo_root / "build" / "bugs_state.json")
            if feedback_dir is not None:
                self.feedback_dir = feedback_dir
            elif markdown_output is not None and markdown_output.parent.name not in ("build", "target"):
                self.feedback_dir = markdown_output.parent
            else:
                self.feedback_dir = self.repo_root / "feedback"
        if self.feedback_dir != self.repo_root / "feedback":
            try:
                self.feedback_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        self.state_file = state_file or (self.repo_root / "build" / "bugs_state.json")
        self.sqlite_file = sqlite_file or (self.repo_root / "build" / "bugs.sqlite")
        self.attachments_dir = attachments_dir or (self.repo_root / "attachments")
        self.fresh = fresh
        self.bind_and_activate = bind_and_activate

        self._lock = threading.RLock()
        self._is_internal_saving = False

        self.sqlite_store = SQLiteBugStore(self.sqlite_file)
        self.exporter = MarkdownBugExporter(repo_root=self.repo_root)
        self.markdown_mtime = self.markdown_output.stat().st_mtime if self.markdown_output.exists() else 0.0
        self.feedback_mtime = self._get_feedback_dir_mtime()
        self.db_version: int = 1
        self.database = self._initialize_database()
        self._watcher_stop = threading.Event()
        if bind_and_activate:
            self._start_file_watcher()
            super().__init__((host, port), BugReportRequestHandler)
            self.actual_port = self.server_address[1]
        else:
            self.actual_port = port

    def get_request(self) -> Any:
        """Accept incoming connection and set a socket timeout to prevent lingering sockets."""
        sock, addr = super().get_request()
        sock.settimeout(10.0)
        return sock, addr

    def _get_feedback_dir_mtime(self) -> float:
        """Compute maximum mtime across feedback_dir and all BUG_*.md / WORM_*.md files within it."""
        if not self.feedback_dir.exists():
            return 0.0
        try:
            max_mtime = self.feedback_dir.stat().st_mtime
            with os.scandir(self.feedback_dir) as it:
                for entry in it:
                    if entry.is_file() and (entry.name.startswith(("BUG_", "WORM_")) and entry.name.endswith(".md")):
                        try:
                            m = entry.stat().st_mtime
                            if m > max_mtime:
                                max_mtime = m
                        except OSError:
                            pass
            return max_mtime
        except OSError:
            return 0.0

    def check_file_watch(self) -> bool:
        """Check if feedback_dir or markdown_output was modified externally and reload state."""
        with self._lock:
            if self._is_internal_saving:
                return False
            changed = False
            if self.markdown_output.exists():
                try:
                    curr_mtime = self.markdown_output.stat().st_mtime
                    if curr_mtime > self.markdown_mtime + 0.001:
                        changed = True
                except OSError:
                    pass

            curr_fb_mtime = self._get_feedback_dir_mtime()
            if curr_fb_mtime > self.feedback_mtime + 0.001:
                changed = True

            if changed:
                self.sync_with_feedback_dir()
                return True
            return False

    def _start_file_watcher(self) -> None:
        """Start background polling thread to watch feedback_dir and BUGS.md for external changes."""

        def watch_loop() -> None:
            import time

            while not self._watcher_stop.is_set():
                time.sleep(1.0)
                try:
                    self.check_file_watch()
                except Exception:
                    pass

        t = threading.Thread(target=watch_loop, daemon=True)
        t.start()

    def server_close(self) -> None:
        """Stop background file watcher and close server."""
        self._watcher_stop.set()
        if hasattr(self, "socket"):
            super().server_close()

    def _ensure_unique_bug_ids(self, db: BugDatabaseModel) -> None:
        """Ensure all bug IDs and UUIDs in database are unique, disambiguating any duplicates."""
        seen_ids: set[str] = set()
        seen_uuids: set[str] = set()
        for bug in db.bugs:
            if bug.id in seen_ids:
                bug.id = db.generate_bug_id()
                bug.uuid = str(uuid.uuid4())
            if bug.uuid in seen_uuids:
                bug.uuid = str(uuid.uuid4())
            seen_ids.add(bug.id)
            seen_uuids.add(bug.uuid)

    def _initialize_database(self) -> BugDatabaseModel:
        """Load existing database state from SQLite/JSON and perform R+M+W sync with feedback/ and BUGS.md."""
        db = None
        if not self.fresh:
            if self.sqlite_file.exists():
                db = self.sqlite_store.load_database()
            elif self.state_file.exists():
                db = self.exporter.load_state_json(self.state_file)

        if db is None:
            db = BugDatabaseModel(
                title="Hardware Bug Tracker",
                summary="Hardware engineering defects, PCB layout issues, and reproduction tracking.",
            )

        ws_root = self.repo_root.resolve()
        try:
            from provider.vcs.git_engine import get_git_root

            ws_root = get_git_root().resolve()
        except Exception:
            pass
        is_workspace = self.repo_root.resolve() == ws_root
        skip_detached = is_workspace and (self.sqlite_file.parent.name not in ("build", "target"))

        if not self.fresh and not db.bugs and not skip_detached and (self.repo_root / ".git").exists():
            try:
                from provider.bug_report.detached_branch import DetachedBranchBugStore

                detached_db = DetachedBranchBugStore(self.repo_root).load_database()
                if detached_db and detached_db.bugs:
                    db = detached_db
            except Exception:
                pass

        if not self.fresh and self.feedback_dir.exists():
            self.exporter.scan_and_sync_feedback_dir(self.feedback_dir, db, self.sqlite_store)

        self._ensure_unique_bug_ids(db)
        if not self.fresh:
            self.sqlite_store.save_database(db)
        return db

    def sync_with_markdown(self) -> Path:
        """Perform Read-Modify-Write (R+M+W) sync with feedback/ and BUGS.md and persist to stores."""
        with self._lock:
            if self.feedback_dir.exists():
                self.exporter.scan_and_sync_feedback_dir(self.feedback_dir, self.database, self.sqlite_store)
            if self.markdown_output.exists():
                md_db = self.exporter.parse_markdown(self.markdown_output)
                if md_db and md_db.bugs:
                    self.database = self.exporter.merge_databases(self.database, md_db)
                    self._ensure_unique_bug_ids(self.database)
            self._is_internal_saving = True
            try:
                return self.save_and_sync()
            finally:
                self._is_internal_saving = False

    def sync_with_feedback_dir(self) -> Dict[str, Any]:
        """Scan feedback/ directory, detect file renames, merge into SQLite, and update markdown."""
        with self._lock:
            if self.markdown_output.exists():
                md_db = self.exporter.parse_markdown(self.markdown_output)
                if md_db and md_db.bugs:
                    self.database = self.exporter.merge_databases(self.database, md_db)
            stats = self.exporter.scan_and_sync_feedback_dir(self.feedback_dir, self.database, self.sqlite_store)
            if stats.get("merged", 0) > 0 or stats.get("renamed", 0) > 0:
                self.save_and_sync()
            else:
                self.feedback_mtime = self._get_feedback_dir_mtime()
            return stats

    def save_and_sync(self, dirty_bug_ids: Optional[Collection[str]] = None) -> Path:
        """Persist bug database to SQLite, JSON, BUGS.md, and individual BUG_<id>.md files."""
        with self._lock:
            if not self._is_internal_saving and self.feedback_dir.exists():
                curr_fb_mtime = self._get_feedback_dir_mtime()
                if curr_fb_mtime > self.feedback_mtime + 0.001:
                    self.exporter.scan_and_sync_feedback_dir(self.feedback_dir, self.database, self.sqlite_store)
                    self.feedback_mtime = curr_fb_mtime
            self._is_internal_saving = True
            try:
                self.database.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                if dirty_bug_ids is not None:
                    dirty_set = set(dirty_bug_ids)
                    for bug in self.database.bugs:
                        if bug.id in dirty_set:
                            self.sqlite_store.save_bug(bug)
                    with self.sqlite_store._get_connection() as conn:
                        conn.execute(
                            "INSERT INTO metadata (key, value) VALUES ('updated_at', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                            (self.database.updated_at,),
                        )
                else:
                    self.sqlite_store.save_database(self.database)

                self.exporter.export_state_json(self.database, self.state_file)
                out = self.exporter.export_markdown(
                    self.database,
                    self.markdown_output,
                    store=self.sqlite_store,
                    feedback_dir=self.feedback_dir,
                    dirty_bug_ids=dirty_bug_ids,
                )
                if self.markdown_output.exists():
                    self.markdown_mtime = self.markdown_output.stat().st_mtime
                self.db_version += 1
                ws_root = self.repo_root.resolve()
                try:
                    from provider.vcs.git_engine import get_git_root

                    ws_root = get_git_root().resolve()
                except Exception:
                    pass
                is_workspace = self.repo_root.resolve() == ws_root
                skip_detached = is_workspace and (self.sqlite_file.parent.name not in ("build", "target"))

                if not skip_detached and not self.fresh and (self.repo_root / ".git").exists():
                    try:
                        from provider.bug_report.detached_branch import DetachedBranchBugStore

                        DetachedBranchBugStore(self.repo_root).commit_database(
                            self.database,
                            commit_message=f"Update bug database (v{self.db_version})",
                            sync_local_disk=False,
                            dirty_bug_ids=dirty_bug_ids,
                        )
                    except Exception:
                        pass
                # Update feedback_mtime after commit_database completes so it reflects post-commit disk state
                self.feedback_mtime = self._get_feedback_dir_mtime()
                return out
            finally:
                self._is_internal_saving = False

    def save_bug(self, bug: BugReportModel) -> None:
        """Save a single bug and sync to stores."""
        with self._lock:
            self.database.add_or_update(bug)
            self.save_and_sync(dirty_bug_ids=[bug.id])

    def delete_bug(self, bug_id: str) -> bool:
        """Delete a bug from all stores."""
        with self._lock:
            self._is_internal_saving = True
            try:
                deleted = self.sqlite_store.delete_bug(bug_id)
                self.database.bugs = [b for b in self.database.bugs if b.id != bug_id]
                self.exporter.export_state_json(self.database, self.state_file)
                self.exporter.export_markdown(self.database, self.markdown_output, feedback_dir=self.feedback_dir)
                md_path = self.feedback_dir / f"{bug_id.replace('-', '_')}.md"
                if md_path.exists():
                    try:
                        md_path.unlink()
                    except OSError:
                        pass
                return deleted
            finally:
                self._is_internal_saving = False

    def get_url(self) -> str:
        """Return reachable HTTP URL for browser."""
        port = getattr(self, "actual_port", None) or self.port
        return f"http://{self.host}:{port}"
