"""Regression unit test for WORM-016: Privacy and relative paths verification in hardware repo.

Guards against:
1. Leaking personal information (usernames, local user home directories) in git-tracked files.
2. Embedding absolute file URLs or hardcoded local paths in documentation and configs.
3. Leaking personal information in bug and code report feedback and tracebacks.
"""

from datetime import datetime, timezone
from pathlib import Path
import subprocess

from model.code_review import CommentModel, ReviewSessionModel, ReviewSeverity, ReviewStatus
from model.bug_report import BugCategory, BugDatabaseModel, BugReportModel, BugSeverity, BugStatus
from provider.code_review.markdown_exporter import MarkdownReviewExporter
from provider.sanitizer import elide_personal_info, get_usernames_to_redact
from provider.bug_report.markdown_exporter import MarkdownBugExporter


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def test_no_personal_username_in_tracked_files() -> None:
    """Verify git tracked files do not contain the personal username 'daparker'."""
    cmd = ["git", "grep", "-i", "-I", "daparker"]
    proc = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True)
    assert proc.returncode != 0, (
        f"Found occurrences of 'daparker' in git tracked files:\n{proc.stdout}"
    )


def test_elide_personal_info_tracebacks_and_paths() -> None:
    """Verify elide_personal_info redacts usernames and local home directories."""
    traceback_sample = """
Traceback (most recent call last):
  File "/Users/daparker/gh/hardware/src/daemon.py", line 403, in run
    return subprocess.run(cmd, check=True)
  File "/Users/daparker/miniforge3/envs/cq/lib/python3.13/site-packages/ocp_vscode/comms.py", line 161, in _send
    stdout, stderr = process.communicate(input, timeout=timeout)
FileNotFoundError: [Errno 2] No such file or directory: 'pytest-of-daparker/pytest-473'
"""
    cleaned = elide_personal_info(traceback_sample)
    assert "daparker" not in cleaned
    assert "/Users/<username>/gh/hardware/src/daemon.py" in cleaned
    assert "pytest-of-<username>/pytest-473" in cleaned


def test_documentation_uses_relative_paths() -> None:
    """Verify documentation files do not contain absolute file:///Users/ links."""
    gemini_file = WORKSPACE_ROOT / "GEMINI.md"
    assert gemini_file.exists(), "GEMINI.md must exist"
    gemini_text = gemini_file.read_text(encoding="utf-8")
    assert "file:///Users/" not in gemini_text
    assert "daparker" not in gemini_text


def test_bug_exporter_automatically_elides_personal_info(tmp_path: Path) -> None:
    """Verify MarkdownBugExporter automatically sanitizes personal info when rendering and exporting."""
    exporter = MarkdownBugExporter(repo_root=tmp_path)
    bug = BugReportModel(
        id="BUG-999",
        uuid="99999999-9999-9999-9999-999999999999",
        title="Test Bug with Personal Info",
        status=BugStatus.OPEN,
        severity=BugSeverity.MEDIUM,
        category=BugCategory.PCB,
        description="Encountered failure under /Users/daparker/gh/hardware/build/board.kicad_pcb",
        reproduction_steps=["Run pytest under /private/var/folders/pytest-of-daparker/test_1"],
        expected_behavior="Expected clean execution without leaking /Users/daparker paths",
        actual_behavior="Leaked /Users/daparker/miniforge3/env",
        logs='File "/Users/daparker/gh/hardware/src/view.py", line 10',
        resolution_notes="Fixed by daparker",
    )
    database = BugDatabaseModel(
        title="Privacy Test Database",
        summary="Summary mentioning /Users/daparker",
        bugs=[bug],
    )

    rendered_bug = exporter.render_bug_markdown(bug)
    assert "daparker" not in rendered_bug
    assert "<username>" in rendered_bug

    rendered_db = exporter.render_markdown(database)
    assert "daparker" not in rendered_db
    assert "<username>" in rendered_db

    exported_file = tmp_path / "BUGS.md"
    exporter.export_markdown(database, exported_file, feedback_dir=tmp_path / "feedback")
    content = exported_file.read_text(encoding="utf-8")
    assert "daparker" not in content
    assert "<username>" in content

    exported_bug_file = tmp_path / "feedback" / "BUG_999.md"
    assert exported_bug_file.exists()
    bug_content = exported_bug_file.read_text(encoding="utf-8")
    assert "daparker" not in bug_content
    assert "<username>" in bug_content


def test_code_review_exporter_automatically_elides_personal_info(tmp_path: Path) -> None:
    """Verify MarkdownReviewExporter automatically sanitizes personal info when exporting."""
    exporter = MarkdownReviewExporter(repo_root=tmp_path)
    session = ReviewSessionModel(
        title="Privacy Review",
        verdict=ReviewStatus.CHANGES_REQUESTED,
        summary="Review by daparker for /Users/daparker/gh/hardware",
        comments=[
            CommentModel(
                id="c99",
                uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                file_path="src/main.py",
                start_line=1,
                end_line=5,
                severity=ReviewSeverity.MUST_FIX,
                body="Please check /Users/daparker/gh/hardware/src/main.py",
                code_snippet="# Author: daparker\npath = '/Users/daparker'",
                created_at=datetime.now(timezone.utc).isoformat(),
                commit="12345678",
            )
        ],
    )

    rendered_cr = exporter.render_markdown(session)
    assert "daparker" not in rendered_cr
    assert "<username>" in rendered_cr

    out_file = tmp_path / "CR.md"
    exporter.export_markdown(session, out_file)
    content = out_file.read_text(encoding="utf-8")
    assert "daparker" not in content
    assert "<username>" in content

    commit_out = exporter.export_commit_markdown(session, "12345678", tmp_path / "feedback")
    assert commit_out is not None and commit_out.exists()
    commit_content = commit_out.read_text(encoding="utf-8")
    assert "daparker" not in commit_content
    assert "<username>" in commit_content
