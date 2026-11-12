#!/usr/bin/env python3
"""Compile and statically lint first-party JavaScript and Jinja2 HTML templates via Oxlint.

Extracts classic ``<script>`` blocks, ES module ``<script type="module">`` blocks, and
inline HTML ``on*="..."`` event attributes from rendered Jinja2 ``.html.j2`` template
variants as well as standalone first-party ``.js`` assets, then runs ``oxlint`` to enforce
zero syntax errors, zero undefined identifiers, and zero static correctness violations.
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
import tempfile
from typing import Dict, List, Optional, Sequence, Tuple

import jinja2

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_JS_FILENAMES = frozenset({"highlight.min.js", "three-cad-viewer.esm.js"})
INLINE_EVENT_ATTR_PREFIX = "on"
WINDOW_EXPORT_PATTERN = re.compile(r"\bwindow\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=")
SAMPLE_COMMIT_HASH = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
SAMPLE_SHORT_HASH = "a1b2c3d4"
DEFAULT_SERVER_PORT = 8877
DEFAULT_SCOPE_MAX_STEPS = 1000


class ScriptKind(str, Enum):
    """Classification of an extracted HTML script tag."""

    CLASSIC = "classic"
    MODULE = "module"


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


@dataclass(frozen=True)
class ExtractedInlineHandler:
    """Single HTML inline ``on*="..."`` event handler attribute."""

    tag_name: str
    attr_name: str
    code: str
    line: int


@dataclass(frozen=True)
class SourceSpanMapping:
    """Maps a contiguous line range in a generated lint unit back to its origin file."""

    generated_start_line: int
    generated_end_line: int
    display_path: str
    origin_start_line: int
    fixed_origin_line: bool = False


@dataclass(frozen=True)
class TemplateVariant:
    """Named rendering context variant for a Jinja2 HTML template."""

    variant_name: str
    context: Dict[str, object]
    autoescape: bool = False
    ambient_static_scripts: Tuple[Path, ...] = ()


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
        super().__init__(convert_charrefs=True)
        self.scripts: List[ExtractedScript] = []
        self.inline_handlers: List[ExtractedInlineHandler] = []
        self._in_script: bool = False
        self._current_script_kind: ScriptKind = ScriptKind.CLASSIC
        self._current_script_line: int = 1
        self._current_script_chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        """Capture ``<script>`` start metadata or inline ``on*`` event attributes."""
        tag_lower = tag.lower()
        line_no, _ = self.getpos()
        attr_map = {k.lower(): v for k, v in attrs}

        if tag_lower == "script":
            src_val = attr_map.get("src")
            script_type = (attr_map.get("type") or "").strip().lower()
            if src_val:
                kind = ScriptKind.MODULE if script_type == "module" else ScriptKind.CLASSIC
                self.scripts.append(ExtractedScript(kind=kind, code="", start_line=line_no, src_attr=src_val))
                return
            if script_type in ("", "text/javascript", "application/javascript"):
                self._in_script = True
                self._current_script_kind = ScriptKind.CLASSIC
                self._current_script_line = line_no
                self._current_script_chunks = []
            elif script_type == "module":
                self._in_script = True
                self._current_script_kind = ScriptKind.MODULE
                self._current_script_line = line_no
                self._current_script_chunks = []
            return

        for attr_name, attr_value in attrs:
            name_lower = attr_name.lower()
            if (
                name_lower.startswith(INLINE_EVENT_ATTR_PREFIX)
                and len(name_lower) > len(INLINE_EVENT_ATTR_PREFIX)
                and attr_value is not None
                and attr_value.strip()
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
        """Accumulate raw JavaScript source text inside an active ``<script>`` tag."""
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
                )
            )
            self._in_script = False
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
    """Return sorted first-party standalone ``.js`` files, excluding vendor bundles."""
    provider_dir = repo_root / "provider"
    if not provider_dir.is_dir():
        return []
    return sorted(p for p in provider_dir.rglob("*.js") if p.name not in EXCLUDED_JS_FILENAMES)


def discover_html_templates(repo_root: Path) -> List[Path]:
    """Return sorted ``.html.j2`` Jinja2 templates under ``provider/templates``."""
    templates_dir = repo_root / "provider" / "templates"
    if not templates_dir.is_dir():
        return []
    return sorted(templates_dir.glob("*.html.j2"))


def build_template_variants(template_path: Path, repo_root: Path) -> List[TemplateVariant]:
    """Build representative Jinja2 rendering contexts covering template branches."""
    name = template_path.name
    common_js_path = repo_root / "provider" / "code_review" / "static" / "common.js"

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
        ambient = (common_js_path,) if common_js_path.is_file() else ()
        return [TemplateVariant(variant_name="partial", context={}, ambient_static_scripts=ambient)]

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


def resolve_static_script_attr(src_attr: str, repo_root: Path) -> Optional[Path]:
    """Map a template ``/static/...`` script ``src`` attribute to a first-party local file."""
    clean_src = src_attr.split("?", 1)[0].strip()
    if not clean_src.startswith("/static/"):
        return None
    rel_name = clean_src[len("/static/") :]
    if Path(rel_name).name in EXCLUDED_JS_FILENAMES:
        return None
    candidate = repo_root / "provider" / "code_review" / "static" / rel_name
    if candidate.is_file():
        return candidate
    return None


def map_generated_line(
    line_no: int,
    spans: Sequence[SourceSpanMapping],
    fallback_path: str,
) -> Tuple[str, int]:
    """Translate a 1-based line in a generated JS unit back to its source file and line."""
    for span in spans:
        if span.generated_start_line <= line_no <= span.generated_end_line:
            if span.fixed_origin_line:
                return span.display_path, span.origin_start_line
            offset = line_no - span.generated_start_line
            return span.display_path, span.origin_start_line + offset
    return fallback_path, line_no


def byte_offset_to_line_col(content: str, byte_offset: int) -> Tuple[int, int]:
    """Convert a UTF-8 byte offset from ``oxlint`` JSON output into 1-based ``(line, col)``."""
    encoded = content.encode("utf-8")
    clamped = max(0, min(byte_offset, len(encoded)))
    prefix = encoded[:clamped].decode("utf-8", errors="replace")
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


def _prepare_template_units(
    template_path: Path,
    variant: TemplateVariant,
    repo_root: Path,
    temp_dir: Path,
    unit_counter: List[int],
    unit_spans: Dict[Path, Tuple[str, str, List[SourceSpanMapping]]],
) -> None:
    """Render one Jinja2 template variant and emit temporary JS/MJS units with line maps."""
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

    referenced_static_files: List[Path] = list(variant.ambient_static_scripts)
    classic_blocks: List[ExtractedScript] = []
    module_blocks: List[ExtractedScript] = []
    module_window_exports: List[str] = []

    for script in extractor.scripts:
        if script.src_attr:
            resolved = resolve_static_script_attr(script.src_attr, repo_root)
            if resolved is not None and resolved not in referenced_static_files:
                referenced_static_files.append(resolved)
            continue
        if script.kind == ScriptKind.MODULE:
            module_blocks.append(script)
            for ident in WINDOW_EXPORT_PATTERN.findall(script.code):
                if ident not in module_window_exports:
                    module_window_exports.append(ident)
        else:
            classic_blocks.append(script)

    for m_idx, mod in enumerate(module_blocks):
        unit_counter[0] += 1
        unit_path = temp_dir / f"unit_{unit_counter[0]:04d}_{template_path.stem}_mod_{m_idx}.mjs"
        line_count = mod.code.count("\n") + 1
        spans = [
            SourceSpanMapping(
                generated_start_line=1,
                generated_end_line=line_count,
                display_path=display_label,
                origin_start_line=mod.start_line,
            )
        ]
        unit_path.write_text(mod.code, encoding="utf-8")
        unit_spans[unit_path] = (display_label, mod.code, spans)

    if len(classic_blocks) > 1:
        for c_idx, blk in enumerate(classic_blocks):
            unit_counter[0] += 1
            syn_path = temp_dir / f"syntax_{unit_counter[0]:04d}_{template_path.stem}_blk_{c_idx}.js"
            line_count = blk.code.count("\n") + 1
            spans = [
                SourceSpanMapping(
                    generated_start_line=1,
                    generated_end_line=line_count,
                    display_path=display_label,
                    origin_start_line=blk.start_line,
                )
            ]
            syn_path.write_text(blk.code, encoding="utf-8")
            unit_spans[syn_path] = (display_label, blk.code, spans)

    if not classic_blocks and not extractor.inline_handlers:
        return

    combined_chunks: List[str] = []
    combined_spans: List[SourceSpanMapping] = []
    current_line = 1

    for static_js in referenced_static_files:
        static_code = static_js.read_text(encoding="utf-8")
        if not static_code.endswith("\n"):
            static_code += "\n"
        static_lines = static_code.count("\n")
        combined_spans.append(
            SourceSpanMapping(
                generated_start_line=current_line,
                generated_end_line=current_line + static_lines - 1,
                display_path=_format_display_path(static_js, repo_root),
                origin_start_line=1,
            )
        )
        combined_chunks.append(static_code)
        current_line += static_lines

    if module_window_exports:
        stubs = "".join(f"var {ident} = window.{ident};\n" for ident in module_window_exports)
        stub_lines = stubs.count("\n")
        combined_spans.append(
            SourceSpanMapping(
                generated_start_line=current_line,
                generated_end_line=current_line + stub_lines - 1,
                display_path=display_label,
                origin_start_line=1,
                fixed_origin_line=True,
            )
        )
        combined_chunks.append(stubs)
        current_line += stub_lines

    for blk in classic_blocks:
        blk_code = blk.code if blk.code.endswith("\n") else f"{blk.code}\n"
        blk_lines = blk_code.count("\n")
        combined_spans.append(
            SourceSpanMapping(
                generated_start_line=current_line,
                generated_end_line=current_line + blk_lines - 1,
                display_path=display_label,
                origin_start_line=blk.start_line,
            )
        )
        combined_chunks.append(blk_code)
        current_line += blk_lines

    if extractor.inline_handlers:
        header = "function __validate_html_inline_handlers__(event) {\n"
        combined_chunks.append(header)
        current_line += 1
        for h_idx, handler in enumerate(extractor.inline_handlers):
            single_line_body = handler.code.replace("\r\n", " ").replace("\n", " ")
            wrapped_line = (
                f"  (function() {{ {single_line_body}\n"
                f"  }}).call(document.createElement({json.dumps(handler.tag_name)}), event); // inline_{h_idx}\n"
            )
            wrapped_count = wrapped_line.count("\n")
            combined_spans.append(
                SourceSpanMapping(
                    generated_start_line=current_line,
                    generated_end_line=current_line + wrapped_count - 1,
                    display_path=display_label,
                    origin_start_line=handler.line,
                    fixed_origin_line=True,
                )
            )
            combined_chunks.append(wrapped_line)
            current_line += wrapped_count
        footer = "}\nwindow.__validate_html_inline_handlers__ = __validate_html_inline_handlers__;\n"
        combined_chunks.append(footer)
        current_line += footer.count("\n")

    unit_counter[0] += 1
    combined_code = "".join(combined_chunks)
    page_unit_path = temp_dir / f"unit_{unit_counter[0]:04d}_{template_path.stem}_{variant.variant_name}_page.js"
    page_unit_path.write_text(combined_code, encoding="utf-8")
    unit_spans[page_unit_path] = (display_label, combined_code, combined_spans)


def _run_oxlint_json(
    oxlint_bin: str,
    config_path: Path,
    target_files: Sequence[Path],
    extra_args: Sequence[str] = (),
) -> Tuple[int, List[Dict[str, object]], str]:
    """Execute ``oxlint -f json`` on ``target_files`` and parse structured diagnostics."""
    if not target_files:
        return 0, [], ""
    cmd = [
        oxlint_bin,
        "-c",
        str(config_path),
        "-f",
        "json",
        "--deny-warnings",
        *extra_args,
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
    """Compile and lint JavaScript sources and Jinja2 HTML templates, returning ``(exit_code, errors)``."""
    oxlint_bin = resolve_oxlint_binary()
    resolved_config = config_path or (repo_root / ".oxlintrc.json")

    if paths is not None:
        js_files = [
            p.resolve()
            for p in paths
            if p.suffix in (".js", ".mjs") and p.name not in EXCLUDED_JS_FILENAMES and p.is_file()
        ]
        template_files = [p.resolve() for p in paths if p.name.endswith(".html.j2") and p.is_file()]
    else:
        js_files = discover_first_party_js_files(repo_root)
        template_files = discover_html_templates(repo_root)

    errors: List[str] = []
    seen_errors: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="validate_js_") as tmp_dir_str:
        temp_dir = Path(tmp_dir_str).resolve()
        unit_counter = [0]
        unit_spans: Dict[Path, Tuple[str, str, List[SourceSpanMapping]]] = {}

        for js_file in js_files:
            content = js_file.read_text(encoding="utf-8")
            display = _format_display_path(js_file, repo_root)
            line_count = content.count("\n") + 1
            unit_spans[js_file.resolve()] = (
                display,
                content,
                [
                    SourceSpanMapping(
                        generated_start_line=1,
                        generated_end_line=line_count,
                        display_path=display,
                        origin_start_line=1,
                    )
                ],
            )

        for tpl_path in template_files:
            if template_context is not None:
                variants = [TemplateVariant(variant_name="default", context=template_context)]
            elif paths is not None and not tpl_path.is_relative_to(repo_root.resolve()):
                variants = [TemplateVariant(variant_name="default", context={})]
            else:
                variants = build_template_variants(tpl_path, repo_root)
            for variant in variants:
                _prepare_template_units(
                    template_path=tpl_path,
                    variant=variant,
                    repo_root=repo_root,
                    temp_dir=temp_dir,
                    unit_counter=unit_counter,
                    unit_spans=unit_spans,
                )

        full_lint_targets = [
            *js_files,
            *sorted(p for p in temp_dir.iterdir() if p.name.startswith("unit_")),
        ]
        syntax_only_targets = sorted(p for p in temp_dir.iterdir() if p.name.startswith("syntax_"))

        batches: List[Tuple[List[Path], Tuple[str, ...]]] = [
            (full_lint_targets, ()),
            (syntax_only_targets, ("-A", "no-undef")),
        ]

        for batch_files, extra_flags in batches:
            rc, diagnostics, stderr_msg = _run_oxlint_json(
                oxlint_bin=oxlint_bin,
                config_path=resolved_config,
                target_files=batch_files,
                extra_args=extra_flags,
            )
            if rc != 0 and not diagnostics and stderr_msg:
                errors.append(f"oxlint execution error: {stderr_msg}")
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

                if diag_path is not None and diag_path in unit_spans:
                    fallback_disp, unit_content, spans = unit_spans[diag_path]
                    gen_line, gen_col = byte_offset_to_line_col(unit_content, byte_offset)
                    src_disp, src_line = map_generated_line(gen_line, spans, fallback_disp)
                    formatted = f"{src_disp}:{src_line}:{gen_col} [{code}] {message}"
                else:
                    formatted = f"{raw_filename} [{code}] {message}"

                if formatted not in seen_errors:
                    seen_errors.add(formatted)
                    errors.append(formatted)

    return (1 if errors else 0), errors


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for ``validate_js.py``."""
    parser = argparse.ArgumentParser(
        description="Compile and lint first-party JavaScript and Jinja2 HTML templates via Oxlint."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional explicit .js / .html.j2 files to validate (defaults to all first-party sources).",
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

    print("JavaScript compilation and lint checks passed (0 errors).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
