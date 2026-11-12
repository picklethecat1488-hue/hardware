"""Standalone HTTP Server for Interactive CAD/PCB Scope Workstation."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import mimetypes
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional
import urllib.parse
import uuid
import jinja2
import orjson

from model.bug_report import BugReportModel, BugStatus, BugSeverity, BugCategory, BugAttachmentModel
from provider.bug_report.sqlite_store import SQLiteBugStore
from provider.bug_report.markdown_exporter import MarkdownBugExporter
from model.scope import ScopeTargetBugRequest
from .pipeline import ScopeGeometryPipeline


class ScopeRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for Scope Workstation UI and REST APIs."""

    server: "ScopeServer"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Log HTTP requests through the dedicated Scope logger."""
        if hasattr(self, "server") and hasattr(self.server, "logger"):
            self.server.logger.info("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)

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

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send a JSON response using high-performance orjson with optional gzip compression."""
        try:
            body = orjson.dumps(data, option=orjson.OPT_SERIALIZE_NUMPY)
            accept_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
            use_gzip = accept_gzip and len(body) > 1024
            if use_gzip:
                body = gzip.compress(body, compresslevel=6)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if use_gzip:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            if hasattr(self, "server") and hasattr(self.server, "logger"):
                self.server.logger.warning("Client connection reset/aborted while sending JSON to %s", self.path)
            self.close_connection = True

    def _send_gzip(self, gz_data: bytes, status: int = 200) -> None:
        """Send pre-compressed gzip JSON directly, decompressing if client lacks gzip support."""
        try:
            accept_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
            if accept_gzip:
                body = gz_data
                is_gzip = True
            else:
                body = gzip.decompress(gz_data)
                is_gzip = False
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if is_gzip:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            if hasattr(self, "server") and hasattr(self.server, "logger"):
                self.server.logger.warning("Client connection reset/aborted while streaming gzip to %s", self.path)
            self.close_connection = True

    def _handle_serve_static(self, path: str) -> None:
        """Serve static vendor assets from provider/code_review/static/."""
        rel_path = path.lstrip("/")
        if rel_path.startswith("static/"):
            rel_path = rel_path[len("static/") :]

        file_path = self.server.static_dir / rel_path
        if not file_path.is_file():
            self.send_error(404, f"Static asset '{rel_path}' not found")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        if file_path.suffix in (".js", ".mjs"):
            content_type = "application/javascript"
        elif file_path.suffix == ".css":
            content_type = "text/css"
        elif file_path.suffix == ".wasm":
            content_type = "application/wasm"

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            accept_encoding = self.headers.get("Accept-Encoding", "")
            use_gzip = "gzip" in accept_encoding and len(content) > 1024

            if use_gzip:
                cache_key = (rel_path, file_path.stat().st_mtime)
                if not hasattr(self.server, "_static_gzip_cache"):
                    self.server._static_gzip_cache = {}
                if cache_key not in self.server._static_gzip_cache:
                    self.server._static_gzip_cache[cache_key] = gzip.compress(content, compresslevel=6)
                content = self.server._static_gzip_cache[cache_key]

            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            if use_gzip:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _handle_serve_attachment(self, path: str) -> None:
        """Serve attachment files from attachments/ directory."""
        clean_path = path.lstrip("/")
        if clean_path.startswith("attachments/"):
            clean_path = clean_path[len("attachments/") :]

        file_path = self.server.attachments_dir / clean_path
        if not file_path.is_file():
            self.send_error(404, f"Attachment '{clean_path}' not found")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        try:
            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _handle_serve_ui(self, query: Dict[str, List[str]]) -> None:
        """Render and serve the scope single-page application template."""
        template_path = self.server.template_dir / "scope.html.j2"
        if not template_path.is_file():
            self.send_error(500, "Scope template not found")
            return

        init_project = query.get("project", [""])[0]
        init_target = query.get("target", [""])[0]
        init_sub = query.get("subassembly", [""])[0]
        init_mode = query.get("mode", ["CAD"])[0].upper()
        raw_max_steps = query.get("max_steps", ["1000"])[0]
        init_max_steps = int(raw_max_steps) if raw_max_steps.isdigit() else 1000

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.server.template_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )
        template = env.get_template("scope.html.j2")
        html = template.render(
            init_project=init_project,
            init_target=init_target,
            init_subassembly=init_sub,
            init_mode=init_mode,
            init_max_steps=init_max_steps,
            port=self.server.actual_port,
        )

        body = html.encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests for UI and REST APIs."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/static/"):
            self._handle_serve_static(path)
            return

        if path.startswith("/attachments/"):
            self._handle_serve_attachment(path)
            return

        if path == "/favicon.ico":
            self._handle_serve_static("/static/scope-favicon.ico")
            return
        if path == "/favicon.svg":
            self._handle_serve_static("/static/scope-icon.svg")
            return

        match path:
            case "/" | "/scope" | "/scope/":
                self._handle_serve_ui(query)
            case "/api/scope/projects":
                projects = self.server.pipeline.get_projects()
                self._send_json({"projects": [p.model_dump() for p in projects]})
            case "/api/scope/sync":
                self.server.pipeline.sync()
                self._send_json({"status": "ok", "message": "Manifests synchronized and caches cleared"})
            case "/api/scope/load":
                project = query.get("project", [""])[0]
                target = query.get("target", [""])[0]
                subassembly = query.get("subassembly", [None])[0] or None
                mode = query.get("mode", ["CAD"])[0]
                step = int(query["step"][0]) if "step" in query and query["step"][0].isdigit() else None

                if not project or not target:
                    self.server.logger.warning(
                        "Rejecting /api/scope/load request with missing parameters: %s", self.path
                    )
                    self._send_json({"error": "Missing 'project' or 'target' query parameters"}, status=400)
                    return

                t0 = time.time()
                self.server.logger.info(
                    "Loading geometry for %s/%s [%s] (subassembly: %s, step: %s)...",
                    project,
                    target,
                    mode,
                    subassembly,
                    step,
                )
                try:
                    # 1. Fast direct streaming if cached gzip exists
                    cached_gz = self.server.pipeline.get_cached_gzip(
                        project=project,
                        target=target,
                        subassembly=subassembly,
                        mode=mode,
                        step_index=step,
                    )
                    if cached_gz is not None:
                        elapsed = time.time() - t0
                        self.server.logger.info(
                            "Delivered cached geometry for %s/%s [%s] in %.3fs (%.2f MB compressed)",
                            project,
                            target,
                            mode,
                            elapsed,
                            len(cached_gz) / (1024 * 1024),
                        )
                        self._send_gzip(cached_gz)
                        return

                    # 2. Compile / tessellate / persist
                    payload = self.server.pipeline.load_geometry(
                        project=project,
                        target=target,
                        subassembly=subassembly,
                        mode=mode,
                        step_index=step,
                    )
                    elapsed = time.time() - t0
                    self.server.logger.info(
                        "Successfully loaded geometry for %s/%s [%s] in %.2fs", project, target, mode, elapsed
                    )
                    self._send_json(payload)
                except Exception as err:
                    elapsed = time.time() - t0
                    self.server.logger.exception(
                        "Failed to load geometry for %s after %.2fs: %s", self.path, elapsed, err
                    )
                    self._send_json({"error": str(err)}, status=500)
            case "/api/scope/pcb_metadata":
                project = query.get("project", [""])[0]
                target = query.get("target", [""])[0]
                subassembly = query.get("subassembly", [None])[0] or None
                try:
                    payload = self.server.pipeline.load_geometry(
                        project=project,
                        target=target,
                        subassembly=subassembly,
                        mode="PCB",
                    )
                    self._send_json(payload.get("pcb_metadata", {}))
                except Exception as err:
                    self._send_json({"error": str(err)}, status=500)
            case "/api/scope/simulation_telemetry":
                project = query.get("project", [""])[0]
                target = query.get("target", [""])[0]
                try:
                    payload = self.server.pipeline.load_simulation_telemetry(project, target)
                    self._send_json(payload)
                except Exception as err:
                    self._send_json({"error": str(err)}, status=500)
            case "/api/scope/download_rrd":
                project = query.get("project", [""])[0]
                target = query.get("target", [""])[0]
                self._handle_download_rrd(project, target)
            case _:
                self.send_error(404, f"Endpoint {path} not found")

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST requests for Target Bug filing."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            data = orjson.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid JSON payload: {e}"}, status=400)
            return

        match path:
            case "/api/scope/target_bug":
                self._handle_target_bug(data)
            case "/api/scope/open_rerun":
                self._handle_open_rerun(data, parsed)
            case _:
                self.send_error(404, f"Endpoint {path} not found")

    def _handle_target_bug(self, data: Dict[str, Any]) -> None:
        """Handle direct bug submission from the Target Bug button."""
        try:
            req = ScopeTargetBugRequest.model_validate(data)
        except Exception as err:
            self._send_json({"error": f"Invalid Target Bug request: {err}"}, status=400)
            return

        try:
            store = SQLiteBugStore(self.server.sqlite_file)
            bug_id = store.generate_next_bug_id()

            # Save base64 image screenshot into attachments/<bug_id>/snapshot.png
            img_b64 = req.image_base64
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]

            img_bytes = base64.b64decode(img_b64)
            bug_att_dir = self.server.attachments_dir / bug_id
            bug_att_dir.mkdir(parents=True, exist_ok=True)
            img_path = bug_att_dir / "snapshot.png"
            with open(img_path, "wb") as f:
                f.write(img_bytes)

            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            rel_att_path = f"attachments/{bug_id}/snapshot.png"

            att = BugAttachmentModel(
                id=uuid.uuid4().hex[:8],
                filename="snapshot.png",
                file_type="image/png",
                file_path=rel_att_path,
                size_bytes=len(img_bytes),
                description="3D CAD/PCB annotated WebGL viewport snapshot",
                created_at=now_str,
            )
            attachments = [att]

            # Read and attach scope.py execution logs if available
            logs_content = ""
            scope_log_file = self.server.repo_root / "build" / "scope.log"
            if scope_log_file.exists():
                try:
                    with open(scope_log_file, "r", encoding="utf-8", errors="replace") as lf:
                        lines = lf.readlines()
                    tail_lines = lines[-500:] if len(lines) > 500 else lines
                    logs_content = "".join(tail_lines)
                    log_bytes = logs_content.encode("utf-8")
                    log_path = bug_att_dir / "scope.log"
                    with open(log_path, "wb") as lf_out:
                        lf_out.write(log_bytes)
                    rel_log_path = f"attachments/{bug_id}/scope.log"
                    log_att = BugAttachmentModel(
                        id=uuid.uuid4().hex[:8],
                        filename="scope.log",
                        file_type="text/plain",
                        file_path=rel_log_path,
                        size_bytes=len(log_bytes),
                        description="Scope workstation execution logs",
                        created_at=now_str,
                    )
                    attachments.append(log_att)
                except Exception as log_err:
                    self.server.log.warning("Could not attach scope.log to bug %s: %s", bug_id, log_err)

            # Build enriched description including 3D pin annotations
            desc_lines = [req.description.strip(), ""]
            if req.annotations:
                desc_lines.append("### Spatial 3D Annotations")
                for a in req.annotations:
                    desc_lines.append(f"- **Pin #{a.id}** `({a.x:.2f}, {a.y:.2f}, {a.z:.2f})`: {a.text}")
                desc_lines.append("")

            # Map severity and category
            sev = BugSeverity(req.severity) if req.severity in [s.value for s in BugSeverity] else BugSeverity.MEDIUM
            cat = BugCategory(req.category) if req.category in [c.value for c in BugCategory] else BugCategory.CAD

            rep_steps = [req.reproduction_steps] if req.reproduction_steps else ["python tools/scope.py"]
            bug = BugReportModel(
                id=bug_id,
                title=req.title,
                status=BugStatus.OPEN,
                severity=sev,
                category=cat,
                component=req.project,
                description="\n".join(desc_lines).strip(),
                reproduction_steps=rep_steps,
                logs=logs_content,
                attachments=attachments,
                created_at=now_str,
                updated_at=now_str,
            )

            store.save_bug(bug)

            # Export markdown to feedback/BUG_<ID>.md
            exporter = MarkdownBugExporter(repo_root=self.server.repo_root)
            md_path = exporter.export_individual_bug(bug, self.server.feedback_dir)

            self._send_json(
                {
                    "status": "ok",
                    "bug_id": bug.id,
                    "markdown_path": str(md_path),
                    "attachment_path": rel_att_path,
                }
            )
        except Exception as err:
            self._send_json({"error": f"Failed to file bug: {err}"}, status=500)

    def _handle_open_rerun(self, data: Dict[str, Any], parsed: urllib.parse.ParseResult) -> None:
        """Launch official Rerun Viewer for deep telemetry inspection."""
        query = urllib.parse.parse_qs(parsed.query)
        project = data.get("project") or query.get("project", ["cat_fountain"])[0]
        target = data.get("target") or query.get("target", ["product"])[0]
        rec = data.get("recording") or query.get("recording", [""])[0]

        rrd_path: Optional[Path] = None
        if rec and Path(rec).exists():
            rrd_path = Path(rec)
        else:
            candidates = [
                Path(f"recordings/{project}_3blade.rrd"),
                Path(f"recordings/{project}.rrd"),
                Path(f"recordings/{project}_{target}.rrd"),
            ]
            for cand in candidates:
                if cand.exists():
                    rrd_path = cand
                    break

        if rrd_path is None or not rrd_path.exists():
            recordings_dir = Path("recordings")
            if recordings_dir.exists():
                for f in recordings_dir.glob("*.rrd"):
                    if project in f.name:
                        rrd_path = f
                        break

        if rrd_path is None or not rrd_path.exists():
            self._send_json({"error": f"No simulation recording found for {project}/{target}"}, status=404)
            return

        try:
            import subprocess
            import shutil

            rerun_bin = shutil.which("rerun") or "rerun"
            subprocess.Popen([rerun_bin, str(rrd_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._send_json(
                {
                    "status": "ok",
                    "message": f"Launched Rerun Viewer with {rrd_path.name}",
                    "recording": str(rrd_path),
                }
            )
        except Exception as err:
            self._send_json({"error": f"Failed to launch Rerun Viewer: {err}"}, status=500)

    def _handle_download_rrd(self, project: str, target: str) -> None:
        """Stream the authentic Rerun .rrd recording file as an attachment download."""
        candidates = [
            Path(f"recordings/{project}_3blade.rrd"),
            Path(f"recordings/{project}.rrd"),
            Path(f"recordings/{project}_{target}.rrd"),
        ]
        rrd_path = None
        for cand in candidates:
            if cand.exists():
                rrd_path = cand
                break

        if rrd_path is None or not rrd_path.exists():
            recordings_dir = Path("recordings")
            if recordings_dir.exists():
                for f in recordings_dir.glob("*.rrd"):
                    if project in f.name:
                        rrd_path = f
                        break

        if rrd_path is None or not rrd_path.exists():
            self._send_json({"error": f"No simulation recording found for {project}/{target}"}, status=404)
            return

        content = rrd_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{rrd_path.name}"')
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


class ScopeServer(ThreadingHTTPServer):
    """Local Threading HTTP server for CAD/PCB Scope Workstation."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        repo_root: Optional[Path] = None,
        pipeline: Optional[ScopeGeometryPipeline] = None,
        sqlite_file: Optional[Path] = None,
        attachments_dir: Optional[Path] = None,
        feedback_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
        bind_and_activate: bool = True,
    ) -> None:
        """Initialize ScopeServer with static, template, and bug directories."""
        self.host = host
        self.port = port
        self.logger = logger or logging.getLogger("scope.server")
        self.repo_root = (repo_root or Path(__file__).resolve().parent.parent.parent).resolve()
        self.static_dir = self.repo_root / "provider" / "code_review" / "static"
        self.template_dir = self.repo_root / "provider" / "templates"
        self.feedback_dir = feedback_dir or (self.repo_root / "feedback")
        self.attachments_dir = attachments_dir or (self.repo_root / "attachments")
        self.sqlite_file = sqlite_file or (self.repo_root / "build" / "bugs.sqlite")
        self.pipeline = pipeline or ScopeGeometryPipeline()

        if bind_and_activate:
            super().__init__((host, port), ScopeRequestHandler)
            self.actual_port = self.server_address[1]
        else:
            self.actual_port = port

    def warm_up(
        self,
        project: str,
        target: str,
        subassembly: Optional[str] = None,
        mode: str = "CAD",
        step_index: Optional[int] = None,
    ) -> None:
        """Pre-warm geometry cache in a background daemon thread upon server startup."""

        def _warm_worker():
            try:
                t0 = time.time()
                self.logger.info("Background pre-warming geometry for %s/%s [%s]...", project, target, mode)
                self.pipeline.load_geometry(
                    project=project,
                    target=target,
                    subassembly=subassembly,
                    mode=mode,
                    step_index=step_index,
                )
                self.logger.info(
                    "Background pre-warming completed for %s/%s in %.2fs", project, target, time.time() - t0
                )
            except Exception as err:
                self.logger.warning("Background pre-warming error for %s/%s: %s", project, target, err)

        thread = threading.Thread(target=_warm_worker, daemon=True, name="ScopePrewarm")
        thread.start()

    def get_request(self) -> Any:
        """Accept incoming connection and set client socket timeout to prevent lingering sockets."""
        sock, addr = super().get_request()
        sock.settimeout(180.0)
        return sock, addr
