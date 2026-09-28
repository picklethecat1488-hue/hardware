"""Unit tests for Quake Diff Viewer, Smartlog DAG tree, and VCS Workstation.

Validates DiffViewServer REST API endpoints, Smartlog DAG generation, working tree
staging/unstaging/discarding/committing, commit split/combine, merge conflict resolution,
and inter-tool navigation to code_review and bug_report.
"""

import json
from pathlib import Path
import subprocess
import threading
import time
from typing import Tuple
import urllib.request

import pytest

from diff_view import parse_arguments, print_cli_smartlog
from model.vcs import (
    BranchInfoModel,
    CommitNodeModel,
    DiffViewSessionModel,
    FileDiffModel,
    WorkingTreeFileModel,
)
from provider.diff_view.server import DiffViewServer
from provider.vcs.git_engine import GitEngine, get_git_root


def create_isolated_git_repo(path: Path) -> Tuple[Path, list[str]]:
    """Create a minimal isolated git repository with multiple branches and commits for testing."""
    repo_dir = path / "git_test_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Engineer"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_dir, check=True, capture_output=True)

    # Commit 1
    f1 = repo_dir / "file1.txt"
    f1.write_text("initial line 1\ninitial line 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "file1.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit (BUG-168)"], cwd=repo_dir, check=True, capture_output=True)
    sha1 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    # Commit 2
    f2 = repo_dir / "file2.py"
    f2.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    subprocess.run(["git", "add", "file2.py"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add hello function"], cwd=repo_dir, check=True, capture_output=True)
    sha2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    # Commit 3
    f1.write_text("initial line 1\nmodified line 2\nnew line 3\n", encoding="utf-8")
    subprocess.run(["git", "add", "file1.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Modify file1 (BUG-171)"], cwd=repo_dir, check=True, capture_output=True)
    sha3 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    return repo_dir, [sha1, sha2, sha3]


def test_diff_view_server_initialization_and_session(tmp_path: Path) -> None:
    """Verify DiffViewServer initializes and constructs session data model."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    server = DiffViewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    try:
        session = server.build_session()
        assert isinstance(session, DiffViewSessionModel)
        assert session.repo_name == "git_test_repo"
        assert len(session.smartlog_nodes) >= 3
        assert any(n.commit_hash == shas[2] for n in session.smartlog_nodes)
        assert len(session.branches) >= 1
    finally:
        server.server_close()


def test_diff_view_http_get_endpoints(tmp_path: Path) -> None:
    """Verify HTTP GET endpoints: UI dashboard, /api/session, /api/commits, /api/branches, /api/diff, /api/raw."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    server = DiffViewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = server.get_url()

    try:
        # 1. UI HTML dashboard
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "QUAKE VCS" in html
            assert "DIFF VIEWER &amp; SMARTLOG" in html or "DIFF VIEWER & SMARTLOG" in html
            assert "Smartlog Tree (sl)" in html

        # 2. /api/session
        with urllib.request.urlopen(f"{base_url}/api/session") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["repo_name"] == "git_test_repo"
            assert len(data["smartlog_nodes"]) >= 3

        # 3. /api/commits
        with urllib.request.urlopen(f"{base_url}/api/commits?limit=5") as resp:
            assert resp.status == 200
            nodes = json.loads(resp.read().decode("utf-8"))
            assert len(nodes) == 3
            assert nodes[0]["commit_hash"] == shas[2]

        # 4. /api/branches
        with urllib.request.urlopen(f"{base_url}/api/branches") as resp:
            assert resp.status == 200
            branches = json.loads(resp.read().decode("utf-8"))
            assert len(branches) >= 1

        # 5. /api/files
        with urllib.request.urlopen(f"{base_url}/api/files?commit={shas[2]}") as resp:
            assert resp.status == 200
            files = json.loads(resp.read().decode("utf-8"))
            assert any(f["path"] == "file1.txt" for f in files)

        # 6. /api/diff
        with urllib.request.urlopen(f"{base_url}/api/diff?commit={shas[2]}&file=file1.txt") as resp:
            assert resp.status == 200
            diff = json.loads(resp.read().decode("utf-8"))
            assert diff["file_path"] == "file1.txt"
            assert diff["additions"] > 0
            assert len(diff["hunks"]) > 0

        # 7. /api/raw
        with urllib.request.urlopen(f"{base_url}/api/raw?commit={shas[2]}&file=file1.txt&parent=false") as resp:
            assert resp.status == 200
            raw_text = resp.read().decode("utf-8")
            assert "modified line 2" in raw_text

    finally:
        server.shutdown()
        server.server_close()


def test_working_tree_staging_unstaging_and_discarding(tmp_path: Path) -> None:
    """Verify POST endpoints for staging, unstaging, discarding, and committing files."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    server = DiffViewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = server.get_url()

    try:
        # Create an untracked file
        untracked = repo_dir / "untracked_sample.txt"
        untracked.write_text("some untracked content\n", encoding="utf-8")

        # 1. Check working files
        with urllib.request.urlopen(f"{base_url}/api/working") as resp:
            files = json.loads(resp.read().decode("utf-8"))
            match_untracked = [f for f in files if f["path"] == "untracked_sample.txt"]
            assert len(match_untracked) == 1
            assert match_untracked[0]["is_untracked"] is True

        # 2. Stage file
        req = urllib.request.Request(
            f"{base_url}/api/stage",
            data=json.dumps({"file": "untracked_sample.txt"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert res["staged"] == "untracked_sample.txt"

        # Verify it is now staged
        with urllib.request.urlopen(f"{base_url}/api/working") as resp:
            files = json.loads(resp.read().decode("utf-8"))
            staged_file = [f for f in files if f["path"] == "untracked_sample.txt"][0]
            assert staged_file["is_staged"] is True

        # 3. Unstage file
        req = urllib.request.Request(
            f"{base_url}/api/unstage",
            data=json.dumps({"file": "untracked_sample.txt"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"

        # 4. Discard untracked file
        req = urllib.request.Request(
            f"{base_url}/api/discard",
            data=json.dumps({"file": "untracked_sample.txt"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"

        assert not untracked.exists()

        # 5. Commit staged changes test
        mod_file = repo_dir / "file1.txt"
        mod_file.write_text("changed for commit test\n", encoding="utf-8")
        subprocess.run(["git", "add", "file1.txt"], cwd=repo_dir, check=True, capture_output=True)

        req = urllib.request.Request(
            f"{base_url}/api/commit",
            data=json.dumps({"message": "test commit via api"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert len(res["commit_hash"]) == 40

    finally:
        server.shutdown()
        server.server_close()


def test_commit_split_and_combine(tmp_path: Path) -> None:
    """Verify POST /api/split and /api/combine commit manipulation endpoints."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    server = DiffViewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = server.get_url()

    try:
        # 1. Split commit HEAD (Commit 3)
        req = urllib.request.Request(
            f"{base_url}/api/split",
            data=json.dumps({"commit": "HEAD"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"

        # Now HEAD should be Commit 2, and file1.txt changes are in working tree
        head_now = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
        ).stdout.strip()
        assert head_now == shas[1]

        # Re-commit file1.txt as two separate commits
        subprocess.run(["git", "add", "file1.txt"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Part A"], cwd=repo_dir, check=True, capture_output=True)
        new_sha_a = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
        ).stdout.strip()

        # Another commit
        f3 = repo_dir / "file3.txt"
        f3.write_text("content 3\n", encoding="utf-8")
        subprocess.run(["git", "add", "file3.txt"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Part B"], cwd=repo_dir, check=True, capture_output=True)
        new_sha_b = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
        ).stdout.strip()

        # 2. Combine Part A and Part B
        req = urllib.request.Request(
            f"{base_url}/api/combine",
            data=json.dumps({"commits": [new_sha_b, new_sha_a], "message": "Combined A and B"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            combined_sha = res["commit_hash"]
            assert len(combined_sha) == 40

        # Verify combined commit message
        log_msg = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"], cwd=repo_dir, check=True, capture_output=True, text=True
        ).stdout.strip()
        assert log_msg == "Combined A and B"

    finally:
        server.shutdown()
        server.server_close()


def test_merge_conflict_detection_and_resolution(tmp_path: Path) -> None:
    """Verify merge conflict detection and resolution via POST /api/resolve_conflict."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)

    # Create a conflicting branch
    subprocess.run(["git", "checkout", "-b", "conflict-branch", shas[0]], cwd=repo_dir, check=True, capture_output=True)
    cfile = repo_dir / "file1.txt"
    cfile.write_text("branch conflict line\n", encoding="utf-8")
    subprocess.run(["git", "add", "file1.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Branch conflict edit"], cwd=repo_dir, check=True, capture_output=True)

    # Switch to main and attempt merge to produce conflict
    subprocess.run(
        [
            "git",
            "checkout",
            "master"
            if "master" in str(subprocess.run(["git", "branch"], cwd=repo_dir, capture_output=True).stdout)
            else "main",
        ],
        cwd=repo_dir,
        check=False,
        capture_output=True,
    )
    # Trigger conflict
    subprocess.run(["git", "merge", "conflict-branch"], cwd=repo_dir, check=False, capture_output=True)

    engine = GitEngine(repo_root=repo_dir)
    conflicts = engine.get_merge_conflicts()
    assert len(conflicts) >= 1
    assert any(c.path == "file1.txt" for c in conflicts)

    server = DiffViewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = server.get_url()

    try:
        # GET /api/conflicts
        with urllib.request.urlopen(f"{base_url}/api/conflicts") as resp:
            conf_data = json.loads(resp.read().decode("utf-8"))
            assert len(conf_data) >= 1
            assert conf_data[0]["path"] == "file1.txt"

        # POST /api/resolve_conflict using 'ours'
        req = urllib.request.Request(
            f"{base_url}/api/resolve_conflict",
            data=json.dumps({"file": "file1.txt", "resolution": "ours"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"

        # Conflict is now resolved and staged
        conflicts_after = engine.get_merge_conflicts()
        assert len(conflicts_after) == 0

    finally:
        server.shutdown()
        server.server_close()


def test_cross_tool_endpoints_code_review_and_bug_viewer(tmp_path: Path) -> None:
    """Verify POST /api/open_code_review and /api/open_bug format target URLs."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    server = DiffViewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = server.get_url()

    try:
        # 1. Code Review multi-commit redirect
        req = urllib.request.Request(
            f"{base_url}/api/open_code_review",
            data=json.dumps({"commits": [shas[1], shas[2]]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert f"revisions={shas[1]},{shas[2]}" in res["url"]

        # 2. Bug Viewer navigation for existing bug
        req = urllib.request.Request(
            f"{base_url}/api/open_bug",
            data=json.dumps({"bug_id": "171"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert "8766/#BUG-171" in res["url"]

        # 3. Bug Viewer creation prefilling commit
        req = urllib.request.Request(
            f"{base_url}/api/open_bug",
            data=json.dumps({"commit": shas[2]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert f"commit={shas[2]}" in res["url"]

    finally:
        server.shutdown()
        server.server_close()


def test_cli_smartlog_printer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify print_cli_smartlog prints the ASCII DAG tree and working tree summary to stdout."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    print_cli_smartlog(engine)
    captured = capsys.readouterr().out
    assert "QUAKE VCS // SMARTLOG DAG TREE" in captured
    assert "WORKING TREE" in captured
    assert "Initial commit" in captured
    assert "Modify file1" in captured
