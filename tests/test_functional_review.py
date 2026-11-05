"""Unit tests for the functional review process, detached bug branch, and CLI/API extensions."""

import json
from pathlib import Path
import sqlite3
import subprocess
import threading
import urllib.request
import pytest

from model.bug_report import (
    BugCategory,
    BugDatabaseModel,
    BugReportModel,
    BugSeverity,
    BugStatus,
    ReviewTaskModel,
    ReviewTaskStatus,
)
from provider.bug_report.detached_branch import DetachedBranchBugStore
from provider.bug_report.markdown_exporter import MarkdownBugExporter
from provider.bug_report.server import BugReportServer
from provider.bug_report.sqlite_store import SQLiteBugStore
from tools.dashboard import main as dashboard_main


def create_test_git_repo(path: Path) -> Path:
    """Create a minimal isolated git repository for detached branch testing."""
    repo_dir = path / "git_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Engineer"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_dir, check=True, capture_output=True)
    (repo_dir / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo_dir, check=True, capture_output=True)
    return repo_dir


def test_review_task_model() -> None:
    """Verify ReviewTaskModel initialization, defaults, and serialization."""
    task = ReviewTaskModel(
        id="task-123",
        title="Verify motor RPM under load",
        command="python tools/view.py",
        status=ReviewTaskStatus.PENDING,
        notes="Inspect graph",
    )
    assert task.id == "task-123"
    assert task.title == "Verify motor RPM under load"
    assert task.command == "python tools/view.py"
    assert task.status == ReviewTaskStatus.PENDING
    assert task.notes == "Inspect graph"

    dumped = task.model_dump(mode="json")
    assert dumped["status"] == "PENDING"
    assert dumped["command"] == "python tools/view.py"

    loaded = ReviewTaskModel.model_validate(dumped)
    assert loaded.id == task.id
    assert loaded.status == ReviewTaskStatus.PENDING


def test_bug_report_model_functional_review_fields() -> None:
    """Verify BugReportModel supports commit_ids, review_tasks, rejection_notes, and timestamps."""
    bug = BugReportModel(
        id="BUG-TEST-TASK-001",
        title="Check functional review lifecycle",
        status=BugStatus.RESOLVED,
        severity=BugSeverity.MEDIUM,
        category=BugCategory.PCB,
        commit_ids=["c0ffee1", "c0ffee2"],
        review_tasks=[
            ReviewTaskModel(
                id="task-1",
                title="Run DRC checks",
                command="pytest tests/test_pcb_drc.py",
                status=ReviewTaskStatus.COMPLETED,
            )
        ],
        rejection_notes="Previous fix failed thermal checks",
        accepted_at=None,
        rejected_at="2026-11-04 10:00:00 UTC",
    )

    assert bug.commit_ids == ["c0ffee1", "c0ffee2"]
    assert len(bug.review_tasks) == 1
    assert bug.review_tasks[0].status == ReviewTaskStatus.COMPLETED
    assert bug.rejection_notes == "Previous fix failed thermal checks"
    assert bug.rejected_at == "2026-11-04 10:00:00 UTC"

    dumped = bug.model_dump(mode="json")
    assert dumped["commit_ids"] == ["c0ffee1", "c0ffee2"]
    assert dumped["review_tasks"][0]["id"] == "task-1"
    assert dumped["rejection_notes"] == "Previous fix failed thermal checks"

    restored = BugReportModel.model_validate(dumped)
    assert restored.commit_ids == bug.commit_ids
    assert len(restored.review_tasks) == 1
    assert restored.review_tasks[0].title == "Run DRC checks"


def test_sqlite_store_functional_review_roundtrip_and_migration(tmp_path: Path) -> None:
    """Verify SQLiteBugStore saves and restores functional review fields and handles schema migrations."""
    db_file = tmp_path / "test_bugs.sqlite"
    store = SQLiteBugStore(db_path=db_file)

    bug = BugReportModel(
        id="BUG-SQLITE-001",
        title="SQLite Functional Review Test",
        status=BugStatus.RESOLVED,
        severity=BugSeverity.HIGH,
        category=BugCategory.GENERAL,
        commit_ids=["7a8b9c0"],
        review_tasks=[
            ReviewTaskModel(
                id="task-sql-1",
                title="Check query plan",
                command="EXPLAIN QUERY PLAN",
                status=ReviewTaskStatus.PENDING,
            )
        ],
        rejection_notes=None,
        accepted_at=None,
        rejected_at=None,
    )
    store.save_bug(bug)

    loaded = store.get_bug("BUG-SQLITE-001")
    assert loaded is not None
    assert loaded.commit_ids == ["7a8b9c0"]
    assert len(loaded.review_tasks) == 1
    assert loaded.review_tasks[0].id == "task-sql-1"
    assert loaded.review_tasks[0].title == "Check query plan"
    assert loaded.rejection_notes is None

    # Test migration on legacy database schema
    legacy_db_file = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(legacy_db_file)
    conn.execute("""
        CREATE TABLE bugs (
            id TEXT PRIMARY KEY,
            uuid TEXT,
            title TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            category TEXT NOT NULL,
            component TEXT,
            description TEXT,
            reproduction_steps TEXT,
            expected_behavior TEXT,
            actual_behavior TEXT,
            logs TEXT,
            resolution_notes TEXT,
            resolution TEXT,
            created_at TEXT,
            updated_at TEXT,
            resolved_at TEXT,
            closed_at TEXT
        )
    """)
    conn.execute("""
        INSERT INTO bugs (id, title, severity, status, category)
        VALUES ('BUG-LEGACY-001', 'Legacy Bug', 'LOW', 'OPEN', 'GENERAL')
    """)
    conn.commit()
    conn.close()

    # Reopening with SQLiteBugStore should run migration without error
    legacy_store = SQLiteBugStore(db_path=legacy_db_file)
    legacy_bug = legacy_store.get_bug("BUG-LEGACY-001")
    assert legacy_bug is not None
    assert legacy_bug.commit_ids == []
    assert legacy_bug.review_tasks == []
    assert legacy_bug.rejection_notes is None


def test_markdown_exporter_functional_review_sections(tmp_path: Path) -> None:
    """Verify MarkdownBugExporter correctly writes and parses attached commits, tasks, and rejection notes."""
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    exporter = MarkdownBugExporter(repo_root=tmp_path)

    bug = BugReportModel(
        id="BUG-MD-001",
        title="Markdown Review Test",
        status=BugStatus.RESOLVED,
        severity=BugSeverity.CRITICAL,
        category=BugCategory.PCB,
        description="Verify review sections.",
        commit_ids=["1111111", "2222222"],
        review_tasks=[
            ReviewTaskModel(
                id="task-md-1",
                title="Execute smoke test",
                command="python tools/smoke.py",
                status=ReviewTaskStatus.COMPLETED,
            ),
            ReviewTaskModel(
                id="task-md-2",
                title="Inspect preview",
                command="",
                status=ReviewTaskStatus.PENDING,
            ),
        ],
        rejection_notes="Needs cleaner wire routing",
        rejected_at="2026-11-04 10:15:00 UTC",
    )

    exported_path = exporter.export_individual_bug(bug, feedback_dir)
    content = exported_path.read_text(encoding="utf-8")
    assert "#### Attached Commits" in content
    assert "`1111111`" in content
    assert "`2222222`" in content
    assert "#### Review Tasks & Functional Checklist" in content
    assert "Execute smoke test | `python tools/smoke.py`" in content
    assert "<!-- task:task-md-1 -->" in content
    assert "Inspect preview" in content
    assert "<!-- task:task-md-2 -->" in content
    assert "#### Rejection Feedback" in content
    assert "Needs cleaner wire routing" in content

    # Parse exported markdown back
    parsed = exporter.parse_individual_bug_file(exported_path)
    assert parsed is not None
    assert parsed.id == "BUG-MD-001"
    assert parsed.commit_ids == ["1111111", "2222222"]
    assert len(parsed.review_tasks) == 2
    assert parsed.review_tasks[0].title == "Execute smoke test"
    assert parsed.review_tasks[0].status == ReviewTaskStatus.COMPLETED
    assert parsed.review_tasks[0].command == "python tools/smoke.py"
    assert parsed.review_tasks[1].title == "Inspect preview"
    assert parsed.review_tasks[1].status == ReviewTaskStatus.PENDING
    assert parsed.rejection_notes == "Needs cleaner wire routing"


def test_detached_branch_bug_store(tmp_path: Path) -> None:
    """Verify DetachedBranchBugStore commits and loads from detached git branch without dirtying working tree."""
    repo_dir = create_test_git_repo(tmp_path)
    store = DetachedBranchBugStore(repo_root=repo_dir, branch_name="bugs")

    # Initially empty
    data = store.load_database()
    assert data is None

    # Commit data to detached branch
    db = BugDatabaseModel(
        title="Detached Tracker",
        bugs=[
            BugReportModel(
                id="BUG-DETACHED-001",
                title="Detached Test Bug",
                status=BugStatus.OPEN,
                severity=BugSeverity.MEDIUM,
                category=BugCategory.PCB,
                commit_ids=["feed123"],
            )
        ],
    )

    commit_sha = store.commit_database(
        database=db,
        commit_message="Initial bug database sync",
    )
    assert commit_sha is not None
    assert len(commit_sha) == 40

    # Ensure working tree was NOT modified or checked out
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo_dir, check=True, capture_output=True, text=True)
    assert status.stdout.strip() == ""
    curr_branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert curr_branch == "main"

    # Load from detached branch
    loaded = store.load_database()
    assert loaded is not None
    assert len(loaded.bugs) == 1
    assert loaded.bugs[0].id == "BUG-DETACHED-001"
    assert loaded.bugs[0].commit_ids == ["feed123"]


def test_bug_server_functional_review_api_endpoints(tmp_path: Path) -> None:
    """Verify BugReportServer REST endpoints: accept, reject, attach_commit, add_task, update_task, run_command."""
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "bugs.sqlite"

    store = SQLiteBugStore(db_path=db_file)
    test_bug = BugReportModel(
        id="BUG-SERVER-001",
        title="Server API Bug",
        status=BugStatus.RESOLVED,
        severity=BugSeverity.MEDIUM,
        category=BugCategory.PCB,
    )
    store.save_bug(test_bug)

    server = BugReportServer(
        host="127.0.0.1",
        port=0,
        repo_root=tmp_path,
        feedback_dir=feedback_dir,
        sqlite_file=db_file,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = server.get_url()

    try:
        # 1. Attach commit
        req = urllib.request.Request(
            f"{base_url}/api/bugs/attach_commit",
            data=json.dumps({"id": "BUG-SERVER-001", "commit_id": "abc1234"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert "abc1234" in data["bug"]["commit_ids"]

        # 2. Add review task
        req = urllib.request.Request(
            f"{base_url}/api/bugs/add_task",
            data=json.dumps(
                {
                    "id": "BUG-SERVER-001",
                    "title": "Run echo test",
                    "command": "echo 'Hello from review task'",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            tasks = data["bug"]["review_tasks"]
            assert len(tasks) == 1
            task_id = tasks[0]["id"]
            assert tasks[0]["title"] == "Run echo test"

        # 3. Update task status
        req = urllib.request.Request(
            f"{base_url}/api/bugs/update_task",
            data=json.dumps(
                {
                    "id": "BUG-SERVER-001",
                    "task_id": task_id,
                    "status": "COMPLETED",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["bug"]["review_tasks"][0]["status"] == "COMPLETED"

        # 4. Run task command
        req = urllib.request.Request(
            f"{base_url}/api/bugs/run_command",
            data=json.dumps(
                {
                    "id": "BUG-SERVER-001",
                    "command": "echo 'Command demo execution output'",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert "Command demo execution output" in data["stdout"]
            assert data["exit_code"] == 0

        # 5. Reject bug -> transitions RESOLVED to OPEN
        req = urllib.request.Request(
            f"{base_url}/api/bugs/reject",
            data=json.dumps(
                {
                    "id": "BUG-SERVER-001",
                    "notes": "Echo test output was insufficient.",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["bug"]["status"] == "OPEN"
            assert data["bug"]["rejection_notes"] == "Echo test output was insufficient."
            assert data["bug"]["rejected_at"] is not None

        # Re-resolve bug to test accept
        bug_obj = store.get_bug("BUG-SERVER-001")
        bug_obj.status = BugStatus.RESOLVED
        store.save_bug(bug_obj)

        # 6. Accept bug -> transitions RESOLVED to CLOSED
        req = urllib.request.Request(
            f"{base_url}/api/bugs/accept",
            data=json.dumps(
                {
                    "id": "BUG-SERVER-001",
                    "notes": "Verified and accepted.",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["bug"]["status"] == "CLOSED"
            assert data["bug"]["accepted_at"] is not None

    finally:
        server.server_close()


def test_cli_functional_review_subcommands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify CLI commands: attach-commit, add-task, resolve-task, accept-bug, reject-bug, and list-bugs --open."""
    repo_dir = create_test_git_repo(tmp_path)
    monkeypatch.chdir(repo_dir)
    db_file = repo_dir / "bugs.sqlite"
    store = SQLiteBugStore(db_path=db_file)

    bug = BugReportModel(
        id="BUG-CLI-001",
        title="CLI Review Bug",
        status=BugStatus.RESOLVED,
        severity=BugSeverity.HIGH,
        category=BugCategory.PCB,
    )
    store.save_bug(bug)

    # 1. attach-commit
    dashboard_main(["--db-file", str(db_file), "attach-commit", "--id", "BUG-CLI-001", "--commit", "f00ba42"])
    updated = store.get_bug("BUG-CLI-001")
    assert "f00ba42" in updated.commit_ids

    # 2. add-task
    dashboard_main(
        [
            "--db-file",
            str(db_file),
            "add-task",
            "--id",
            "BUG-CLI-001",
            "--title",
            "CLI Verification Step",
            "--command",
            "ls -la",
        ]
    )
    updated = store.get_bug("BUG-CLI-001")
    assert len(updated.review_tasks) == 1
    task_id = updated.review_tasks[0].id
    assert updated.review_tasks[0].title == "CLI Verification Step"

    # 3. resolve-task
    dashboard_main(
        [
            "--db-file",
            str(db_file),
            "resolve-task",
            "--id",
            "BUG-CLI-001",
            "--task-id",
            task_id,
            "--status",
            "COMPLETED",
        ]
    )
    updated = store.get_bug("BUG-CLI-001")
    assert updated.review_tasks[0].status == ReviewTaskStatus.COMPLETED

    # 4. list-bugs --open keeps RESOLVED visible as [RESOLVED (AWAITING REVIEW)]
    capsys.readouterr()
    dashboard_main(["--db-file", str(db_file), "list-bugs", "--open"])
    captured = capsys.readouterr()
    assert "BUG-CLI-001" in captured.out
    assert "AWAITING REVIEW" in captured.out

    # 5. reject-bug
    dashboard_main(["--db-file", str(db_file), "reject-bug", "--id", "BUG-CLI-001", "--notes", "CLI rejected this"])
    updated = store.get_bug("BUG-CLI-001")
    assert updated.status == BugStatus.OPEN
    assert updated.rejection_notes == "CLI rejected this"
    assert updated.rejected_at is not None

    # Re-resolve for accept test
    updated.status = BugStatus.RESOLVED
    store.save_bug(updated)

    # 6. accept-bug
    dashboard_main(["--db-file", str(db_file), "accept-bug", "--id", "BUG-CLI-001", "--notes", "CLI accepted this"])
    updated = store.get_bug("BUG-CLI-001")
    assert updated.status == BugStatus.CLOSED
    assert updated.accepted_at is not None

    # Verify list-bugs --open now hides the CLOSED bug
    capsys.readouterr()
    dashboard_main(["--db-file", str(db_file), "list-bugs", "--open"])
    captured = capsys.readouterr()
    assert "BUG-CLI-001" not in captured.out
