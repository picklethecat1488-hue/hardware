"""HTTP server and REST API for unified Quake VCS Dashboard, Code Review, and Bug Report.

Serves the primary engineering diff workstation UI, DAG ancestor tree visualization,
working tree stage/unstage/discard/commit operations, commit split/combine,
merge conflict resolution, interactive line-by-line Code Review, and Bug Tracker.
"""

import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import socket
from typing import Any, Dict, List, Optional
import urllib.parse
import uuid

import jinja2

from model.bug_report import (
    BugAttachmentModel,
    BugCategory,
    BugReportModel,
    BugSeverity,
    BugStatus,
)
from model.code_review import CommentModel, ReviewSeverity, ReviewStatus
from model.vcs import (
    BranchInfoModel,
    CommitNodeModel,
    DiffViewSessionModel,
    FileDiffModel,
    MergeConflictFileModel,
    WorkingTreeFileModel,
)
from provider.bug_report.server import BugReportServer
from provider.code_review.server import ReviewServer
from provider.vcs.git_engine import GitEngine, extract_line_snippet, get_git_root


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler dispatching unified VCS dashboard, code review, and bug report APIs."""

    server: "DashboardServer"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Suppress default HTTP server logging to preserve clean console output."""
        return

    def do_GET(self) -> None:  # noqa: N802
        """Route GET requests for UI dashboards and data query endpoints."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/static/"):
            self._handle_serve_static(path)
            return

        if path.startswith("/attachments/") or path.startswith("/build/attachments/"):
            self._handle_serve_attachment(path)
            return

        match path:
            case "/" | "/index.html":
                self._handle_serve_diff_ui()
            case "/review" | "/review/":
                self._handle_serve_review_ui()
            case "/bugs" | "/bugs/":
                self._handle_serve_bug_ui()
            case "/api/session":
                referer = self.headers.get("Referer", "")
                if query.get("type", [""])[0] == "review" or "/review" in referer:
                    self._send_json(self.server.review_server.session.model_dump(mode="json"))
                else:
                    session = self.server.build_session()
                    self._send_json(session.model_dump(mode="json"))
            case "/api/review/session":
                self._send_json(self.server.review_server.session.model_dump(mode="json"))
            case "/api/commits":
                limit_str = query.get("limit", ["40"])[0]
                limit = int(limit_str) if limit_str.isdigit() else 40
                commits = self.server.git_engine.get_smartlog_dag(limit=limit)
                self._send_json([c.model_dump(mode="json") for c in commits])
            case "/api/branches":
                branches = self.server.git_engine.get_branches()
                self._send_json([b.model_dump(mode="json") for b in branches])
            case "/api/working":
                files = self.server.git_engine.get_working_tree_files()
                self._send_json([f.model_dump(mode="json") for f in files])
            case "/api/conflicts":
                conflicts = self.server.git_engine.get_merge_conflicts()
                self._send_json([c.model_dump(mode="json") for c in conflicts])
            case "/api/files":
                commit = query.get("commit", ["working"])[0]
                referer = self.headers.get("Referer", "")
                default_fb = "false" if "/review" in referer else "true"
                include_feedback = query.get("include_feedback", [default_fb])[0].lower() in ["true", "1"]
                files = self.server.git_engine.get_changed_files(commit, include_feedback=include_feedback)
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
                parent = (side == "old") or (query.get("parent", ["false"])[0].lower() in ["true", "1"])
                if not file_path:
                    self._send_json({"error": "Missing file parameter"}, status=400)
                    return
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
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(raw_bytes)
            case "/api/database":
                self._send_json(self.server.bug_server.database.model_dump(mode="json"))
            case "/api/next_bug_id":
                self._send_json({"id": self.server.bug_server.database.generate_bug_id()})
            case "/api/version":
                self._send_json({"version": self.server.bug_server.database.updated_at})
            case _:
                self.send_error(404, "Endpoint not found")

    def do_POST(self) -> None:  # noqa: N802
        """Route POST requests for mutating actions."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body"}, status=400)
            return

        match path:
            case "/api/sync":
                res = self.server.git_engine.fetch_or_pull()
                self._send_json(res)
            case "/api/checkout_branch":
                branch = data.get("branch", "").strip()
                if not branch:
                    self._send_json({"error": "Missing branch parameter"}, status=400)
                    return
                try:
                    self.server.git_engine.checkout_branch(branch)
                    self._send_json({"status": "ok", "branch": branch})
                except RuntimeError as e:
                    self._send_json({"error": str(e)}, status=400)
            case "/api/goto":
                target = (data.get("commit", "") or data.get("target", "")).strip()
                if not target:
                    self._send_json({"error": "Missing commit target"}, status=400)
                    return
                try:
                    self.server.git_engine.checkout_branch(target)
                    self._send_json({"status": "ok", "commit": target})
                except RuntimeError as e:
                    self._send_json({"error": str(e)}, status=400)
            case "/api/stage":
                file_path = data.get("file", "").strip()
                if not file_path:
                    self._send_json({"error": "Missing file parameter"}, status=400)
                    return
                try:
                    self.server.git_engine.stage_file(file_path)
                    self._send_json({"status": "ok", "staged": file_path})
                except RuntimeError as e:
                    self._send_json({"error": str(e)}, status=400)
            case "/api/unstage":
                file_path = data.get("file", "").strip()
                if not file_path:
                    self._send_json({"error": "Missing file parameter"}, status=400)
                    return
                try:
                    self.server.git_engine.unstage_file(file_path)
                    self._send_json({"status": "ok", "unstaged": file_path})
                except RuntimeError as e:
                    self._send_json({"error": str(e)}, status=400)
            case "/api/discard":
                file_path = data.get("file", "").strip()
                if not file_path:
                    self._send_json({"error": "Missing file parameter"}, status=400)
                    return
                try:
                    self.server.git_engine.discard_file(file_path)
                    self._send_json({"status": "ok", "discarded": file_path})
                except RuntimeError as e:
                    self._send_json({"error": str(e)}, status=400)
            case "/api/commit":
                message = data.get("message", "").strip()
                if not message:
                    self._send_json({"error": "Commit message cannot be empty"}, status=400)
                    return
                try:
                    sha = self.server.git_engine.commit_staged(message)
                    self._send_json({"status": "ok", "commit_hash": sha})
                except RuntimeError as e:
                    self._send_json({"error": str(e)}, status=400)
            case "/api/split":
                commit_hash = data.get("commit", "HEAD").strip()
                try:
                    res = self.server.git_engine.split_commit(commit_hash)
                    self._send_json(res)
                except RuntimeError as e:
                    self._send_json({"error": str(e)}, status=400)
            case "/api/combine":
                commits = data.get("commits", [])
                message = data.get("message", "Combined commits").strip()
                if not commits:
                    self._send_json({"error": "No commits provided to combine"}, status=400)
                    return
                try:
                    sha = self.server.git_engine.combine_commits(commits, message)
                    self._send_json({"status": "ok", "commit_hash": sha})
                except (RuntimeError, ValueError) as e:
                    self._send_json({"error": str(e)}, status=400)
            case "/api/resolve_conflict":
                file_path = data.get("file", "").strip()
                resolution = data.get("resolution", "mark_resolved").strip()
                if not file_path:
                    self._send_json({"error": "Missing file parameter"}, status=400)
                    return
                try:
                    res = self.server.git_engine.resolve_conflict(file_path, resolution)
                    self._send_json(res)
                except (RuntimeError, ValueError) as e:
                    self._send_json({"error": str(e)}, status=400)
            case "/api/open_code_review":
                commits = data.get("commits", [])
                rev_str = ",".join(commits)
                target_url = f"/review?revisions={rev_str}" if rev_str else "/review"
                self._send_json({"status": "ok", "url": target_url})
            case "/api/open_bug":
                bug_id = data.get("bug_id", "").strip()
                commit = data.get("commit", "").strip()
                if bug_id:
                    target_url = f"/bugs#BUG-{bug_id}"
                elif commit:
                    target_url = f"/bugs#new?commit={commit}"
                else:
                    target_url = "/bugs"
                self._send_json({"status": "ok", "url": target_url})
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
                out_path = self.server.review_server.save_and_sync()
                self._send_json({"status": "ok", "path": str(out_path)})
            case "/api/sync_feedback":
                res = self.server.sync_feedback()
                self._send_json(res)
            case "/api/commit_reviewed":
                query = urllib.parse.parse_qs(parsed.query)
                commit = query.get("commit", [""])[0] or (data.get("commit", "") if isinstance(data, dict) else "")
                short_rev = commit[:8] if commit else "current"
                print(f"\n[Dashboard Review] ✨ All changed files reviewed for commit {short_rev}!\n")
                self._send_json({"status": "ok", "commit": commit})
            case "/api/commit_update":
                self._handle_commit_update(data)
            case "/api/bugs":
                self._handle_save_bug(data)
            case "/api/bugs/delete":
                self._handle_delete_bug(data)
            case "/api/upload":
                self._handle_file_upload(data)
            case "/api/exit":
                out_path = self.server.bug_server.save_and_sync()
                self._send_json({"status": "saved_and_exited", "path": str(out_path), "redirect_to": "/"})
            case _:
                self.send_error(404, "Endpoint not found")

    def do_DELETE(self) -> None:  # noqa: N802
        """Route DELETE requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        match path:
            case "/api/comment":
                cid = query.get("id", [""])[0]
                if not cid:
                    self._send_json({"error": "Missing id parameter"}, status=400)
                    return
                self.server.review_server.session.comments = [
                    c for c in self.server.review_server.session.comments if c.id != cid
                ]
                self.server.review_server.save_and_sync()
                self._send_json({"status": "ok", "deleted": cid})
            case _:
                self.send_error(404, "Endpoint not found")

    def _handle_serve_diff_ui(self) -> None:
        """Render and return Jinja2 VCS diff view dashboard template."""
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        template = env.get_template("diff_view.html.j2")
        session = self.server.build_session()
        html_out = template.render(
            session=session,
            active_branch=self.server.active_branch,
            active_commit=self.server.active_commit,
        )
        self._send_html(html_out)

    def _handle_serve_review_ui(self) -> None:
        """Render and return Jinja2 code review dashboard template."""
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        template = env.get_template("code_review.html.j2")
        html_out = template.render(session=self.server.review_server.session)
        self._send_html(html_out)

    def _handle_serve_bug_ui(self) -> None:
        """Render and return Jinja2 bug report dashboard template."""
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template("bug_report.html.j2")
        db_dump = self.server.bug_server.database.model_dump(mode="json")
        html_content = template.render(
            database=self.server.bug_server.database,
            database_json=json.dumps(db_dump),
            statuses=[s.value for s in BugStatus],
            severities=[s.value for s in BugSeverity],
            categories=[c.value for c in BugCategory],
            server_port=self.server.actual_port,
        )
        self._send_html(html_content)

    def _handle_serve_static(self, path: str) -> None:
        """Serve static files such as JavaScript vendor bundles and CSS."""
        static_dir = Path(__file__).resolve().parent.parent / "code_review" / "static"
        filename = path.removeprefix("/static/").strip("/")
        file_target = (static_dir / filename).resolve()
        if not str(file_target).startswith(str(static_dir)) or not file_target.is_file():
            self.send_error(404, "Static asset not found")
            return
        mime_type, _ = mimetypes.guess_type(str(file_target))
        if not mime_type:
            mime_type = "application/javascript" if filename.endswith(".js") else "text/plain"
        content = file_target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(content)

    def _handle_serve_attachment(self, path: str) -> None:
        """Serve uploaded attachments."""
        rel = path.lstrip("/")
        file_target = (self.server.repo_root / rel).resolve()
        if not file_target.is_file():
            self.send_error(404, "Attachment not found")
            return
        mime_type, _ = mimetypes.guess_type(str(file_target))
        if not mime_type:
            mime_type = "application/octet-stream"
        content = file_target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(content)

    def _handle_add_comment(self, data: Dict[str, Any]) -> None:
        """Add a review comment to the session."""
        commit_target = data.get("commit", "working")
        snippet = extract_line_snippet(
            file_path=data.get("file_path", ""),
            start_line=int(data.get("start_line", 1)),
            end_line=int(data.get("end_line", 1)),
            commit=commit_target,
            repo_root=self.server.repo_root,
        )
        now_str = datetime.now(timezone.utc).isoformat()
        comment = CommentModel(
            id=data.get("id") or uuid.uuid4().hex[:12],
            file_path=data.get("file_path", ""),
            start_line=int(data.get("start_line", 1)),
            end_line=int(data.get("end_line", 1)),
            severity=ReviewSeverity(data.get("severity", ReviewSeverity.MUST_FIX.value)),
            body=data.get("body", ""),
            author=data.get("author", "Reviewer"),
            code_snippet=snippet,
            created_at=now_str,
            commit=commit_target,
        )
        self.server.review_server.session.comments.append(comment)
        self.server.review_server.session.auto_update_status_on_comment()
        self.server.review_server.save_and_sync()
        self._send_json(comment.model_dump(mode="json"))

    def _handle_edit_comment(self, data: Dict[str, Any]) -> None:
        """Edit an existing review comment."""
        cid = data.get("id", "")
        for comment in self.server.review_server.session.comments:
            if comment.id == cid:
                if "body" in data:
                    comment.body = data["body"]
                if "severity" in data:
                    comment.severity = ReviewSeverity(data["severity"])
                if "resolved" in data:
                    comment.resolved = bool(data["resolved"])
                self.server.review_server.session.auto_update_status_on_comment()
                self.server.review_server.save_and_sync()
                self._send_json(comment.model_dump(mode="json"))
                return
        self._send_json({"error": "Comment not found"}, status=404)

    def _handle_update_file_status(self, data: Dict[str, Any]) -> None:
        """Update review status of a file."""
        file_path = data.get("file_path", "")
        reviewed = bool(data.get("reviewed", False))
        commit = data.get("commit", "working")
        for f in self.server.review_server.session.files:
            if f.file_path == file_path and f.commit == commit:
                f.reviewed = reviewed
                break
        else:
            from model.code_review import FileReviewModel

            self.server.review_server.session.files.append(
                FileReviewModel(file_path=file_path, reviewed=reviewed, commit=commit)
            )
        self.server.review_server.save_and_sync()
        self._send_json({"status": "ok", "file_path": file_path, "reviewed": reviewed})

    def _handle_update_verdict(self, data: Dict[str, Any]) -> None:
        """Update code review verdict and persist without server shutdown."""
        verdict_str = data.get("verdict", "")
        if verdict_str in [s.value for s in ReviewStatus]:
            self.server.review_server.session.verdict = ReviewStatus(verdict_str)
        out_path = self.server.review_server.save_and_sync()
        self._send_json(
            {
                "status": "ok",
                "session": self.server.review_server.session.model_dump(mode="json"),
                "exported_to": str(out_path),
                "terminating": False,
                "redirect_to": "/",
            }
        )

    def _handle_commit_update(self, data: Dict[str, Any]) -> None:
        """Handle commit update event (rebase, amend)."""
        orig_commit = data.get("original_commit", "")
        new_commit = data.get("new_commit", "")
        if orig_commit and new_commit:
            self.server.review_server.update_commit_hash(orig_commit, new_commit)
            self._send_json({"status": "ok", "original_commit": orig_commit, "new_commit": new_commit})
        else:
            self._send_json({"error": "Missing commit hashes"}, status=400)

    def _handle_save_bug(self, data: Dict[str, Any]) -> None:
        """Save or update a bug report."""
        bug_id = data.get("id")
        title = data.get("title", "")
        if not bug_id:
            bug_id = self.server.bug_server.database.generate_bug_id()
        bug = self.server.bug_server.database.get_bug(bug_id)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if not bug:
            bug = BugReportModel(
                id=bug_id,
                title=title or "Untitled Defect",
                status=BugStatus(data.get("status", BugStatus.OPEN.value)),
                severity=BugSeverity(data.get("severity", BugSeverity.MEDIUM.value)),
                category=BugCategory(data.get("category", BugCategory.PCB.value)),
                component=data.get("component", ""),
                description=data.get("description", ""),
                steps_to_reproduce=data.get("steps_to_reproduce", []),
                attachments=[BugAttachmentModel(**a) for a in data.get("attachments", [])],
                created_at=now_str,
                updated_at=now_str,
                commit=data.get("commit"),
            )
            self.server.bug_server.database.add_or_update(bug)
        else:
            if title:
                bug.title = title
            if "status" in data and data["status"] in [s.value for s in BugStatus]:
                bug.status = BugStatus(data["status"])
                if bug.status in (BugStatus.RESOLVED, BugStatus.CLOSED):
                    bug.resolved_at = now_str
                else:
                    bug.resolved_at = None
            if "severity" in data and data["severity"] in [s.value for s in BugSeverity]:
                bug.severity = BugSeverity(data["severity"])
            if "category" in data and data["category"] in [c.value for c in BugCategory]:
                bug.category = BugCategory(data["category"])
            if "component" in data:
                bug.component = data["component"]
            if "description" in data:
                bug.description = data["description"]
            if "resolution_notes" in data:
                bug.resolution_notes = data["resolution_notes"]
            if "steps_to_reproduce" in data:
                bug.steps_to_reproduce = data["steps_to_reproduce"]
            if "attachments" in data:
                bug.attachments = [BugAttachmentModel(**a) for a in data["attachments"]]
            bug.updated_at = now_str

        self.server.bug_server.save_and_sync()
        self._send_json(bug.model_dump(mode="json"))

    def _handle_delete_bug(self, data: Dict[str, Any]) -> None:
        """Delete a bug report by ID."""
        bug_id = data.get("id")
        self.server.bug_server.database.bugs = [b for b in self.server.bug_server.database.bugs if b.id != bug_id]
        self.server.bug_server.save_and_sync()
        self._send_json({"status": "deleted", "id": bug_id})

    def _handle_file_upload(self, data: Dict[str, Any]) -> None:
        """Save base64 encoded file upload to attachments directory."""
        filename = data.get("filename", f"attachment_{uuid.uuid4().hex[:8]}.txt")
        file_type = data.get("file_type", "reference")
        desc = data.get("description", "")
        b64_content = data.get("content_base64", "")
        text_content = data.get("content_text", "")

        att_dir = self.server.repo_root / "build" / "attachments"
        att_dir.mkdir(parents=True, exist_ok=True)
        dest_path = att_dir / filename

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

    def _send_html(self, html: str) -> None:
        """Send HTML payload with UTF-8 encoding."""
        encoded = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)
        self.close_connection = True

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send JSON response payload."""
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)
        self.close_connection = True


class DashboardServer(ThreadingHTTPServer):
    """Unified HTTP server for VCS Smartlog diff workstation, code review, and bug tracking."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8767,
        repo_root: Optional[Path] = None,
        initial_branch: Optional[str] = None,
        initial_commit: Optional[str] = None,
        sqlite_bug_file: Optional[Path] = None,
        sqlite_review_file: Optional[Path] = None,
        markdown_bugs_path: Optional[Path] = None,
        markdown_review_path: Optional[Path] = None,
        revisions: Optional[List[str]] = None,
        fresh: bool = False,
        bind_and_activate: bool = True,
    ) -> None:
        """Initialize the unified dashboard workstation server."""
        self.repo_root = (repo_root or get_git_root()).resolve()
        self.git_engine = GitEngine(repo_root=self.repo_root)
        self.host = host
        self.port = port
        self.active_branch = initial_branch or self.git_engine.get_current_branch()
        self.active_commit = initial_commit or "working"

        md_review = markdown_review_path
        if md_review is None and sqlite_review_file and sqlite_review_file.parent.name != "build":
            md_review = sqlite_review_file.parent / "CR.md"

        md_bugs = markdown_bugs_path
        if md_bugs is None and sqlite_bug_file and sqlite_bug_file.parent.name != "build":
            md_bugs = sqlite_bug_file.parent / "BUGS.md"

        review_state = sqlite_review_file.with_suffix(".json") if sqlite_review_file else None
        bug_state = sqlite_bug_file.with_suffix(".json") if sqlite_bug_file else None

        # Embedded review and bug servers without duplicate socket binding
        self.review_server = ReviewServer(
            host=host,
            port=port,
            repo_root=self.repo_root,
            markdown_output=md_review,
            state_file=review_state,
            sqlite_file=sqlite_review_file,
            revisions=revisions,
            fresh=fresh,
            bind_and_activate=False,
        )
        self.bug_server = BugReportServer(
            host=host,
            port=port,
            repo_root=self.repo_root,
            markdown_output=md_bugs,
            state_file=bug_state,
            sqlite_file=sqlite_bug_file,
            fresh=fresh,
            bind_and_activate=False,
        )

        if bind_and_activate:
            bound_port = port
            while True:
                try:
                    super().__init__((host, bound_port), DashboardRequestHandler)
                    break
                except OSError as err:
                    if bound_port == 0 or bound_port > port + 50:
                        raise err
                    bound_port += 1
            self.actual_port = self.server_port
            self.socket.settimeout(10.0)
        else:
            self.actual_port = port

    def get_url(self) -> str:
        """Return the base local HTTP URL for the dashboard workstation."""
        return f"http://{self.host}:{self.actual_port}"

    def build_session(self) -> DiffViewSessionModel:
        """Build DiffViewSessionModel snapshot of the current repository state."""
        branches = self.git_engine.get_branches()
        curr_branch = self.git_engine.get_current_branch()
        head_sha = self.git_engine.get_head_commit()
        smartlog_nodes = self.git_engine.get_smartlog_dag(limit=50)
        working_files = self.git_engine.get_working_tree_files()
        conflicts = self.git_engine.get_merge_conflicts()
        agent_feedback = [f for f in working_files if f.is_feedback]

        # Match bug reports with commits
        bug_dict = {b.id: b for b in self.bug_server.database.bugs}
        for node in smartlog_nodes:
            bug_ids = re.findall(r"\bBUG-\d+\b", node.subject)
            tags = []
            for bid in bug_ids:
                if bid in bug_dict:
                    tags.append(bug_dict[bid])
                else:
                    tags.append(
                        BugReportModel(
                            id=bid,
                            title=bid,
                            status=BugStatus.OPEN,
                            severity=BugSeverity.MEDIUM,
                            category=BugCategory.PCB,
                        )
                    )
            node.bug_tags = tags

        return DiffViewSessionModel(
            repo_name=self.repo_root.name,
            branches=branches,
            current_branch=curr_branch,
            head_commit=head_sha,
            active_commit=self.active_commit,
            smartlog_nodes=smartlog_nodes,
            working_files=working_files,
            conflicts=conflicts,
            agent_feedback_files=agent_feedback,
        )

    def sync_feedback(self) -> Dict[str, Any]:
        """Synchronize review and bug report feedback from workspace feedback/ directory."""
        review_res = self.review_server.sync_feedback()
        bug_res = self.bug_server.sync_with_feedback_dir()
        return {"status": "ok", "review": review_res, "bugs": bug_res}

    def server_close(self) -> None:
        """Close server sockets and cleanup sub-servers."""
        self.review_server.server_close()
        self.bug_server.server_close()
        if hasattr(self, "socket") and self.socket:
            try:
                super().server_close()
            except Exception:
                pass
