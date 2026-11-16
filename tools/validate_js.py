#!/usr/bin/env python3
"""Compile and statically lint JavaScript ES modules and Jinja2 HTML templates via Oxlint.

Enforces across ``js/``, ``tests/js/``, and ``provider/templates/*.html.j2``:
1. ``oxlint --deny-warnings`` across all first-party ES modules, modifiable vendor addons
   (``js/static/vendor/three/addons/**/*.js``), and ``tests/js/*.test.mjs``.
2. Strict Zero-Globals isolation: ``js/core/runtime_context.js`` is the sole file permitted
   to reference ``globalThis`` / ``window`` / ``document`` / ``localStorage`` / ``sessionStorage``.
3. Zero inline executable ``<script>`` blocks and zero inline HTML ``on*="..."`` event
   handler attributes in workstation ``.html.j2`` templates (``ibom.html.j2`` exempted).
4. Strict JSON syntax validation for ``<script type="application/json">`` and
   ``<script type="importmap">`` blocks, plus on-disk resolution of ``/js/...`` and
   ``/static/...`` script ``src`` and importmap targets.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from enum import Enum
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Sequence, Tuple

import jinja2

REPO_ROOT = Path(__file__).resolve().parent.parent

UNMODIFIABLE_VENDOR_FILENAMES = frozenset({"three.module.js", "highlight.js", "highlight.min.js"})
RUNTIME_CONTEXT_FILENAME = "runtime_context.js"
INLINE_EVENT_ATTR_PREFIX = "on"
SAMPLE_COMMIT_HASH = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
SAMPLE_SHORT_HASH = "a1b2c3d4"
DEFAULT_SERVER_PORT = 8877
DEFAULT_SCOPE_MAX_STEPS = 1000

JS_TOKEN_OR_COMMENT_RE = re.compile(
    r"""
    (?P<block_comment>/\*[\s\S]*?\*/)
    | (?P<line_comment>//[^\n]*)
    | (?P<sq_str>'(?:\\.|[^'\\\n])*')
    | (?P<dq_str>"(?:\\.|[^"\\\n])*")
    | (?P<tpl_str>`(?:\\.|[^`\\])*`)
    """,
    re.VERBOSE,
)
DIRECT_GLOBAL_ACCESS_RE = re.compile(r"(?<![.\w$])(window|globalThis|document|localStorage|sessionStorage)\s*\.")
NO_UNDEF_DISABLE_RE = re.compile(r"oxlint-disable[^\n]*\bno-undef\b")
GLSL_IMPORT_RE = re.compile(r"""^\s*import\s+[\w*{},\s]+\s+from\s+["']([^"']+\.glsl)["']""", re.MULTILINE)


class ScriptKind(str, Enum):
    """Classification of an extracted HTML ``<script>`` element."""

    CLASSIC = "classic"
    MODULE = "module"
    JSON_DATA = "application/json"
    IMPORTMAP = "importmap"


class MockReviewVerdict(str, Enum):
    """Review verdict enum stub matching ``ReviewStatus``."""

    IN_REVIEW = "IN_REVIEW"


@dataclass(frozen=True)
class ExtractedScript:
    """Single ``<script>`` block extracted from a rendered HTML document."""

    kind: ScriptKind
    code: str
    start_line: int
    src_attr: Optional[str] = None
    id_attr: Optional[str] = None


@dataclass(frozen=True)
class ExtractedInlineHandler:
    """Single HTML inline ``on*="..."`` event handler attribute."""

    tag_name: str
    attr_name: str
    code: str
    line: int


@dataclass(frozen=True)
class TemplateVariant:
    """Named rendering context variant for a Jinja2 HTML template."""

    variant_name: str
    context: Dict[str, object]
    autoescape: bool = False


@dataclass(frozen=True)
class MockBranch:
    """Lightweight branch fixture for rendering ``diff_view.html.j2``."""

    name: str
    is_current: bool = False
    is_remote: bool = False
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0

    @property
    def is_release_branch_candidate(self) -> bool:
        """Return True when the branch name represents a main or release branch."""
        return self.name in ("main", "master", "origin/main", "origin/master")


@dataclass(frozen=True)
class MockBugTag:
    """Lightweight bug tag fixture for smartlog commit rendering."""

    id: str
    title: str = ""
    status: str = "OPEN"
    severity: str = "LOW"


@dataclass(frozen=True)
class MockCommitNode:
    """Lightweight smartlog commit node fixture."""

    commit_hash: str
    short_hash: str
    author: str = "User"
    email: str = "user@workspace"
    date: str = "2026-11-12"
    time: str = "12:00:00"
    relative_date: str = "1m ago"
    subject: str = "feat: validate js"
    body: str = ""
    parents: Tuple[str, ...] = ()
    children: Tuple[str, ...] = ()
    branches: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    is_head: bool = False
    is_ancestor_top: bool = False
    is_merged: bool = False
    is_merged_into_tracking: bool = False
    ancestor_name: Optional[str] = None
    graph_symbol: str = "@"
    graph_art: str = "@"
    bug_tags: Tuple[MockBugTag, ...] = ()
    pr_status: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    additions: int = 10
    deletions: int = 2
    files_count: int = 1
    is_feedback_only: bool = False
    cr_open_count: int = 0
    cr_resolved_count: int = 0
    cr_total_count: int = 0
    cr_reviewed: bool = False


@dataclass(frozen=True)
class MockWorkingFile:
    """Lightweight working tree file fixture."""

    path: str
    status: str = "M"
    index_status: str = " "
    worktree_status: str = "M"
    is_staged: bool = False
    is_untracked: bool = False
    is_conflicted: bool = False
    is_feedback: bool = False
    is_lfs: bool = False
    additions: int = 5
    deletions: int = 1


@dataclass(frozen=True)
class MockConflictFile:
    """Lightweight merge conflict fixture."""

    path: str
    conflict_type: str = "both_modified"
    conflict_markers_count: int = 1
    ours_summary: str = ""
    theirs_summary: str = ""


@dataclass(frozen=True)
class MockDiffSession:
    """Lightweight session fixture for ``diff_view.html.j2``."""

    repo_name: str = "hardware"
    repo_root: str = ""
    repo_web_url: Optional[str] = None
    github_repo: str = ""
    current_branch: str = "main"
    active_branch: str = "main"
    current_user: str = "User"
    head_commit: str = SAMPLE_COMMIT_HASH
    active_commit: str = "working"
    active_file: Optional[str] = None
    selected_commits: List[str] = field(default_factory=list)
    branches: List[MockBranch] = field(default_factory=list)
    smartlog_nodes: List[MockCommitNode] = field(default_factory=list)
    working_files: List[MockWorkingFile] = field(default_factory=list)
    conflicts: List[MockConflictFile] = field(default_factory=list)
    initial_sync_done: bool = False
    author_blacklist: List[str] = field(default_factory=list)

    def model_dump(self, mode: str = "python") -> Dict[str, object]:
        """Serialize session fields for Jinja2 ``model_dump`` callers."""
        _ = mode
        return asdict(self)


@dataclass(frozen=True)
class MockReviewSession:
    """Lightweight session fixture for ``code_review.html.j2``."""

    title: str = "Code Review: hardware"
    repo_name: str = "hardware"
    repo_root: str = ""
    verdict: MockReviewVerdict = MockReviewVerdict.IN_REVIEW
    status: str = "IN_REVIEW"
    summary: str = ""
    revisions: List[str] = field(default_factory=list)
    commits: List[Dict[str, object]] = field(default_factory=list)
    files: Dict[str, Dict[str, str]] = field(default_factory=dict)
    comments: List[Dict[str, object]] = field(default_factory=list)
    author_blacklist: List[str] = field(default_factory=list)

    def model_dump(self, mode: str = "python") -> Dict[str, object]:
        """Serialize review session fields for Jinja2 ``model_dump`` callers."""
        _ = mode
        data = asdict(self)
        data["verdict"] = self.verdict.value
        return data


@dataclass(frozen=True)
class MockBugItem:
    """Lightweight bug entry fixture for ``bug_report.html.j2``."""

    id: str = "BUG-SAMPLE-101"
    title: str = "Sample defect"
    status: str = "OPEN"
    severity: str = "MEDIUM"
    category: str = "INFRASTRUCTURE"
    component: str = "scope"


@dataclass(frozen=True)
class MockBugDatabase:
    """Lightweight bug database fixture for ``bug_report.html.j2``."""

    title: str = "Hardware Engineering Bug Tracker"
    bugs: List[MockBugItem] = field(default_factory=list)


class HtmlScriptExtractor(HTMLParser):
    """HTML5-aware parser extracting ``<script>`` blocks and inline ``on*`` attributes."""

    def __init__(self) -> None:
        """Initialize empty script and inline event handler collections."""
        super().__init__(convert_charrefs=False)
        self.scripts: List[ExtractedScript] = []
        self.inline_handlers: List[ExtractedInlineHandler] = []
        self._in_script: bool = False
        self._current_script_kind: ScriptKind = ScriptKind.CLASSIC
        self._current_script_line: int = 1
        self._current_script_id: Optional[str] = None
        self._current_script_chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        """Capture ``<script>`` start metadata or inline ``on*`` event attributes."""
        tag_lower = tag.lower()
        line_no, _ = self.getpos()
        attr_map = {k.lower(): v for k, v in attrs}

        if tag_lower == "script":
            src_val = attr_map.get("src")
            script_id = attr_map.get("id")
            script_type = (attr_map.get("type") or "").strip().lower()
            if src_val:
                kind = ScriptKind.MODULE if script_type == "module" else ScriptKind.CLASSIC
                self.scripts.append(
                    ExtractedScript(
                        kind=kind,
                        code="",
                        start_line=line_no,
                        src_attr=src_val,
                        id_attr=script_id,
                    )
                )
                return

            if script_type == "application/json":
                kind = ScriptKind.JSON_DATA
            elif script_type == "importmap":
                kind = ScriptKind.IMPORTMAP
            elif script_type == "module":
                kind = ScriptKind.MODULE
            else:
                kind = ScriptKind.CLASSIC

            self._in_script = True
            self._current_script_kind = kind
            self._current_script_line = line_no
            self._current_script_id = script_id
            self._current_script_chunks = []
            return

        for attr_name, attr_value in attrs:
            name_lower = attr_name.lower()
            if (
                name_lower.startswith(INLINE_EVENT_ATTR_PREFIX)
                and len(name_lower) > len(INLINE_EVENT_ATTR_PREFIX)
                and attr_value is not None
            ):
                self.inline_handlers.append(
                    ExtractedInlineHandler(
                        tag_name=tag_lower,
                        attr_name=name_lower,
                        code=attr_value,
                        line=line_no,
                    )
                )

    def handle_data(self, data: str) -> None:
        """Accumulate raw text inside an active ``<script>`` tag."""
        if self._in_script:
            self._current_script_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Finalize an active ``<script>`` block when ``</script>`` is encountered."""
        if tag.lower() == "script" and self._in_script:
            self.scripts.append(
                ExtractedScript(
                    kind=self._current_script_kind,
                    code="".join(self._current_script_chunks),
                    start_line=self._current_script_line,
                    id_attr=self._current_script_id,
                )
            )
            self._in_script = False
            self._current_script_id = None
            self._current_script_chunks = []


def resolve_oxlint_binary() -> str:
    """Locate the ``oxlint`` executable in the active Python environment or PATH."""
    env_bin = Path(sys.executable).resolve().parent / "oxlint"
    if env_bin.is_file():
        return str(env_bin)
    found = shutil.which("oxlint")
    if found:
        return found
    raise FileNotFoundError("oxlint binary not found. Install it in the active environment via 'pip install oxlint'.")


def discover_first_party_js_files(repo_root: Path) -> List[Path]:
    """Return sorted ``.js`` and ``.mjs`` files under ``js/`` and ``tests/js/``, excluding unmodifiable vendor cores."""
    roots = (repo_root / "js", repo_root / "tests" / "js")
    found: List[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for ext in ("*.js", "*.mjs"):
            for candidate in root.rglob(ext):
                if candidate.name not in UNMODIFIABLE_VENDOR_FILENAMES:
                    found.append(candidate.resolve())
    return sorted(set(found))


def discover_html_templates(repo_root: Path) -> List[Path]:
    """Return sorted ``.html.j2`` Jinja2 templates under ``provider/templates``."""
    templates_dir = repo_root / "provider" / "templates"
    if not templates_dir.is_dir():
        return []
    return sorted(templates_dir.glob("*.html.j2"))


def build_template_variants(template_path: Path, repo_root: Path) -> List[TemplateVariant]:
    """Build representative Jinja2 rendering contexts covering template branches."""
    name = template_path.name

    if name == "diff_view.html.j2":
        empty_session = MockDiffSession(repo_root=str(repo_root))
        populated_session = MockDiffSession(
            repo_root=str(repo_root),
            repo_web_url="https://github.com/workspace/hardware",
            github_repo="workspace/hardware",
            current_branch="feature/js-lint",
            active_branch="feature/js-lint",
            active_commit=SAMPLE_COMMIT_HASH,
            selected_commits=[SAMPLE_COMMIT_HASH],
            branches=[MockBranch(name="feature/js-lint", is_current=True, upstream="origin/main", ahead=1)],
            smartlog_nodes=[
                MockCommitNode(
                    commit_hash=SAMPLE_COMMIT_HASH,
                    short_hash=SAMPLE_SHORT_HASH,
                    branches=("feature/js-lint",),
                    is_head=True,
                    bug_tags=(MockBugTag(id="BUG-100", title="Sample"),),
                )
            ],
            working_files=[MockWorkingFile(path="tools/validate_js.py")],
            conflicts=[MockConflictFile(path="README.md")],
            initial_sync_done=True,
            author_blacklist=["user"],
        )
        return [
            TemplateVariant(
                variant_name="empty",
                context={"session": empty_session, "active_branch": "main", "active_commit": "working"},
            ),
            TemplateVariant(
                variant_name="populated",
                context={
                    "session": populated_session,
                    "active_branch": "feature/js-lint",
                    "active_commit": SAMPLE_COMMIT_HASH,
                },
            ),
        ]

    if name == "code_review.html.j2":
        review_session = MockReviewSession(
            repo_root=str(repo_root),
            revisions=[SAMPLE_COMMIT_HASH],
            commits=[
                {
                    "commit_hash": SAMPLE_COMMIT_HASH,
                    "short_hash": SAMPLE_SHORT_HASH,
                    "author": "User",
                    "date": "2026-11-12",
                    "subject": "feat: validate js",
                    "additions": 8,
                    "deletions": 1,
                    "files_count": 1,
                }
            ],
            author_blacklist=["user"],
        )
        return [
            TemplateVariant(
                variant_name="multi_commit",
                context={"session": review_session, "single_commit": False},
            ),
            TemplateVariant(
                variant_name="single_commit",
                context={"session": review_session, "single_commit": True},
            ),
        ]

    if name == "bug_report.html.j2":
        sample_bug = MockBugItem()
        bug_db = MockBugDatabase(bugs=[sample_bug])
        db_json = json.dumps({"title": bug_db.title, "bugs": [asdict(sample_bug)]})
        return [
            TemplateVariant(
                variant_name="default",
                context={
                    "database": bug_db,
                    "database_json": db_json,
                    "statuses": ["OPEN", "IN_PROGRESS", "PLANNED", "RESOLVED", "CLOSED"],
                    "severities": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                    "categories": ["CAD", "PCB", "SIMULATION", "UI", "INFRASTRUCTURE"],
                    "components": ["scope"],
                    "server_port": DEFAULT_SERVER_PORT,
                },
                autoescape=True,
            )
        ]

    if name == "diff_component.html.j2":
        return [TemplateVariant(variant_name="partial", context={})]

    if name == "scope.html.j2":
        return [
            TemplateVariant(
                variant_name="default",
                context={
                    "init_project": "carrier_board",
                    "init_target": "carrier_board",
                    "init_subassembly": "",
                    "init_mode": "PCB",
                    "init_max_steps": DEFAULT_SCOPE_MAX_STEPS,
                    "port": DEFAULT_SERVER_PORT,
                },
                autoescape=True,
            )
        ]

    if name == "ibom.html.j2":
        return []

    return [TemplateVariant(variant_name="default", context={})]


def resolve_local_web_asset(url_path: str, repo_root: Path) -> Optional[Path]:
    """Resolve a ``/js/...`` or ``/static/...`` web URL to its expected local file path."""
    clean = url_path.split("?", 1)[0].split("#", 1)[0].strip()
    if clean.startswith("/js/"):
        return repo_root / "js" / clean[len("/js/") :]
    if clean.startswith("/static/"):
        return repo_root / "js" / "static" / clean[len("/static/") :]
    return None


def byte_offset_to_line_col(content: str, byte_offset: int) -> Tuple[int, int]:
    """Convert a UTF-8 byte offset from ``oxlint`` JSON output into 1-based ``(line, col)``."""
    encoded = content.encode("utf-8")
    clamped = max(0, min(byte_offset, len(encoded)))
    prefix = encoded[:clamped].decode("utf-8", errors="replace")
    line_no = prefix.count("\n") + 1
    last_nl = prefix.rfind("\n")
    col_no = (len(prefix) + 1) if last_nl == -1 else (len(prefix) - last_nl)
    return line_no, col_no


def _char_offset_to_line_col(content: str, char_offset: int) -> Tuple[int, int]:
    """Convert a character index in ``content`` into 1-based ``(line, col)``."""
    prefix = content[: max(0, char_offset)]
    line_no = prefix.count("\n") + 1
    last_nl = prefix.rfind("\n")
    col_no = (len(prefix) + 1) if last_nl == -1 else (len(prefix) - last_nl)
    return line_no, col_no


def _format_display_path(path: Path, repo_root: Path) -> str:
    """Format ``path`` relative to ``repo_root`` when nested inside the repository."""
    resolved = path.resolve()
    root_resolved = repo_root.resolve()
    if resolved.is_relative_to(root_resolved):
        return str(resolved.relative_to(root_resolved))
    return str(path)


def _strip_comments_and_strings_preserving_newlines(source: str) -> str:
    """Blank out JS comments and string/template literals while preserving exact line/column offsets."""

    def _mask(match: re.Match[str]) -> str:
        raw = match.group(0)
        return "".join("\n" if ch == "\n" else " " for ch in raw)

    return JS_TOKEN_OR_COMMENT_RE.sub(_mask, source)


def _check_zero_globals_boundary(js_file: Path, content: str, display_path: str) -> List[str]:
    """Enforce that only ``runtime_context.js`` accesses browser globals or disables ``no-undef``."""
    if js_file.name == RUNTIME_CONTEXT_FILENAME:
        return []

    findings: List[str] = []
    for match in NO_UNDEF_DISABLE_RE.finditer(content):
        line_no, col_no = _char_offset_to_line_col(content, match.start())
        findings.append(
            f"{display_path}:{line_no}:{col_no} [no-undef-suppression] "
            "Disabling 'no-undef' is restricted exclusively to js/core/runtime_context.js"
        )

    masked = _strip_comments_and_strings_preserving_newlines(content)
    for match in DIRECT_GLOBAL_ACCESS_RE.finditer(masked):
        global_name = match.group(1)
        line_no, col_no = _char_offset_to_line_col(masked, match.start())
        findings.append(
            f"{display_path}:{line_no}:{col_no} [no-direct-global] "
            f"Direct '{global_name}.' access is prohibited outside js/core/runtime_context.js; use RuntimeContext (ctx)"
        )

    for match in GLSL_IMPORT_RE.finditer(content):
        specifier = match.group(1)
        line_no, col_no = _char_offset_to_line_col(content, match.start(1))
        if specifier.startswith("."):
            shader_path = (js_file.parent / specifier).resolve()
            if not shader_path.is_file() or not shader_path.read_text(encoding="utf-8").strip():
                findings.append(
                    f"{display_path}:{line_no}:{col_no} [missing-shader-import] "
                    f"Shader import '{specifier}' does not resolve to a non-empty .glsl file ({shader_path})"
                )
    return findings


def _validate_template_variant(
    template_path: Path,
    variant: TemplateVariant,
    repo_root: Path,
) -> List[str]:
    """Render one Jinja2 template variant and verify zero inline JS/handlers and valid JSON/asset refs."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_path.parent)),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=jinja2.select_autoescape(["html", "xml"]) if variant.autoescape else False,
    )
    rendered_html = env.get_template(template_path.name).render(variant.context)

    extractor = HtmlScriptExtractor()
    extractor.feed(rendered_html)

    display_base = _format_display_path(template_path, repo_root)
    display_label = (
        display_base if variant.variant_name in ("default", "partial") else f"{display_base} [{variant.variant_name}]"
    )
    findings: List[str] = []

    for handler in extractor.inline_handlers:
        findings.append(
            f"{display_label}:{handler.line}:1 [no-inline-event-handler] "
            f"Inline HTML event attribute '<{handler.tag_name} {handler.attr_name}=\"...\">' is prohibited; "
            "bind via addEventListener / onDelegate in ES modules"
        )

    for script in extractor.scripts:
        if script.src_attr is not None:
            asset_path = resolve_local_web_asset(script.src_attr, repo_root)
            if asset_path is not None and not asset_path.is_file():
                findings.append(
                    f"{display_label}:{script.start_line}:1 [missing-script-src] "
                    f"Script src '{script.src_attr}' does not resolve to an existing file ({asset_path})"
                )
            continue

        if script.kind in (ScriptKind.CLASSIC, ScriptKind.MODULE):
            findings.append(
                f"{display_label}:{script.start_line}:1 [no-inline-script] "
                "Inline executable <script> blocks are prohibited in workstation templates; "
                'move code to js/ ES modules and pass state via <script type="application/json">'
            )
            continue

        if script.kind in (ScriptKind.JSON_DATA, ScriptKind.IMPORTMAP):
            try:
                parsed = json.loads(script.code)
            except json.JSONDecodeError as exc:
                err_line = script.start_line + max(0, exc.lineno - 1)
                findings.append(
                    f"{display_label}:{err_line}:{exc.colno} [invalid-json-script] "
                    f'Invalid JSON in <script type="{script.kind.value}">: {exc.msg}'
                )
                continue

            if script.kind == ScriptKind.IMPORTMAP:
                imports_map = parsed.get("imports") if isinstance(parsed, dict) else None
                if not isinstance(imports_map, dict):
                    findings.append(
                        f"{display_label}:{script.start_line}:1 [invalid-importmap] "
                        "<script type=\"importmap\"> must contain an 'imports' object"
                    )
                else:
                    for spec, target in imports_map.items():
                        if isinstance(target, str):
                            resolved_target = resolve_local_web_asset(target, repo_root)
                            target_exists = (
                                resolved_target.is_dir()
                                if resolved_target is not None and target.endswith("/")
                                else (resolved_target.is_file() if resolved_target is not None else True)
                            )
                            if resolved_target is not None and not target_exists:
                                findings.append(
                                    f"{display_label}:{script.start_line}:1 [missing-importmap-target] "
                                    f"Importmap specifier '{spec}' target '{target}' not found ({resolved_target})"
                                )

    return findings


def _run_oxlint_json(
    oxlint_bin: str,
    config_path: Path,
    target_files: Sequence[Path],
) -> Tuple[int, List[Dict[str, object]], str]:
    """Execute ``oxlint -f json --deny-warnings`` on ``target_files`` and parse diagnostics."""
    if not target_files:
        return 0, [], ""
    cmd = [
        oxlint_bin,
        "-c",
        str(config_path),
        "-f",
        "json",
        "--deny-warnings",
        *(str(p) for p in target_files),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stdout_text = proc.stdout.strip()
    stderr_text = proc.stderr.strip()
    if not stdout_text:
        return proc.returncode, [], stderr_text
    if not stdout_text.startswith("{"):
        combined = f"{stdout_text}\n{stderr_text}".strip()
        return proc.returncode, [], combined
    parsed = json.loads(stdout_text)
    diagnostics = parsed.get("diagnostics", []) if isinstance(parsed, dict) else []
    return proc.returncode, diagnostics, stderr_text


def validate_js(
    paths: Optional[Sequence[Path]] = None,
    repo_root: Path = REPO_ROOT,
    config_path: Optional[Path] = None,
    template_context: Optional[Dict[str, object]] = None,
) -> Tuple[int, List[str]]:
    """Compile and lint JavaScript ES modules and Jinja2 HTML templates, returning ``(exit_code, errors)``."""
    oxlint_bin = resolve_oxlint_binary()
    resolved_config = config_path or (repo_root / ".oxlintrc.json")

    if paths is not None:
        js_files = [
            p.resolve()
            for p in paths
            if p.suffix in (".js", ".mjs") and p.name not in UNMODIFIABLE_VENDOR_FILENAMES and p.is_file()
        ]
        template_files = [p.resolve() for p in paths if p.name.endswith(".html.j2") and p.is_file()]
    else:
        js_files = discover_first_party_js_files(repo_root)
        template_files = discover_html_templates(repo_root)

    errors: List[str] = []
    seen_errors: set[str] = set()
    file_contents: Dict[Path, Tuple[str, str]] = {}

    def _record(err: str) -> None:
        if err not in seen_errors:
            seen_errors.add(err)
            errors.append(err)

    for js_file in js_files:
        content = js_file.read_text(encoding="utf-8")
        display = _format_display_path(js_file, repo_root)
        file_contents[js_file] = (display, content)
        for violation in _check_zero_globals_boundary(js_file, content, display):
            _record(violation)

    for tpl_path in template_files:
        if template_context is not None:
            variants = [TemplateVariant(variant_name="default", context=template_context)]
        elif paths is not None and not tpl_path.is_relative_to(repo_root.resolve()):
            variants = [TemplateVariant(variant_name="default", context={})]
        else:
            variants = build_template_variants(tpl_path, repo_root)
        for variant in variants:
            for violation in _validate_template_variant(tpl_path, variant, repo_root):
                _record(violation)

    rc, diagnostics, stderr_msg = _run_oxlint_json(
        oxlint_bin=oxlint_bin,
        config_path=resolved_config,
        target_files=js_files,
    )
    if rc != 0 and not diagnostics and stderr_msg:
        _record(f"oxlint execution error: {stderr_msg}")

    for diag in diagnostics:
        raw_filename = str(diag.get("filename", ""))
        diag_path = Path(raw_filename).resolve() if raw_filename else None
        message = str(diag.get("message", "JavaScript error"))
        code = str(diag.get("code") or "syntax")
        labels = diag.get("labels")
        byte_offset = 0
        if isinstance(labels, list) and labels:
            first_label = labels[0]
            if isinstance(first_label, dict):
                span_obj = first_label.get("span")
                if isinstance(span_obj, dict):
                    byte_offset = int(span_obj.get("offset", 0))

        if diag_path is not None and diag_path in file_contents:
            display_path, content = file_contents[diag_path]
            line_no, col_no = byte_offset_to_line_col(content, byte_offset)
            _record(f"{display_path}:{line_no}:{col_no} [{code}] {message}")
        else:
            _record(f"{raw_filename} [{code}] {message}")

    return (1 if errors else 0), errors


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for ``validate_js.py``."""
    parser = argparse.ArgumentParser(
        description="Compile and lint zero-globals JavaScript ES modules and Jinja2 HTML templates via Oxlint."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional explicit .js / .mjs / .html.j2 files to validate (defaults to all repository sources).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run CLI entry point for JavaScript compilation and linting."""
    args = parse_args(argv)
    explicit_paths = [Path(p) for p in args.paths] if args.paths else None
    exit_code, errors = validate_js(paths=explicit_paths, repo_root=REPO_ROOT)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        print(f"JavaScript validation failed with {len(errors)} error(s).", file=sys.stderr)
        return exit_code

    print("JavaScript compilation and zero-globals lint checks passed (0 errors).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
