"""HTTP server and REST API for interactive Quake Diff Viewer & Smartlog workstation.

Serves the engineering diff workstation UI, DAG ancestor tree visualization,
working tree stage/unstage/discard/commit operations, commit split/combine,
merge conflict resolution, and cross-tool integration with code_review and bug_report.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.parse

import jinja2

from model.vcs import (
    BranchInfoModel,
    CommitNodeModel,
    DiffViewSessionModel,
    FileDiffModel,
    MergeConflictFileModel,
    WorkingTreeFileModel,
)
from provider.vcs.git_engine import GitEngine, get_git_root


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a local TCP port is already open and accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def ensure_server_running(port: int, script_name: str, args: Optional[List[str]] = None) -> None:
    """Ensure companion service (code_review or bug_report) is running on the given port."""
    if is_port_in_use(port):
        return
    script_path = Path(__file__).resolve().parent.parent.parent / script_name
    cmd = [sys.executable, str(script_path), "--port", str(port), "--no-browser"]
    if args:
        cmd.extend(args)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(15):
        time.sleep(0.1)
        if is_port_in_use(port):
            break


class DiffViewRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler dispatching diff viewer API endpoints and Quake dashboard UI."""

    server: "DiffViewServer"

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
                session = self.server.build_session()
                self._send_json(session.model_dump(mode="json"))
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
                include_feedback = query.get("include_feedback", ["true"])[0].lower() in ["true", "1"]
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
            case "/api/raw":
                commit = query.get("commit", ["working"])[0]
                file_path = query.get("file", [""])[0]
                parent = query.get("parent", ["false"])[0].lower() in ["true", "1"]
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
                self.end_headers()
                self.wfile.write(raw_bytes)
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
                target = data.get("commit", "") or data.get("target", "")
                target = target.strip()
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
                review_args = ["--port", "8765"] + (list(commits) if commits else [])
                ensure_server_running(8765, "code_review.py", review_args)
                target_url = f"http://127.0.0.1:8765/?revisions={rev_str}" if rev_str else "http://127.0.0.1:8765/"
                self._send_json({"status": "ok", "url": target_url})
            case "/api/open_bug":
                bug_id = data.get("bug_id", "").strip()
                commit = data.get("commit", "").strip()
                ensure_server_running(8766, "bug_report.py", ["--port", "8766"])
                if bug_id:
                    target_url = f"http://127.0.0.1:8766/#BUG-{bug_id}"
                elif commit:
                    target_url = f"http://127.0.0.1:8766/#new?commit={commit}"
                else:
                    target_url = "http://127.0.0.1:8766/"
                self._send_json({"status": "ok", "url": target_url})
            case _:
                self.send_error(404, "Endpoint not found")

    def _handle_serve_ui(self) -> None:
        """Render and return Jinja2 diff viewer template."""
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        template = env.get_template("diff_view.html.j2")
        session = self.server.build_session()
        html_out = template.render(session=session)

        encoded = html_out.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(encoded)

    def _handle_serve_static(self, path: str) -> None:
        """Serve shared static assets from provider static directory."""
        static_dir = Path(__file__).resolve().parent.parent / "static"
        relative = path.lstrip("/static/")
        target = (static_dir / relative).resolve()
        if not target.is_relative_to(static_dir) or not target.is_file():
            self.send_error(404, "Static file not found")
            return
        mime_type, _ = mimetypes.guess_type(str(target))
        if not mime_type:
            mime_type = "application/octet-stream"
        raw = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Serialize payload to JSON and dispatch HTTP response."""
        encoded = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)
        self.close_connection = True


class DiffViewServer(ThreadingHTTPServer):
    """Multi-threaded HTTP server powering the Quake Diff Viewer and Smartlog workstation."""

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
        port: int = 8767,
        repo_root: Optional[Path] = None,
        initial_branch: Optional[str] = None,
        initial_commit: Optional[str] = None,
        bind_and_activate: bool = True,
    ) -> None:
        """Initialize DiffViewServer instance."""
        self.host = host
        self.requested_port = port
        self.repo_root = repo_root or get_git_root()
        self.git_engine = GitEngine(repo_root=self.repo_root)
        self.initial_branch = initial_branch
        self.initial_commit = initial_commit

        if initial_branch:
            try:
                self.git_engine.checkout_branch(initial_branch)
            except RuntimeError:
                pass

        super().__init__((host, port), DiffViewRequestHandler, bind_and_activate=bind_and_activate)

    def build_session(self) -> DiffViewSessionModel:
        """Construct live DiffViewSessionModel reflecting current repository and working state."""
        branches = self.git_engine.get_branches()
        curr_branch = self.git_engine.get_current_branch()
        head_commit = self.git_engine.get_head_commit()
        smartlog_nodes = self.git_engine.get_smartlog_dag(limit=40)
        working_files = self.git_engine.get_working_tree_files()
        conflicts = self.git_engine.get_merge_conflicts()

        active_commit = self.initial_commit or "working"

        return DiffViewSessionModel(
            repo_name=self.repo_root.name,
            current_branch=curr_branch,
            head_commit=head_commit,
            active_commit=active_commit,
            selected_commits=[head_commit] if head_commit else [],
            branches=branches,
            smartlog_nodes=smartlog_nodes,
            working_files=working_files,
            conflicts=conflicts,
        )

    def get_url(self) -> str:
        """Return the fully-qualified base HTTP URL for the diff viewer dashboard."""
        return f"http://{self.host}:{self.server_port}"
