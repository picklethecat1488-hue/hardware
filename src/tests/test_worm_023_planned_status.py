"""Regression unit test for WORM-023: Add Planned status to bugs (hardware port).

Verifies:
1. BugStatus.PLANNED enum exists and serializes properly.
2. Dashboard CLI list-bugs --open excludes PLANNED bugs by default.
3. Dashboard CLI supports --planned flag.
4. Bug console retains default status as OPEN.
5. Documentation instructs agents not to work on Planned bugs by default.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from src.model.bug_report import (
    BugCategory,
    BugDatabaseModel,
    BugReportModel,
    BugSeverity,
    BugStatus,
)
from src.dashboard import parse_arguments, print_cli_bugs


def test_bug_status_planned_enum_exists() -> None:
    """Verify BugStatus has PLANNED variant."""
    assert hasattr(BugStatus, "PLANNED"), "BugStatus must define PLANNED"
    assert BugStatus.PLANNED.value == "PLANNED"


def test_cli_list_bugs_open_excludes_planned() -> None:
    """Verify list-bugs --open excludes PLANNED bugs by default so agent won't work on them."""
    db = BugDatabaseModel(
        bugs=[
            BugReportModel(
                id="BUG-101",
                title="Active open bug",
                severity=BugSeverity.HIGH,
                status=BugStatus.OPEN,
                category=BugCategory.PCB,
            ),
            BugReportModel(
                id="BUG-102",
                title="Future planned feature",
                severity=BugSeverity.LOW,
                status=BugStatus.PLANNED,
                category=BugCategory.PCB,
            ),
            BugReportModel(
                id="BUG-103",
                title="Resolved defect",
                severity=BugSeverity.MEDIUM,
                status=BugStatus.RESOLVED,
                category=BugCategory.PCB,
            ),
        ]
    )

    out = StringIO()
    with patch("sys.stdout", out):
        print_cli_bugs(db, open_only=True)
    output = out.getvalue()

    assert "BUG-101" in output, "Open bug should be listed"
    assert "BUG-102" not in output, "Planned bug must be excluded when open_only=True"
    assert "BUG-103" not in output, "Resolved bug must be excluded when open_only=True"


def test_cli_planned_argument() -> None:
    """Verify --planned CLI argument filters to PLANNED bugs."""
    with patch("sys.argv", ["dashboard.py", "--planned"]):
        args = parse_arguments()
        assert getattr(args, "planned", False) is True

    db = BugDatabaseModel(
        bugs=[
            BugReportModel(
                id="BUG-101",
                title="Active open bug",
                severity=BugSeverity.HIGH,
                status=BugStatus.OPEN,
                category=BugCategory.PCB,
            ),
            BugReportModel(
                id="BUG-102",
                title="Future planned feature",
                severity=BugSeverity.LOW,
                status=BugStatus.PLANNED,
                category=BugCategory.PCB,
            ),
        ]
    )

    out = StringIO()
    with patch("sys.stdout", out):
        print_cli_bugs(db, planned_only=True)
    output = out.getvalue()

    assert "BUG-102" in output, "Planned bug must be listed when planned_only=True"
    assert "BUG-101" not in output, "Open bug must be excluded when planned_only=True"


def test_template_planned_filter_and_default_open() -> None:
    """Verify bug report template includes PLANNED filter and retains OPEN as default."""
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "bug_report.html.j2"
    assert template_path.exists(), f"Template not found at {template_path}"
    content = template_path.read_text(encoding="utf-8")

    assert 'id="filter-planned"' in content, "Template must have filter-planned button"
    assert "PLANNED" in content, "Template must reference PLANNED"
    assert 'status: "OPEN"' in content, "Template new bug must default to OPEN status"


def test_documentation_planned_bug_exemption() -> None:
    """Verify GEMINI.md states agents must not work on Planned bugs by default."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    gemini_path = repo_root / "GEMINI.md"
    assert gemini_path.exists(), "GEMINI.md must exist"
    gemini_content = gemini_path.read_text(encoding="utf-8")
    assert "PLANNED" in gemini_content, "GEMINI.md must reference PLANNED bugs"
    assert "Planned Bug Exemption" in gemini_content or "planned" in gemini_content.lower()
