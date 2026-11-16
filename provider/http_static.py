"""Unified HTTP static & ES module asset serving with path-traversal protection."""

import gzip
from http.server import BaseHTTPRequestHandler
import json
import mimetypes
from pathlib import Path
from typing import Optional, Sequence

GZIP_MIN_BYTES = 1024
GZIP_COMPRESS_LEVEL = 6
GLSL_SUFFIX = ".glsl"

EXPLICIT_MIME_TYPES: dict[str, str] = {
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".glsl": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".wasm": "application/wasm",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".icns": "application/octet-stream",
}


def get_hardware_js_root(repo_root: Optional[Path] = None) -> Path:
    """Return canonical ``hardware/js`` directory path, falling back to codebase root for temp test repos."""
    default_js_root = Path(__file__).resolve().parent.parent / "js"
    if repo_root is not None:
        candidate = repo_root.resolve() / "js"
        if candidate.is_dir():
            return candidate
    return default_js_root


def get_hardware_static_dir(repo_root: Optional[Path] = None) -> Path:
    """Return canonical ``hardware/js/static`` directory path."""
    return get_hardware_js_root(repo_root) / "static"


def resolve_content_type(file_path: Path) -> str:
    """Resolve deterministic HTTP ``Content-Type`` header for ``file_path``."""
    if file_path.name == "manifest.json":
        return "application/manifest+json; charset=utf-8"
    suffix = file_path.suffix.lower()
    if suffix in EXPLICIT_MIME_TYPES:
        return EXPLICIT_MIME_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(str(file_path))
    if guessed:
        if guessed.startswith("text/"):
            return f"{guessed}; charset=utf-8"
        return guessed
    return "application/octet-stream"


def _resolve_safe_file(base_dir: Path, rel_subpath: str) -> Optional[Path]:
    """Resolve ``rel_subpath`` strictly inside ``base_dir`` or return ``None``."""
    resolved_base = base_dir.resolve()
    candidate = (resolved_base / rel_subpath.lstrip("/")).resolve()
    if not candidate.is_relative_to(resolved_base):
        return None
    if not candidate.is_file():
        return None
    return candidate


def serve_static_asset(
    handler: BaseHTTPRequestHandler,
    request_path: str,
    *,
    js_root: Optional[Path] = None,
    static_dirs: Optional[Sequence[Path]] = None,
    cache_control: str = "no-cache",
    enable_gzip: bool = True,
) -> None:
    """Serve ``/js/*`` and ``/static/*`` assets with strict path-traversal protection."""
    effective_js_root = (js_root or get_hardware_js_root()).resolve()
    effective_static_dirs = [d.resolve() for d in static_dirs] if static_dirs else [effective_js_root / "static"]

    clean_path = request_path.split("?", 1)[0]
    target_file: Optional[Path] = None

    if clean_path.startswith("/js/"):
        rel = clean_path.removeprefix("/js/")
        target_file = _resolve_safe_file(effective_js_root, rel)
    elif clean_path.startswith("/static/"):
        rel = clean_path.removeprefix("/static/")
        for sdir in effective_static_dirs:
            found = _resolve_safe_file(sdir, rel)
            if found is not None:
                target_file = found
                break
    else:
        rel = clean_path.lstrip("/")
        for sdir in effective_static_dirs:
            found = _resolve_safe_file(sdir, rel)
            if found is not None:
                target_file = found
                break

    if target_file is None:
        handler.send_error(404, f"Static asset '{clean_path}' not found")
        return

    content_type = resolve_content_type(target_file)
    try:
        raw_bytes = target_file.read_bytes()
    except OSError as exc:
        handler.send_error(500, f"Failed to read static asset: {exc}")
        return

    if target_file.suffix.lower() == GLSL_SUFFIX:
        glsl_text = raw_bytes.decode("utf-8")
        raw_bytes = f"export default {json.dumps(glsl_text)};\n".encode("utf-8")

    accept_encoding = handler.headers.get("Accept-Encoding", "") if handler.headers else ""
    compressible = content_type.startswith(("text/", "application/javascript", "application/json", "image/svg+xml"))
    use_gzip = enable_gzip and compressible and "gzip" in accept_encoding and len(raw_bytes) >= GZIP_MIN_BYTES

    payload = raw_bytes
    if use_gzip:
        stat = target_file.stat()
        cache_key = (str(target_file), stat.st_mtime_ns, stat.st_size)
        server_obj = getattr(handler, "server", None)
        gzip_cache = getattr(server_obj, "_static_gzip_cache", None) if server_obj is not None else None
        if gzip_cache is None and server_obj is not None:
            gzip_cache = {}
            server_obj._static_gzip_cache = gzip_cache
        if gzip_cache is not None and cache_key in gzip_cache:
            payload = gzip_cache[cache_key]
        else:
            payload = gzip.compress(raw_bytes, compresslevel=GZIP_COMPRESS_LEVEL)
            if gzip_cache is not None:
                gzip_cache[cache_key] = payload

    try:
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        if use_gzip:
            handler.send_header("Content-Encoding", "gzip")
        handler.send_header("Content-Length", str(len(payload)))
        handler.send_header("Cache-Control", cache_control)
        handler.end_headers()
        handler.wfile.write(payload)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        handler.close_connection = True
