"""Tests for detached feedback/attachments push and duplicate bug ID collision detection/mitigation in hardware.

Verifies:
1. Pushing feedback/ and attachments/ via DetachedBranchBugStore.sync_branch(push=True)
   and GitEngine.sync_repo(push=True).
2. Collision detection and mitigation when merging databases with duplicate bug IDs (different UUIDs).
3. Collision detection and mitigation in BugDatabaseModel.add_or_update().
4. Collision detection and mitigation in MarkdownBugExporter.scan_and_sync_feedback_dir().
"""

from pathlib import Path
import subprocess
import uuid

import pytest

from model.bug_report import (
    BugAttachmentModel,
    BugCategory,
    BugDatabaseModel,
    BugReportModel,
    BugSeverity,
    BugStatus,
)
from provider.bug_report.detached_branch import DetachedBranchBugStore
from provider.bug_report.markdown_exporter import MarkdownBugExporter
from provider.vcs.git_engine import GitEngine


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in specified working directory."""
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def repo_with_remote(tmp_path: Path):
    """Create a pair of git repositories: bare remote origin and cloned local working repo."""
    remote_dir = tmp_path / "remote.git"
    remote_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", str(remote_dir)], check=True, capture_output=True)

    local_dir = tmp_path / "local"
    local_dir.mkdir(parents=True)
    run_git(["init", "-b", "main"], cwd=local_dir)
    run_git(["config", "user.name", "User"], cwd=local_dir)
    run_git(["config", "user.email", "user@workspace"], cwd=local_dir)

    readme = local_dir / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    run_git(["add", "README.md"], cwd=local_dir)
    run_git(["commit", "-m", "Initial commit"], cwd=local_dir)
    run_git(["remote", "add", "origin", str(remote_dir)], cwd=local_dir)
    run_git(["push", "-u", "origin", "main"], cwd=local_dir)

    return local_dir, remote_dir


def test_collision_detection_in_add_or_update() -> None:
    """Verify BugDatabaseModel.add_or_update detects duplicate IDs with different UUIDs."""
    db = BugDatabaseModel(title="Test DB")
    b1 = BugReportModel(
        id="BUG-FIERCE-LONGHORN-800",
        uuid=str(uuid.uuid4()),
        title="First Bug",
        status=BugStatus.OPEN,
        severity=BugSeverity.HIGH,
        category=BugCategory.PCB,
    )
    db.add_or_update(b1)
    assert len(db.bugs) == 1
    assert db.bugs[0].id == "BUG-FIERCE-LONGHORN-800"

    # Same UUID: update in place
    b1_updated = b1.model_copy()
    b1_updated.title = "First Bug Updated"
    db.add_or_update(b1_updated)
    assert len(db.bugs) == 1
    assert db.bugs[0].title == "First Bug Updated"

    # Different UUID with SAME ID: COLLISION!
    b2_colliding = BugReportModel(
        id="BUG-FIERCE-LONGHORN-800",
        uuid=str(uuid.uuid4()),
        title="Second Colliding Bug",
        status=BugStatus.OPEN,
        severity=BugSeverity.MEDIUM,
        category=BugCategory.CAD,
    )
    assigned_id = db.add_or_update(b2_colliding)

    # Both bugs must be preserved!
    assert len(db.bugs) == 2
    assert db.bugs[0].id == "BUG-FIERCE-LONGHORN-800"
    assert db.bugs[0].title == "First Bug Updated"

    assert db.bugs[1].id == assigned_id
    assert db.bugs[1].id != "BUG-FIERCE-LONGHORN-800"
    assert db.bugs[1].title == "Second Colliding Bug"
    assert db.bugs[1].id.startswith("BUG-")


def test_collision_detection_in_merge_databases(tmp_path: Path) -> None:
    """Verify MarkdownBugExporter.merge_databases detects and mitigates duplicate ID collisions."""
    exporter = MarkdownBugExporter(tmp_path)

    u1 = str(uuid.uuid4())
    u2 = str(uuid.uuid4())

    base_db = BugDatabaseModel(
        bugs=[
            BugReportModel(
                id="BUG-DUPLICATE-ID-123",
                uuid=u1,
                title="Local Bug Alpha",
                status=BugStatus.OPEN,
                severity=BugSeverity.CRITICAL,
                category=BugCategory.PCB,
            )
        ]
    )

    incoming_db = BugDatabaseModel(
        bugs=[
            # Shares the same ID but has a completely different UUID
            BugReportModel(
                id="BUG-DUPLICATE-ID-123",
                uuid=u2,
                title="Remote Bug Beta",
                status=BugStatus.RESOLVED,
                severity=BugSeverity.LOW,
                category=BugCategory.CAD,
                resolution_notes="Fixed upstream",
            )
        ]
    )

    merged = exporter.merge_databases(base_db, incoming_db)

    # Both bugs must survive collision mitigation
    assert len(merged.bugs) == 2

    # Original bug retained its ID
    bug_alpha = next(b for b in merged.bugs if b.uuid == u1)
    assert bug_alpha.id == "BUG-DUPLICATE-ID-123"
    assert bug_alpha.title == "Local Bug Alpha"

    # Incoming bug received a new unique ID
    bug_beta = next(b for b in merged.bugs if b.uuid == u2)
    assert bug_beta.id != "BUG-DUPLICATE-ID-123"
    assert bug_beta.title == "Remote Bug Beta"
    assert bug_beta.resolution_notes == "Fixed upstream"
    assert bug_beta.id.startswith("BUG-")


def test_collision_detection_in_scan_feedback_dir(tmp_path: Path) -> None:
    """Verify scan_and_sync_feedback_dir mitigates collisions when an untracked file reuses an ID."""
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir(parents=True)
    exporter = MarkdownBugExporter(tmp_path)

    u_orig = str(uuid.uuid4())
    db = BugDatabaseModel(
        bugs=[
            BugReportModel(
                id="BUG-EXISTING-ID-999",
                uuid=u_orig,
                title="Existing Database Bug",
                status=BugStatus.OPEN,
                severity=BugSeverity.HIGH,
                category=BugCategory.SIMULATION,
            )
        ]
    )

    # Create a markdown file on disk with the same ID but a different UUID
    u_new = str(uuid.uuid4())
    colliding_file = feedback_dir / "BUG_EXISTING-ID-999.md"
    colliding_file.write_text(
        f"# `[BUG-EXISTING-ID-999]` Conflicting File Bug\n\n"
        f"- **UUID**: `{u_new}`\n"
        f"- **ID**: `BUG-EXISTING-ID-999`\n"
        f"- **Status**: `OPEN`\n"
        f"- **Severity**: `MEDIUM`\n"
        f"- **Category**: `CAD`\n\n"
        f"#### Description\n\nColliding description.\n",
        encoding="utf-8",
    )

    stats = exporter.scan_and_sync_feedback_dir(feedback_dir, db)
    assert stats["scanned"] == 1
    assert stats["merged"] == 1

    # Both bugs must exist in database!
    assert len(db.bugs) == 2
    b1 = db.get_bug_by_uuid(u_orig)
    assert b1 is not None
    assert b1.id == "BUG-EXISTING-ID-999"

    b2 = db.get_bug_by_uuid(u_new)
    assert b2 is not None
    assert b2.id != "BUG-EXISTING-ID-999"
    assert b2.title == "Conflicting File Bug"


def test_sync_branch_pushes_feedback_and_attachments(repo_with_remote) -> None:
    """Verify DetachedBranchBugStore.sync_branch pushes feedback reports and attachments to remote."""
    local_dir, remote_dir = repo_with_remote
    store = DetachedBranchBugStore(local_dir, branch_name="bugs")

    # Create a bug with an attachment
    bug_id = "BUG-PUSH-TEST-101"
    att_dir = local_dir / "attachments" / bug_id
    att_dir.mkdir(parents=True)
    sample_log = att_dir / "sample.log"
    sample_log.write_text("Crash log contents\n", encoding="utf-8")

    db = BugDatabaseModel(
        bugs=[
            BugReportModel(
                id=bug_id,
                uuid=str(uuid.uuid4()),
                title="Bug to be pushed",
                status=BugStatus.OPEN,
                severity=BugSeverity.HIGH,
                category=BugCategory.PCB,
                attachments=[
                    BugAttachmentModel(
                        id="att-101",
                        filename="sample.log",
                        file_type="log",
                        file_path=f"attachments/{bug_id}/sample.log",
                        size_bytes=len("Crash log contents\n"),
                    )
                ],
            )
        ]
    )

    # Commit to detached branch
    commit_sha = store.commit_database(
        db,
        commit_message="Add push test bug",
        extra_feedback_dir=local_dir / "feedback",
    )
    assert commit_sha is not None

    # Sync branch with push=True
    res = store.sync_branch(push=True)
    assert res["status"] == "ok"
    assert res["pushed"] is True

    # Verify remote bare repo has refs/heads/bugs with the commit
    remote_bug_commit = run_git(["rev-parse", "refs/heads/bugs"], cwd=remote_dir).stdout.strip()
    assert remote_bug_commit == res["commit"]

    # Verify remote has feedback file and attachment, but explicitly NO bugs.json or BUGS.md
    ls_remote = run_git(["ls-tree", "-r", "--name-only", "refs/heads/bugs"], cwd=remote_dir).stdout
    assert "bugs.json" not in ls_remote
    assert "BUGS.md" not in ls_remote
    assert "BUGS.json" not in ls_remote
    assert any(line.endswith(f"BUG_{bug_id.removeprefix('BUG-')}.md") for line in ls_remote.splitlines())
    assert f"attachments/{bug_id}/sample.log" in ls_remote


def test_git_engine_sync_repo_pushes_detached_branch(repo_with_remote) -> None:
    """Verify GitEngine.sync_repo(push=True) pushes the detached branch."""
    local_dir, remote_dir = repo_with_remote
    engine = GitEngine(local_dir)
    store = DetachedBranchBugStore(local_dir, branch_name="bugs")

    db = BugDatabaseModel(
        bugs=[
            BugReportModel(
                id="BUG-ENGINE-SYNC-202",
                uuid=str(uuid.uuid4()),
                title="GitEngine sync test",
                status=BugStatus.OPEN,
                severity=BugSeverity.LOW,
                category=BugCategory.UI,
            )
        ]
    )
    store.commit_database(db, commit_message="Bug for GitEngine sync")

    # Add an unpushed local commit to main
    test_code_file = local_dir / "test.txt"
    test_code_file.write_text("unpushed code\n", encoding="utf-8")
    run_git(["add", "test.txt"], cwd=local_dir)
    run_git(["commit", "-m", "Unpushed code commit"], cwd=local_dir)
    local_main_sha = run_git(["rev-parse", "main"], cwd=local_dir).stdout.strip()
    remote_main_before = run_git(["rev-parse", "main"], cwd=remote_dir).stdout.strip()

    # Run sync_repo with push=True
    sync_res = engine.sync_repo(push=True)
    assert sync_res["status"] == "ok"
    assert sync_res["detached"]["pushed"] is True
    assert "Feedback and attachments pushed" in sync_res["message"]

    # Verify remote has the bug ref
    remote_sha = run_git(["rev-parse", "refs/heads/bugs"], cwd=remote_dir).stdout.strip()
    assert len(remote_sha) == 40

    # Verify remote main was NOT pushed (code branches must only be pushed via user-managed PRs)
    remote_main_after = run_git(["rev-parse", "main"], cwd=remote_dir).stdout.strip()
    assert remote_main_after == remote_main_before
    assert remote_main_after != local_main_sha


def test_stage_feedback_files_tracks_bugs_crs_and_excludes_index_files(repo_with_remote) -> None:
    """Verify GitEngine.stage_feedback_files stages BUG_*.md, CR_*.md and explicitly excludes index files."""
    local_dir, _ = repo_with_remote
    engine = GitEngine(local_dir)

    feedback_dir = local_dir / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    # Create individual bug and CR files
    bug_file = feedback_dir / "BUG_TEST-101.md"
    bug_file.write_text("# Bug 101\n", encoding="utf-8")
    cr_file = feedback_dir / "CR_1234567.md"
    cr_file.write_text("# CR 1234567\n", encoding="utf-8")

    # Create index files that MUST NOT be staged/tracked
    bugs_idx = feedback_dir / "BUGS.md"
    bugs_idx.write_text("# BUGS Index\n", encoding="utf-8")
    cr_idx = feedback_dir / "CR.md"
    cr_idx.write_text("# CR Index\n", encoding="utf-8")
    root_bugs_idx = local_dir / "BUGS.md"
    root_bugs_idx.write_text("# Root BUGS Index\n", encoding="utf-8")

    # Call stage_feedback_files
    staged = engine.stage_feedback_files()
    assert "feedback/BUG_TEST-101.md" in staged
    assert "feedback/CR_1234567.md" in staged
    assert "feedback/BUGS.md" not in staged
    assert "feedback/CR.md" not in staged
    assert "BUGS.md" not in staged

    # Verify git index via diff --cached
    staged_in_git = run_git(["diff", "--cached", "--name-only"], cwd=local_dir).stdout.splitlines()
    assert "feedback/BUG_TEST-101.md" in staged_in_git
    assert "feedback/CR_1234567.md" in staged_in_git
    assert "feedback/BUGS.md" not in staged_in_git
    assert "feedback/CR.md" not in staged_in_git
    assert "BUGS.md" not in staged_in_git
