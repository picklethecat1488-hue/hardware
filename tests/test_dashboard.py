"""Unit tests for Quake Diff Viewer, Smartlog DAG tree, and VCS Workstation.

Validates DiffViewServer REST API endpoints, Smartlog DAG generation, working tree
staging/unstaging/discarding/committing, commit split/combine, merge conflict resolution,
and inter-tool navigation to code_review and bug_report.
"""

import base64
import json
from pathlib import Path
import sqlite3
import subprocess
import threading
import time
from typing import Tuple
from unittest.mock import MagicMock
import urllib.request

import pytest

from forge import main, parse_arguments, print_cli_smartlog
from model.vcs import (
    BranchInfoModel,
    CommitNodeModel,
    DiffViewSessionModel,
    FileDiffModel,
    WorkingTreeFileModel,
)
from provider.dashboard.server import DashboardRequestHandler, DashboardServer
from provider.vcs.git_engine import GitEngine, get_git_root, run_git_command


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
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo_dir, check=True, capture_output=True)
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
    server = DashboardServer(
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
    server = DashboardServer(
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
    server = DashboardServer(
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
    server = DashboardServer(
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

    server = DashboardServer(
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
    server = DashboardServer(
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
            assert "/review" in res["url"]
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
            assert "/bugs#BUG-171" in res["url"]

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
            assert "/bugs" in res["url"]
            assert f"commit={shas[2]}" in res["url"]

        # 4. Direct GET /review and /bugs UI serving
        with urllib.request.urlopen(f"{base_url}/review") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "Code Review" in html or "quake" in html.lower()

        with urllib.request.urlopen(f"{base_url}/bugs") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "BUG REPORT" in html or "quake" in html.lower()

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


def test_regression_bug_178_unified_dashboard_and_no_standalone_tools(tmp_path: Path) -> None:
    """Verify BUG-178: standalone bug_report/code_review tools are removed and integrated into forge.py."""
    repo_root = get_git_root()

    # 1. Standalone scripts MUST NOT exist
    assert not (repo_root / "src" / "bug_report.py").exists()
    assert not (repo_root / "src" / "code_review.py").exists()
    assert not (repo_root / "src" / "diff_view.py").exists()
    assert not (repo_root / "tools" / "bug_report.py").exists()
    assert not (repo_root / "tools" / "code_review.py").exists()
    assert not (repo_root / "tools" / "diff_view.py").exists()

    # 2. Unified forge script MUST exist
    forge_script = repo_root / "tools" / "forge.py"
    assert forge_script.exists()

    # 3. Test unified server on ephemeral port
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    server = DashboardServer(
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
        # Check diff view UI
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")

        # Check code review UI
        with urllib.request.urlopen(f"{base_url}/review") as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")

        # Check bug report UI
        with urllib.request.urlopen(f"{base_url}/bugs") as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")

        # Check POST /api/verdict concluding does NOT shut down the server
        req = urllib.request.Request(
            f"{base_url}/api/verdict",
            data=json.dumps({"verdict": "APPROVED"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert res["terminating"] is False

        # Server is still alive and accepting requests
        with urllib.request.urlopen(f"{base_url}/api/commits") as resp:
            assert resp.status == 200

        # Check POST /api/exit does NOT shut down the server
        req_exit = urllib.request.Request(
            f"{base_url}/api/exit",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_exit) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "saved_and_exited"

        # Server is still alive
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200

    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_185_commit_amend_and_discard_files(tmp_path: Path) -> None:
    """Verify BUG-185: GitEngine and HTTP endpoints for selective commit, amend, and multi-file discard."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    # Make changes to file1.txt, file2.py, and create an untracked file
    f1 = repo_dir / "file1.txt"
    f1.write_text("updated file1\n", encoding="utf-8")
    f2 = repo_dir / "file2.py"
    f2.write_text("# updated file2\n", encoding="utf-8")
    f_untracked = repo_dir / "untracked_sample.txt"
    f_untracked.write_text("untracked\n", encoding="utf-8")

    # Selective commit: only commit file1.txt
    new_sha = engine.commit_files("Selective commit for file1", file_paths=["file1.txt"], amend=False)
    assert new_sha != shas[2]
    assert engine.get_head_commit_message() == "Selective commit for file1"

    # Verify file2.py and untracked_sample.txt are still in working tree
    working_files = engine.get_working_tree_files()
    working_paths = [f.path for f in working_files]
    assert "file2.py" in working_paths
    assert "untracked_sample.txt" in working_paths
    assert "file1.txt" not in working_paths

    # Amend commit with file2.py
    amended_sha = engine.commit_files("Amended commit with file2 (BUG-185)", file_paths=["file2.py"], amend=True)
    assert engine.get_head_commit_message() == "Amended commit with file2 (BUG-185)"

    # Verify file2.py is now committed and untracked_sample.txt is still untracked
    working_files = engine.get_working_tree_files()
    working_paths = [f.path for f in working_files]
    assert "file2.py" not in working_paths
    assert "untracked_sample.txt" in working_paths

    # Discard untracked file
    engine.discard_file("untracked_sample.txt")
    assert not f_untracked.exists()

    # 3. Test HTTP Server endpoints: /api/head_commit_message, /api/commit with files, /api/amend, /api/discard
    server = DashboardServer(
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
        # Check GET /api/head_commit_message
        with urllib.request.urlopen(f"{base_url}/api/head_commit_message") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["message"] == "Amended commit with file2 (BUG-185)"

        # Create two untracked files
        t1 = repo_dir / "target1.txt"
        t1.write_text("target 1\n", encoding="utf-8")
        t2 = repo_dir / "target2.txt"
        t2.write_text("target 2\n", encoding="utf-8")

        # Selective commit via API
        req_commit = urllib.request.Request(
            f"{base_url}/api/commit",
            data=json.dumps({"message": "Add target1 via API", "files": ["target1.txt"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_commit) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert "commit_hash" in res

        # Target2 should still be untracked
        assert t2.exists()
        working = engine.get_working_tree_files()
        assert any(w.path == "target2.txt" for w in working)

        # Amend via API
        req_amend = urllib.request.Request(
            f"{base_url}/api/amend",
            data=json.dumps({"message": "Add target1 and target2 via API", "files": ["target2.txt"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_amend) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert engine.get_head_commit_message() == "Add target1 and target2 via API"

        # Discard multiple files via API
        t3 = repo_dir / "target3.txt"
        t3.write_text("to discard\n", encoding="utf-8")
        f1.write_text("modified to discard\n", encoding="utf-8")

        req_discard = urllib.request.Request(
            f"{base_url}/api/discard",
            data=json.dumps({"files": ["target3.txt", "file1.txt"]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_discard) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert "target3.txt" in res["discarded"]
            assert "file1.txt" in res["discarded"]

        assert not t3.exists()
        assert f1.read_text(encoding="utf-8") == "updated file1\n"

    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_186_lfs_tracking_for_attachments(tmp_path: Path) -> None:
    """Verify BUG-186: Automatically track attachments in Git LFS when committing/amending."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_dir)

    # 1. Check .gitattributes at root has attachments/*
    root_repo = Path(__file__).resolve().parent.parent
    root_ga = (root_repo / ".gitattributes").read_text(encoding="utf-8")
    assert "attachments/* filter=lfs diff=lfs merge=lfs -text" in root_ga
    assert "attachments/** filter=lfs diff=lfs merge=lfs -text" in root_ga

    # 2. In isolated repo, add an attachment under attachments/
    att_dir = repo_dir / "attachments"
    att_dir.mkdir(parents=True, exist_ok=True)
    sample_img = att_dir / "test_screenshot.png"
    sample_img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

    # 3. Commit the attachment using commit_files
    commit_sha = engine.commit_files(message="Add attachment", file_paths=["attachments/test_screenshot.png"])
    assert commit_sha

    # 4. Verify .gitattributes was automatically updated and committed
    ga_file = repo_dir / ".gitattributes"
    assert ga_file.exists()
    ga_text = ga_file.read_text(encoding="utf-8")
    assert "attachments/* filter=lfs diff=lfs merge=lfs -text" in ga_text

    # 5. Verify /attachments/ serving via DashboardServer
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        with urllib.request.urlopen(f"{base_url}/attachments/test_screenshot.png") as resp:
            assert resp.status == 200
            assert resp.read() == b"\x89PNG\r\n\x1a\nfakeimagebytes"
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_194_lfs_tracked_files_grouping_and_styling(tmp_path: Path) -> None:
    """Verify BUG-194: GitEngine and /api/working identify LFS tracked files."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_dir)

    assets_dir = repo_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    lfs_file = assets_dir / "diagram.png"
    lfs_file.write_bytes(b"\x89PNG\r\n\x1a\ntestdiagram")

    reg_file = repo_dir / "main.py"
    reg_file.write_text("print('hello')\n", encoding="utf-8")

    # Ensure .gitattributes has LFS pattern
    ga = repo_dir / ".gitattributes"
    ga.write_text("assets/* filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")

    # 3. Check get_working_tree_files identifies is_lfs
    working = engine.get_working_tree_files()
    lfs_items = [w for w in working if w.is_lfs]
    reg_items = [w for w in working if not w.is_lfs and not w.is_feedback]
    assert any(w.path == "assets/diagram.png" for w in lfs_items)
    assert any(w.path == "main.py" for w in reg_items)

    # 4. Check get_changed_files identifies is_lfs
    changed = engine.get_changed_files("working", include_feedback=False)
    lfs_changed = [c for c in changed if c.get("is_lfs")]
    reg_changed = [c for c in changed if not c.get("is_lfs")]
    assert any(c["path"] == "assets/diagram.png" for c in lfs_changed)
    assert any(c["path"] == "main.py" for c in reg_changed)

    # 5. Check API endpoint /api/working returns is_lfs: true
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        with urllib.request.urlopen(f"{base_url}/api/working") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            lfs_api = [f for f in data if f.get("is_lfs")]
            reg_api = [f for f in data if not f.get("is_lfs") and not f.get("is_feedback")]
            assert any(f["path"] == "assets/diagram.png" for f in lfs_api)
            assert any(f["path"] == "main.py" for f in reg_api)
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_188_initial_sqlite_sync_loading_modal(tmp_path: Path) -> None:
    """Verify BUG-188: initial SQLite sync loading screen and feedback synchronization."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)

    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        assert not server.initial_sync_done

        # 3. GET / serves modal visible (display: flex) on initial load
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert 'id="syncModalOverlay"' in html
            assert "SYNCHRONIZING FEEDBACK DATABASES" in html
            assert "display: flex;" in html

        # 4. Check /api/sync_status returns false initially
        with urllib.request.urlopen(f"{base_url}/api/sync_status") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("initial_sync_done") is False

        # 5. Trigger /api/sync_feedback POST
        req = urllib.request.Request(
            f"{base_url}/api/sync_feedback",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert res["initial_sync_done"] is True
            assert "review" in res
            assert "bugs" in res

        # 6. Verify server state is now synced
        assert server.initial_sync_done is True

        with urllib.request.urlopen(f"{base_url}/api/sync_status") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("initial_sync_done") is True

        # 7. GET / now serves modal hidden (display: none)
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "display: none;" in html

    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_190_pr_branch_tag_clickable_link(tmp_path: Path) -> None:
    """Verify BUG-190: PR branch tags like pr520 render in DashboardServer smartlog HTML."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)

    run_git_command(["branch", "pr520", shas[1]], cwd=repo_dir)

    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "pr520" in html
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_192_pr_highlight_on_commit_element(tmp_path: Path) -> None:
    """Verify BUG-192: GitEngine detects pr_number/pr_url and DashboardServer renders PR #520."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    run_git_command(["branch", "pr520", shas[1]], cwd=repo_dir)

    nodes = engine.get_smartlog_dag(limit=10)
    pr_node = next(n for n in nodes if n.commit_hash == shas[1])
    assert pr_node.pr_number == 520
    assert pr_node.pr_status == "PR #520"
    assert "pull/520" in (pr_node.pr_url or "")

    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "PR #520" in html
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_193_create_and_unlink_pr_buttons_and_ancestors(tmp_path: Path) -> None:
    """Verify BUG-193: Create PR and Unlink PR backend actions and REST endpoints."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    res = engine.submit_prs()
    assert res["status"] == "ok"
    assert "logs" in res

    # 3. Create dummy PR branches to test unlinking
    run_git_command(["branch", "pr101", shas[1]], cwd=repo_dir)
    run_git_command(["branch", "pr102", shas[2]], cwd=repo_dir)

    # 4. Test unlinking PRs
    unlinked = engine.unlink_prs_for_commits([shas[1], shas[2]])
    assert len(unlinked) == 2
    assert any(u["commit"] == shas[1] for u in unlinked)
    assert any(u["commit"] == shas[2] for u in unlinked)

    # 5. Test validation: unlinking commit without PR raises ValueError
    with pytest.raises(ValueError, match="does not have an associated PR to unlink"):
        engine.unlink_prs_for_commits([shas[1]])

    # 6. Test DashboardServer REST endpoints /api/pr/create and /api/pr/unlink
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()

        # Successful PR creation/submission via API
        req = urllib.request.Request(
            f"{base_url}/api/pr/create",
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert "logs" in res

        # Successful PR unlink via API
        run_git_command(["branch", "pr103", shas[1]], cwd=repo_dir)
        req = urllib.request.Request(
            f"{base_url}/api/pr/unlink",
            data=json.dumps({"commits": [shas[1]]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert len(res["unlinked"]) == 1
            assert res["unlinked"][0]["commit"] == shas[1]

        # Unlink again returns 400
        req = urllib.request.Request(
            f"{base_url}/api/pr/unlink",
            data=json.dumps({"commits": [shas[1]]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 400

    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_198_save_bug_reproduction_steps_no_traceback(tmp_path: Path) -> None:
    """Verify BUG-198: Saving bug report with steps_to_reproduce and commit does not cause traceback."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        sqlite_bug_file=tmp_path / "bugs.sqlite",
        sqlite_review_file=tmp_path / "review.sqlite",
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = f"http://127.0.0.1:{server.actual_port}"

        # 1. Create bug with steps_to_reproduce and commit in payload (Save and Exit action)
        payload = {
            "title": "Bug with steps",
            "status": "OPEN",
            "severity": "HIGH",
            "category": "INFRASTRUCTURE",
            "component": "dashboard",
            "description": "Traceback observed",
            "steps_to_reproduce": ["Click Save and Exit", "Verify no traceback"],
            "commit": "947e55f5",
        }
        req = urllib.request.Request(
            f"{base_url}/api/bug/save",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["title"] == "Bug with steps"
            assert data["reproduction_steps"] == ["Click Save and Exit", "Verify no traceback"]
            bug_id = data["id"]

        # 2. Update existing bug with steps_to_reproduce
        update_payload = {
            "id": bug_id,
            "title": "Updated Bug",
            "steps_to_reproduce": ["Step A", "Step B"],
        }
        req2 = urllib.request.Request(
            f"{base_url}/api/bug/save",
            data=json.dumps(update_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2) as resp:
            assert resp.status == 200
            updated_data = json.loads(resp.read().decode("utf-8"))
            assert updated_data["title"] == "Updated Bug"
            assert updated_data["reproduction_steps"] == ["Step A", "Step B"]

    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_191_and_205_code_review_revisions_and_multi_commit(tmp_path: Path) -> None:
    """Verify BUG-191 & BUG-205: Code review with single selected commit or multiple commits opens expected commits."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        sqlite_bug_file=tmp_path / "bugs.sqlite",
        sqlite_review_file=tmp_path / "review.sqlite",
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = f"http://127.0.0.1:{server.actual_port}"

        # BUG-205: Selecting non-HEAD commit (shas[1]) opens that specific commit, not HEAD (shas[2])
        req = urllib.request.Request(
            f"{base_url}/api/open_code_review",
            data=json.dumps({"commits": [shas[1]]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert res["url"] == f"/review?revisions={shas[1]}"

        # Session API with revisions query returns selected commit
        with urllib.request.urlopen(f"{base_url}/api/session?revisions={shas[1]}") as resp:
            assert resp.status == 200
            session_data = json.loads(resp.read().decode("utf-8"))
            assert session_data["commit_hash"] == shas[1]
            assert session_data["revisions"] == [shas[1]]

        # Commits API with revisions returns CommitInfoModel for requested commit
        with urllib.request.urlopen(f"{base_url}/api/commits?revisions={shas[1]}") as resp:
            assert resp.status == 200
            commits_data = json.loads(resp.read().decode("utf-8"))
            assert len(commits_data) >= 1
            assert commits_data[0]["commit_hash"] == shas[1]
            assert "files_count" in commits_data[0]

        # Review UI HTML renders for requested revision with collapsed pane for single commit
        with urllib.request.urlopen(f"{base_url}/review?revisions={shas[1]}") as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "Code Review:" in html
            assert 'id="paneCommits" class="pane-commits collapsed"' in html

        # BUG-191: Selecting multiple commits (shas[0], shas[1]) creates multi-commit review session
        multi_revs = f"{shas[0]},{shas[1]}"
        req_multi = urllib.request.Request(
            f"{base_url}/api/open_code_review",
            data=json.dumps({"commits": [shas[0], shas[1]]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_multi) as resp:
            assert resp.status == 200
            res_multi = json.loads(resp.read().decode("utf-8"))
            assert res_multi["url"] == f"/review?revisions={multi_revs}"

        with urllib.request.urlopen(f"{base_url}/api/session?revisions={multi_revs}") as resp:
            assert resp.status == 200
            multi_session = json.loads(resp.read().decode("utf-8"))
            assert multi_session["commit_hash"] == shas[0]
            assert multi_session["revisions"] == [shas[0], shas[1]]

        with urllib.request.urlopen(f"{base_url}/api/commits?revisions={multi_revs}") as resp:
            assert resp.status == 200
            multi_commits = json.loads(resp.read().decode("utf-8"))
            assert len(multi_commits) == 2
            commit_hashes = {c["commit_hash"] for c in multi_commits}
            assert shas[0] in commit_hashes
            assert shas[1] in commit_hashes

        with urllib.request.urlopen(f"{base_url}/review?revisions={multi_revs}") as resp:
            assert resp.status == 200
            multi_html = resp.read().decode("utf-8")
            assert "Code Review" in multi_html

    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_190_pr_branch_tags_clickable_links(tmp_path: Path) -> None:
    """Verify BUG-190: GitEngine resolves PR and normal branch URLs accurately."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    pr_branch_url = engine.get_branch_url("origin/pr520")
    assert pr_branch_url.endswith("/pull/520"), f"Expected PR URL for origin/pr520, got {pr_branch_url}"

    norm_branch_url = engine.get_branch_url("origin/feature-xyz")
    assert norm_branch_url.endswith("/tree/feature-xyz"), f"Expected branch tree URL, got {norm_branch_url}"


def test_regression_bug_199_jump_to_cr_icon_button_and_comment_counter() -> None:
    """Verify BUG-199: CommitNodeModel tracks open, resolved, and total CR counts."""
    from model.vcs import CommitNodeModel

    node = CommitNodeModel(
        commit_hash="abc1234567890",
        short_hash="abc1234",
        author="Tester",
        date="2026-09-28",
        subject="Test commit",
        cr_open_count=2,
        cr_resolved_count=3,
        cr_total_count=5,
        cr_reviewed=True,
    )
    assert node.cr_open_count == 2
    assert node.cr_total_count == 5
    assert node.cr_reviewed is True


def test_regression_bug_212_pr_past_535_404_handling(tmp_path: Path) -> None:
    """Verify BUG-212: PRs past 534 without remote GitHub PRs do not link to 404 URLs."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    # 1. Mock remote PR numbers simulating GitHub state where only PRs <= 534 exist
    engine._remote_pr_cache = {530, 531, 532, 533, 534}

    # 2. Existing remote PR 534 resolves to valid GitHub PR URL
    status_534, num_534, url_534 = engine._extract_pr_info("feat: test", "", ["origin/pr534"], [])
    assert num_534 == 534
    assert status_534 == "PR #534"
    assert url_534 is not None and url_534.endswith("/pull/534")

    # 3. Unsubmitted PR 535 resolves to Local PR with None pr_url to prevent 404
    status_535, num_535, url_535 = engine._extract_pr_info("feat: test", "", ["pr535"], [])
    assert num_535 == 535
    assert status_535 == "Local PR #535"
    assert url_535 is None, f"Expected None pr_url for uncreated PR 535, got {url_535}"

    # 4. get_branch_url for local pr535 falls back to tree URL instead of 404 PR URL
    branch_url_535 = engine.get_branch_url("pr535")
    assert branch_url_535.endswith("/tree/pr535")
    assert "/pull/535" not in branch_url_535


def test_regression_bug_211_code_review_panel_resizing_and_lfs_styling() -> None:
    """Verify BUG-211: FileDiffModel supports is_lfs metadata field."""
    diff_model = FileDiffModel(file_path="attachments/screenshot.png", is_lfs=True)
    assert diff_model.is_lfs is True


def test_regression_bug_213_ancestor_top_marker_merged_pruning_and_rebase(tmp_path: Path) -> None:
    """Verify BUG-213: Smartlog identifies ancestor top, prunes older merged commits, and rebase updates ancestor."""
    # 1. Setup repository with main and feature branch
    repo_dir = tmp_path / "bug213_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Engineer"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_dir, check=True, capture_output=True)

    # Commit 1 on main
    f1 = repo_dir / "f1.txt"
    f1.write_text("commit 1", encoding="utf-8")
    subprocess.run(["git", "add", "f1.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Commit 1 (old merged)"], cwd=repo_dir, check=True, capture_output=True)

    # Commit 2 on main (divergence point)
    f2 = repo_dir / "f2.txt"
    f2.write_text("commit 2", encoding="utf-8")
    subprocess.run(["git", "add", "f2.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Commit 2 (ancestor top)"], cwd=repo_dir, check=True, capture_output=True)
    sha_c2 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    # Create feature branch
    subprocess.run(["git", "checkout", "-b", "feature-x"], cwd=repo_dir, check=True, capture_output=True)

    # Commit 3 on feature
    f3 = repo_dir / "f3.txt"
    f3.write_text("commit 3", encoding="utf-8")
    subprocess.run(["git", "add", "f3.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Commit 3 (feature work)"], cwd=repo_dir, check=True, capture_output=True)

    # Commit 4 on feature
    f4 = repo_dir / "f4.txt"
    f4.write_text("commit 4", encoding="utf-8")
    subprocess.run(["git", "add", "f4.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Commit 4 (feature done)"], cwd=repo_dir, check=True, capture_output=True)

    # Advance main with Commit 5 while on feature
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True, capture_output=True)
    f5 = repo_dir / "f5.txt"
    f5.write_text("commit 5", encoding="utf-8")
    subprocess.run(["git", "add", "f5.txt"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Commit 5 (mainline advance)"], cwd=repo_dir, check=True, capture_output=True
    )
    sha_c5 = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout.strip()

    # Switch back to feature
    subprocess.run(["git", "checkout", "feature-x"], cwd=repo_dir, check=True, capture_output=True)

    engine = GitEngine(repo_root=repo_dir)

    # 2. Verify get_smartlog_dag shows feature commits down to merge-base (Commit 2) and PRUNES Commit 1
    dag = engine.get_smartlog_dag(branch="HEAD")
    hashes = [n.commit_hash for n in dag]
    assert sha_c2 in hashes, "Ancestor merge-base commit 2 must be present in DAG"
    ancestor_node = next(n for n in dag if n.commit_hash == sha_c2)
    assert ancestor_node.is_ancestor_top is True
    assert ancestor_node.ancestor_name == "main"

    # Commit 1 must be pruned because it was already merged prior to the ancestor top
    assert len(dag) == 3, f"Expected 3 commits (Commit 4, Commit 3, Commit 2), got {len(dag)}"

    # 3. Test rebase_branch onto main
    rebase_res = engine.rebase_branch("main")
    assert rebase_res["status"] == "ok"

    # 4. Verify after rebase, ancestor top marker is updated to Commit 5
    dag_after = engine.get_smartlog_dag(branch="HEAD")
    hashes_after = [n.commit_hash for n in dag_after]
    assert sha_c5 in hashes_after, "New ancestor commit 5 must be present in DAG after rebase"
    ancestor_node_after = next(n for n in dag_after if n.commit_hash == sha_c5)
    assert ancestor_node_after.is_ancestor_top is True
    assert ancestor_node_after.ancestor_name == "main"
    assert sha_c2 not in hashes_after, "Old ancestor commit 2 must now be pruned after rebase"
    assert len(dag_after) == 3, (
        f"Expected 3 commits after rebase (rebased 4, rebased 3, and ancestor 5), got {len(dag_after)}"
    )


def test_regression_bug_216_save_and_exit_preserves_resolved_bugs(tmp_path: Path) -> None:
    """Verify BUG-216 regression: Save and Exit in DashboardServer preserves resolved bugs.

    Ensures:
    1. /api/next_bug_id returns {"next_id": ...} matching frontend expectations.
    2. /api/version returns an integer version counter.
    3. File watcher in embedded BugReportServer detects external bug resolutions.
    4. Calling /api/exit or POSTing stale OPEN status without notes does not regress resolved bugs.
    """
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    fb_dir = repo_dir / "feedback"
    fb_dir.mkdir(parents=True, exist_ok=True)

    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    base_url = f"http://127.0.0.1:{server.actual_port}"

    try:
        # 1. Verify /api/next_bug_id has "next_id"
        with urllib.request.urlopen(f"{base_url}/api/next_bug_id") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert "next_id" in data
            assert data["next_id"].startswith("BUG-")

        # 2. Verify /api/version returns integer version
        with urllib.request.urlopen(f"{base_url}/api/version") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert "version" in data
            assert isinstance(data["version"], int)

        # 3. Create BUG-001 on disk as RESOLVED with notes
        bug_file = fb_dir / "BUG_001.md"
        bug_file.write_text(
            "# 🟢 `[BUG-001]` Power Rail Ripple\n\n"
            "- **UUID**: `11111111-2222-3333-4444-555555555555`\n"
            "- **ID**: `BUG-001`\n"
            "- **Status**: `RESOLVED`\n"
            "- **Severity**: `HIGH`\n"
            "- **Category**: `PCB`\n\n"
            "#### Description\n\nRipple on 3V3 rail.\n\n"
            "#### Resolution Notes\n\nAdded decoupling capacitor C12.\n",
            encoding="utf-8",
        )

        # 4. Trigger file watch check / sync
        assert server.bug_server.check_file_watch() is True
        bug_in_db = server.bug_server.database.get_bug("BUG-001")
        assert bug_in_db is not None
        assert bug_in_db.status.value == "RESOLVED"
        assert bug_in_db.resolution_notes == "Added decoupling capacitor C12."

        # 5. POST to /api/bugs with stale OPEN status and no resolution notes (simulating unrefreshed UI form submission)
        req_stale = urllib.request.Request(
            f"{base_url}/api/bugs",
            data=json.dumps(
                {
                    "id": "BUG-001",
                    "title": "Power Rail Ripple",
                    "status": "OPEN",
                    "severity": "HIGH",
                    "category": "PCB",
                    "description": "Ripple on 3V3 rail.",
                    "resolution_notes": "",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_stale) as resp:
            saved_resp = json.loads(resp.read().decode("utf-8"))
            assert saved_resp["status"] == "RESOLVED"  # Protected from regressing!

        # 6. POST to /api/exit
        req_exit = urllib.request.Request(
            f"{base_url}/api/exit",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_exit) as resp:
            exit_data = json.loads(resp.read().decode("utf-8"))
            assert exit_data["status"] == "saved_and_exited"

        # 7. Verify BUG_001.md on disk remained RESOLVED
        disk_content = bug_file.read_text(encoding="utf-8")
        assert "- **Status**: `RESOLVED`" in disk_content
        assert "Added decoupling capacitor C12." in disk_content

    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_218_pr_creation_points_at_and_merged_commits_hidden(tmp_path: Path) -> None:
    """Verify BUG-218: PR detection uses --points-at instead of --contains and merged commits are detected."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    # Initial repo has main at shas[2]
    # Create topic branch with 2 commits
    run_git_command(["checkout", "-b", "feature/my-work"], cwd=repo_dir)
    f3 = repo_dir / "file3.txt"
    f3.write_text("commit a\n", encoding="utf-8")
    run_git_command(["add", "file3.txt"], cwd=repo_dir)
    run_git_command(["commit", "-m", "feature commit A"], cwd=repo_dir)
    sha_a = run_git_command(["rev-parse", "HEAD"], cwd=repo_dir).strip()

    f3.write_text("commit b\n", encoding="utf-8")
    run_git_command(["add", "file3.txt"], cwd=repo_dir)
    run_git_command(["commit", "-m", "feature commit B"], cwd=repo_dir)
    sha_b = run_git_command(["rev-parse", "HEAD"], cwd=repo_dir).strip()

    # Create a pr branch pointing at sha_b
    run_git_command(["branch", "pr123", sha_b], cwd=repo_dir)

    # Query smartlog DAG
    nodes = engine.get_smartlog_dag(limit=20)
    node_by_sha = {n.commit_hash: n for n in nodes}

    # Verify sha_a and sha_b are present
    assert sha_a in node_by_sha
    assert sha_b in node_by_sha

    # Verify commits on main (e.g. shas[2]) are marked merged
    if shas[2] in node_by_sha:
        assert node_by_sha[shas[2]].is_merged_into_tracking is True

    # Commit sha_a has no branch pointing directly to it, but pr123 contains sha_a.
    # With --points-at, sha_a should NOT be flagged as already having PR #123!
    assert node_by_sha[sha_a].pr_number is None
    assert node_by_sha[sha_b].pr_number == 123


def test_regression_bug_221_branches_missing_from_branch_viewer(tmp_path: Path) -> None:
    """Verify BUG-221: main branch and release branches v1..v3 appear cleanly in GitEngine.get_branches."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    # Tag 'main' commit as 'main' (creates ref collision: refs/tags/main vs refs/heads/main)
    run_git_command(["tag", "main", "HEAD"], cwd=repo_dir)

    # Create release branches v1, v2, v3
    run_git_command(["branch", "v1", "HEAD"], cwd=repo_dir)
    run_git_command(["branch", "v2", "HEAD"], cwd=repo_dir)
    run_git_command(["branch", "v3", "HEAD"], cwd=repo_dir)

    branches = engine.get_branches()
    branch_map = {b.name: b for b in branches}

    # Verify 'main' is parsed cleanly as 'main' rather than 'heads/main'
    assert "main" in branch_map, f"Branch list must contain 'main', found: {list(branch_map.keys())}"
    assert "heads/main" not in branch_map, "Branch list must not expose raw 'heads/main'"

    # Verify release branches v1, v2, v3 exist
    for v in ["v1", "v2", "v3"]:
        assert v in branch_map, f"Branch list must contain release branch '{v}'"

    # Verify checkout of 'main' succeeds
    assert engine.checkout_branch("main") is True
    assert engine.get_current_branch() == "main"


def test_regression_bug_223_dashboard_comment_response_and_error_handling(tmp_path: Path) -> None:
    """Verify BUG-223: DashboardServer /api/comment returns status ok and id to prevent undefined errors."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        port = server.server_address[1]
        base_url = f"http://127.0.0.1:{port}"

        # 1. Add comment via POST /api/comment
        payload = {
            "commit_hash": shas[2],
            "file_path": "file1.txt",
            "start_line": 2,
            "end_line": 2,
            "body": "Need verification of this change",
            "severity": "proposal",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/comment",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res.get("status") == "ok", f"Response must include status 'ok', got: {res}"
            assert "comment" in res
            assert "id" in res or "id" in res["comment"]
            comment_id = res["comment"]["id"] if "comment" in res else res["id"]

        # 2. Edit comment via POST /api/comment
        edit_payload = {
            "id": comment_id,
            "body": "Updated comment body",
            "severity": "nitpick",
        }
        req_edit = urllib.request.Request(
            f"{base_url}/api/comment",
            data=json.dumps(edit_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_edit) as resp:
            assert resp.status == 200
            res_edit = json.loads(resp.read().decode("utf-8"))
            assert res_edit.get("status") == "ok"
            assert res_edit["comment"]["body"] == "Updated comment body"

        # 3. Invalid payload returns 400 with descriptive error
        invalid_payload = {"body": "Missing file_path and commit"}
        req_inv = urllib.request.Request(
            f"{base_url}/api/comment",
            data=json.dumps(invalid_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_inv)
        assert exc_info.value.code == 400
        err_res = json.loads(exc_info.value.read().decode("utf-8"))
        assert err_res.get("status") == "error"
        assert "error" in err_res or "message" in err_res
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_226_merged_commits_marked_in_smartlog(tmp_path: Path) -> None:
    """Verify BUG-226: commits merged into tracking branch or ancestor are marked as merged in smartlog.

    Asserts that:
    1. A topic branch diverging from main correctly marks ancestor commits as merged.
    2. When commits are present in main/tracking candidates, is_merged is True.
    3. get_smartlog_dag identifies is_topic_branch and prunes merged ancestor history.
    """
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    # Create feature branch 'feat/new-sensor'
    run_git_command(["checkout", "-b", "feat/new-sensor"], cwd=repo_dir)
    f_feat = repo_dir / "sensor.txt"
    f_feat.write_text("sensor line 1\n", encoding="utf-8")
    run_git_command(["add", "sensor.txt"], cwd=repo_dir)
    run_git_command(["commit", "-m", "Add sensor driver"], cwd=repo_dir)
    feat_sha = run_git_command(["rev-parse", "HEAD"], cwd=repo_dir).strip()

    # Query smartlog DAG on feature branch
    nodes = engine.get_smartlog_dag(limit=20)
    node_map = {n.commit_hash: n for n in nodes}

    assert feat_sha in node_map
    assert node_map[feat_sha].is_merged is False, "Feature commit must not be marked merged initially"

    # Merge base (shas[2]) must be marked merged and is_ancestor_top must be True
    assert shas[2] in node_map
    assert node_map[shas[2]].is_ancestor_top is True
    assert node_map[shas[2]].is_merged is True, "Merge base must be marked merged"
    assert node_map[shas[2]].is_merged_into_tracking is True

    # Now merge feat/new-sensor into main
    run_git_command(["checkout", "main"], cwd=repo_dir)
    run_git_command(["merge", "--ff-only", "feat/new-sensor"], cwd=repo_dir)

    # Check out feature branch again: feat_sha is now merged into main!
    run_git_command(["checkout", "feat/new-sensor"], cwd=repo_dir)
    nodes_merged = engine.get_smartlog_dag(limit=20)
    node_merged_map = {n.commit_hash: n for n in nodes_merged}

    assert feat_sha in node_merged_map
    assert node_merged_map[feat_sha].is_merged is True, "Commit merged into main must have is_merged=True (BUG-226)"
    assert node_merged_map[feat_sha].is_merged_into_tracking is True


def test_cr_feedback_release_branch_candidate_and_dynamic_repo_name(tmp_path: Path) -> None:
    """Verify CR comments: is_release_branch_candidate model property and dynamic repo URLs."""
    from model.vcs import BranchInfoModel, DiffViewSessionModel

    # 1. BranchInfoModel.is_release_branch_candidate property
    b_main = BranchInfoModel(name="main", is_current=True)
    assert b_main.is_release_branch_candidate is True

    b_master = BranchInfoModel(name="master")
    assert b_master.is_release_branch_candidate is True

    b_v1 = BranchInfoModel(name="v1.0")
    assert b_v1.is_release_branch_candidate is True

    b_release = BranchInfoModel(name="release-2026")
    assert b_release.is_release_branch_candidate is True

    b_feat = BranchInfoModel(name="feature/touch-sensor")
    assert b_feat.is_release_branch_candidate is False

    b_bug = BranchInfoModel(name="fix/bug-223")
    assert b_bug.is_release_branch_candidate is False

    # 2. DiffViewSessionModel dynamic repo fields
    session = DiffViewSessionModel(
        repo_name="firmware",
        repo_web_url="https://github.com/myorg/firmware",
        github_repo="myorg/firmware",
    )
    assert session.repo_name == "firmware"
    assert session.repo_web_url == "https://github.com/myorg/firmware"
    assert session.github_repo == "myorg/firmware"


def test_regression_bug_229_pr_submit_interactive_modal_and_github_submission(tmp_path: Path) -> None:
    """Verify BUG-229: GitEngine.submit_prs and DashboardServer /api/pr/submit return execution logs."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    res = engine.submit_prs()
    assert res["status"] == "ok"
    assert len(res["logs"]) > 0

    # 4. Test DashboardServer endpoint handles /api/pr/submit with logs
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        req = urllib.request.Request(
            f"{base_url}/api/pr/submit",
            data=json.dumps({"commits": [shas[2]]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert isinstance(data["created"], list)
            assert "logs" in data
            assert len(data["logs"]) > 0
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_230_execution_logs_and_tracebacks_preserved(tmp_path: Path) -> None:
    """Verify BUG-230: Execution logs, tracebacks, expected and actual behavior are preserved on save."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        test_logs = "Traceback (most recent call last):\n  File 'test.py', line 10\nZeroDivisionError: division by zero"

        # 1. Create bug with execution logs
        payload = {
            "title": "Test Bug Logs",
            "category": "PCB",
            "severity": "HIGH",
            "status": "OPEN",
            "description": "Failure during flying probe testing",
            "logs": test_logs,
            "expected_behavior": "Should pass cleanly",
            "actual_behavior": "Fails with division by zero",
        }
        req = urllib.request.Request(
            f"{base_url}/api/bugs",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            bug_id = res["id"]
            assert res["logs"] == test_logs
            assert res["expected_behavior"] == "Should pass cleanly"
            assert res["actual_behavior"] == "Fails with division by zero"

        # 2. Update bug with new logs and verify preservation
        updated_logs = test_logs + "\nAdditional log line from subsequent run."
        payload_update = {
            "id": bug_id,
            "title": "Test Bug Logs",
            "status": "OPEN",
            "logs": updated_logs,
        }
        req_update = urllib.request.Request(
            f"{base_url}/api/bugs",
            data=json.dumps(payload_update).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_update) as resp:
            assert resp.status == 200
            res_update = json.loads(resp.read().decode("utf-8"))
            assert res_update["logs"] == updated_logs

        # 3. Verify server database persists logs
        db_bug = server.bug_server.database.get_bug(bug_id)
        assert db_bug is not None
        assert db_bug.logs == updated_logs
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_234_pr_submit_no_git_sl_error(tmp_path: Path):
    """Verify BUG-234: GitEngine.submit_prs never runs git with sl binary."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    res = engine.submit_prs()
    assert res["status"] == "ok"

    for line in res["logs"]:
        assert "is not a git command" not in line.lower(), f"Confusing git error in logs: {line}"
        assert "error running git" not in line.lower(), f"Confusing git error in logs: {line}"


def test_regression_bug_235_favicon_web_icon(tmp_path: Path):
    """Verify BUG-235: favicon.ico and /static/favicon.svg are served across DashboardServer."""
    static_favicon = Path(__file__).parent.parent / "provider" / "code_review" / "static" / "favicon.svg"
    assert static_favicon.exists(), "static/favicon.svg must exist"

    repo_dir, _ = create_isolated_git_repo(tmp_path)
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        with urllib.request.urlopen(f"{base_url}/favicon.ico") as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert (
                "image/x-icon" in content_type
                or "image/svg+xml" in content_type
                or "vnd.microsoft.icon" in content_type
            )
            assert len(resp.read()) > 0

        with urllib.request.urlopen(f"{base_url}/static/favicon.svg") as resp:
            assert resp.status == 200
            assert "image/svg+xml" in resp.headers.get("Content-Type")
            assert len(resp.read()) > 0
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_236_cr_count_persistence_and_file_watch(tmp_path: Path) -> None:
    """Verify BUG-236: ReviewServer syncs external CR markdown files and updates smartlog counts."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)
    feedback_dir = repo_dir / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    cr_sha = shas[0]
    cr_md = feedback_dir / f"CR_{cr_sha}.md"
    cr_content = f"""# Code Review Report: Code Review: hardware

## Review Overview

| Metric | Details |
| :--- | :--- |
| **Revisions** | `{cr_sha}` |
| **Overall Verdict** | **`CHANGES_REQUESTED`** |

## File-by-File Review Findings

### [`file1.txt`](file://{repo_dir}/file1.txt)

#### **[MUST FIX]** [file1.txt:L1](file://{repo_dir}/file1.txt#L1)
<!-- comment-uuid: 11111111-2222-3333-4444-555555555555 -->
<!-- comment-commit: {cr_sha} -->

> **Reviewer**: fix this

## Action Items Checklist

- [ ] **[MUST FIX]** [`file1.txt:L1`](file://{repo_dir}/file1.txt#L1): fix this <!-- uuid:11111111-2222-3333-4444-555555555555 -->
"""
    cr_md.write_text(cr_content, encoding="utf-8")

    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=False,
    )
    session = server.build_session()
    # Check that the smartlog node received cr_total_count >= 1
    node = next(n for n in session.smartlog_nodes if n.commit_hash == cr_sha)
    assert node.cr_total_count >= 1


def test_regression_bug_238_auto_rename_cr_working(tmp_path: Path) -> None:
    """Verify BUG-238: Git commit automatically renames CR_working.md to CR_<commit_sha>.md."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)
    feedback_dir = repo_dir / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    cr_working = feedback_dir / "CR_working.md"
    cr_working.write_text(
        """# Code Review Report: Code Review: hardware

## Review Overview

| Metric | Details |
| :--- | :--- |
| **Revisions** | `working` |
| **Overall Verdict** | **`APPROVED`** |

## Action Items Checklist

- [ ] **[NIT]** [`test.txt:L1`](test.txt#L1): note <!-- uuid:aaaa0000-bbbb-cccc-dddd-eeee11112222 -->
""",
        encoding="utf-8",
    )

    # Modify a file and commit
    test_file = repo_dir / "test.txt"
    test_file.write_text("commit changes", encoding="utf-8")
    new_sha = engine.commit_files("Auto rename test commit", file_paths=["test.txt"])

    assert not cr_working.exists(), "CR_working.md should be renamed upon commit"
    expected_cr = feedback_dir / f"CR_{new_sha}.md"
    assert expected_cr.exists(), f"CR_{new_sha}.md should exist after commit"
    assert new_sha in expected_cr.read_text(encoding="utf-8")


def test_regression_bug_239_per_user_filtering(tmp_path: Path) -> None:
    """Verify BUG-239: Per-user author queries and CLI filtering options."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    user = engine.get_current_user()
    assert "name" in user and "email" in user
    assert len(user["name"]) > 0

    # Uncommitted modified file attributes to current user
    test_file = repo_dir / "file1.txt"
    test_file.write_text("modified", encoding="utf-8")
    author = engine.get_file_author(test_file)
    assert author["name"] == user["name"]

    # Arguments parse per-user flags
    parsed_reviews = parse_arguments(["list-reviews", "--all-users"])
    assert parsed_reviews.all_users is True
    parsed_bugs = parse_arguments(["list-bugs", "--user", "Alice"])
    assert parsed_bugs.user == "Alice"


def test_regression_bug_240_action_topic_subcommands() -> None:
    """Verify BUG-240: CLI supports action-topic subcommands with backward compatibility for flags."""
    # Subcommands
    args_rev = parse_arguments(["list-reviews", "--open"])
    assert args_rev.subcommand == "list-reviews"
    assert args_rev.open is True

    args_bugs = parse_arguments(["list-bugs", "--open", "--severity", "HIGH"])
    assert args_bugs.subcommand == "list-bugs"
    assert args_bugs.open is True
    assert args_bugs.severity == "HIGH"

    args_res_c = parse_arguments(["resolve-comment", "c_12345"])
    assert args_res_c.subcommand == "resolve-comment"
    assert args_res_c.id == "c_12345"

    args_res_b = parse_arguments(["resolve-bug", "BUG-999", "--notes", "Fixed properly"])
    assert args_res_b.subcommand == "resolve-bug"
    assert args_res_b.id == "BUG-999"
    assert args_res_b.notes == "Fixed properly"

    # Backward compatibility flags
    args_flag_b = parse_arguments(["--bugs", "--open"])
    assert args_flag_b.bugs is True
    assert args_flag_b.open is True

    args_flag_r = parse_arguments(["--reviews", "--all"])
    assert args_flag_r.reviews is True
    assert args_flag_r.all_users is True


def test_regression_bug_244_commit_subcommand_cli_parsing() -> None:
    """Verify BUG-244: dashboard CLI argument parsing supports commit subcommand and --commit flag."""
    # Commit with -m flag
    args_m = parse_arguments(["commit", "-m", "Test commit message"])
    assert args_m.subcommand == "commit"
    assert args_m.commit_message == "Test commit message"
    assert args_m.amend is False

    # Commit with positional message and files
    args_pos = parse_arguments(["commit", "Positional message", "file1.txt", "file2.txt"])
    assert args_pos.subcommand == "commit"
    assert args_pos.args == ["Positional message", "file1.txt", "file2.txt"]

    # Commit with --files and -a
    args_files = parse_arguments(["commit", "-m", "Selective", "--files", "a.py", "b.py", "-a"])
    assert args_files.subcommand == "commit"
    assert args_files.commit_message == "Selective"
    assert args_files.flag_files == ["a.py", "b.py"]
    assert args_files.all_files is True

    # Commit amend
    args_amend = parse_arguments(["commit", "--amend"])
    assert args_amend.subcommand == "commit"
    assert args_amend.amend is True

    # Top-level --commit flag
    args_top = parse_arguments(["--commit", "Top level message"])
    assert args_top.commit == "Top level message"


def test_regression_bug_244_commit_subcommand_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify BUG-244: dashboard commit subcommand commits untracked and staged changes in repository."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    monkeypatch.chdir(repo_dir)

    engine = GitEngine(repo_root=repo_dir)

    # 1. Selective commit of untracked file via CLI args
    f_untracked = repo_dir / "untracked.txt"
    f_untracked.write_text("untracked content\n", encoding="utf-8")
    f_other = repo_dir / "other.txt"
    f_other.write_text("other content\n", encoding="utf-8")

    main(["commit", "-m", "Commit untracked selectively", "untracked.txt"])
    assert engine.get_head_commit_message() == "Commit untracked selectively"

    working_files = engine.get_working_tree_files()
    working_paths = [f.path for f in working_files]
    assert "untracked.txt" not in working_paths
    assert "other.txt" in working_paths

    # 2. Commit all remaining changes without explicit file arguments
    main(["commit", "Commit remaining files without flag"])
    assert engine.get_head_commit_message() == "Commit remaining files without flag"
    assert len(engine.get_working_tree_files()) == 0

    # 3. Amend last commit via CLI
    main(["commit", "--amend", "-m", "Amended via CLI (BUG-244)"])
    assert engine.get_head_commit_message() == "Amended via CLI (BUG-244)"

    # 4. Commit via top-level --commit flag
    f_top = repo_dir / "top_level.txt"
    f_top.write_text("top level flag content\n", encoding="utf-8")
    main(["--commit", "Commit via top-level flag"])
    assert engine.get_head_commit_message() == "Commit via top-level flag"
    assert len(engine.get_working_tree_files()) == 0


def test_regression_bug_247_server_api_sync_unification(tmp_path: Path) -> None:
    """Verify BUG-247: /api/sync executes both git repository fetch and feedback/bug database synchronization."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        url = f"{server.get_url()}/api/sync"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert "feedback" in data
            assert data["feedback"]["status"] == "ok"
            assert data["feedback"]["initial_sync_done"] is True
    finally:
        server.server_close()


def test_regression_bug_269_dashboard_scoped_attachments(tmp_path: Path) -> None:
    """Verify BUG-269: DashboardServer correctly handles bug-scoped attachments with identical filenames."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        base_url = server.get_url()

        # 1. Upload daemon.log for BUG-268
        p1 = json.dumps(
            {
                "bug_id": "BUG-268",
                "filename": "daemon.log",
                "content_text": "log for 268 in dashboard",
                "description": "268 log",
            }
        ).encode("utf-8")
        req1 = urllib.request.Request(
            f"{base_url}/api/upload",
            data=p1,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req1) as resp:
            assert resp.status == 200
            res1 = json.loads(resp.read().decode("utf-8"))
            assert res1["filename"] == "daemon.log"
            assert res1["file_path"] == "attachments/BUG-268/daemon.log"

        # 2. Upload daemon.log for BUG-269
        p2 = json.dumps(
            {
                "bug_id": "BUG-269",
                "filename": "daemon.log",
                "content_text": "log for 269 in dashboard",
                "description": "269 log",
            }
        ).encode("utf-8")
        req2 = urllib.request.Request(
            f"{base_url}/api/upload",
            data=p2,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req2) as resp:
            assert resp.status == 200
            res2 = json.loads(resp.read().decode("utf-8"))
            assert res2["filename"] == "daemon.log"
            assert res2["file_path"] == "attachments/BUG-269/daemon.log"

        # 3. Verify neither file overwrote the other and both are independently served
        f268 = repo_dir / "attachments" / "BUG-268" / "daemon.log"
        f269 = repo_dir / "attachments" / "BUG-269" / "daemon.log"
        assert f268.exists()
        assert f269.exists()
        assert f268.read_text(encoding="utf-8") == "log for 268 in dashboard"
        assert f269.read_text(encoding="utf-8") == "log for 269 in dashboard"

        with urllib.request.urlopen(f"{base_url}/attachments/BUG-268/daemon.log") as resp:
            assert resp.status == 200
            assert resp.read() == b"log for 268 in dashboard"

        with urllib.request.urlopen(f"{base_url}/attachments/BUG-269/daemon.log") as resp:
            assert resp.status == 200
            assert resp.read() == b"log for 269 in dashboard"
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_270_dashboard_server_handles_broken_pipe_gracefully(capsys):
    """Verify BUG-270: BrokenPipeError and client disconnects are handled cleanly without printing tracebacks."""
    server = DashboardServer.__new__(DashboardServer)

    # 1. Verify BrokenPipeError in handle_error does not print traceback to stderr
    try:
        raise BrokenPipeError(32, "Broken pipe")
    except BrokenPipeError:
        server.handle_error(None, ("127.0.0.1", 58468))

    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "BrokenPipeError" not in captured.err

    # 2. Verify unexpected errors are still reported to super().handle_error
    try:
        raise RuntimeError("Real unexpected server failure")
    except RuntimeError:
        server.handle_error(None, ("127.0.0.1", 58468))

    captured = capsys.readouterr()
    assert "Real unexpected server failure" in captured.err

    # 3. Verify handler _send_json and _send_html gracefully handle BrokenPipeError
    handler = DashboardRequestHandler.__new__(DashboardRequestHandler)
    mock_wfile = MagicMock()
    mock_wfile.write.side_effect = BrokenPipeError(32, "Broken pipe")
    handler.wfile = mock_wfile
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.close_connection = False

    # Should not raise exception, and should set close_connection = True
    handler._send_json({"status": "ok"})
    assert handler.close_connection is True

    handler.close_connection = False
    handler._send_html("<html><body>test</body></html>")
    assert handler.close_connection is True


def test_regression_bug_273_dashboard_fd_limit_and_stability(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify BUG-273: Dashboard elevates soft FD limit, caches commit diffs, and absorbs EMFILE cleanly."""
    import errno
    import resource
    from provider.dashboard.server import ensure_high_fd_limit

    # 1. Verify ensure_high_fd_limit raises soft limit when constrained
    orig_soft, orig_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    try:
        # Simulate lower soft limit (e.g., 256 default on macOS)
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, orig_hard))
        new_soft = ensure_high_fd_limit(min_limit=10240)
        curr_soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        assert curr_soft >= 10240 or curr_soft == orig_hard
        assert new_soft == curr_soft
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (orig_soft, orig_hard))

    # 2. Verify GitEngine commit diff caching prevents redundant subprocess spawns
    repo_dir, commit_shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)
    assert hasattr(engine, "_commit_diff_cache")

    c1 = commit_shas[0]
    res1 = engine._get_commit_diff_summary(c1)
    assert c1 in engine._commit_diff_cache
    assert engine._commit_diff_cache[c1] == res1

    # Second call returns cached result directly
    res2 = engine._get_commit_diff_summary(c1)
    assert res2 == res1

    # 3. Verify EMFILE (Errno 24 Too many open files) in handle_error does not dump traceback
    server = DashboardServer.__new__(DashboardServer)
    emfile_err = OSError(errno.EMFILE, "Too many open files")
    try:
        raise emfile_err
    except OSError:
        server.handle_error(None, ("127.0.0.1", 56253))

    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Too many open files" not in captured.err


def test_regression_worm_014_nonexistent_bugs_not_tagged_as_open(tmp_path: Path) -> None:
    """Verify WORM-014: Non-existent bug IDs are not assigned phantom OPEN tags."""
    repo = tmp_path / "repo"
    repo.mkdir()
    build_dir = repo / "build"
    build_dir.mkdir()

    # Create build/bugs.sqlite with only BUG-274 marked RESOLVED
    bugs_db = build_dir / "bugs.sqlite"
    conn = sqlite3.connect(str(bugs_db))
    conn.execute(
        "CREATE TABLE bugs (id TEXT PRIMARY KEY, title TEXT, status TEXT, severity TEXT, category TEXT, description TEXT)"
    )
    conn.execute(
        "INSERT INTO bugs (id, title, status, severity, category, description) "
        "VALUES ('BUG-274', 'Make code review modal', 'RESOLVED', 'MEDIUM', 'UI', 'Desc')"
    )
    conn.commit()
    conn.close()

    engine = GitEngine(repo_root=repo)

    # 1. Commit mentioning non-existent bug BUG-999
    tags_999 = engine._extract_bug_tags("feat(dashboard): dummy test commit (BUG-999)")
    assert len(tags_999) == 0, f"Expected no tags for non-existent BUG-999, but got: {tags_999}"

    # 2. Commit mentioning BUG-274 and non-existent WORM-999
    tags_mixed = engine._extract_bug_tags("fix(dashboard): resolve modal issue (BUG-274 / WORM-999)")
    assert len(tags_mixed) == 1, f"Expected exactly 1 tag (BUG-274), but got: {tags_mixed}"
    assert tags_mixed[0].id == "BUG-274"
    assert tags_mixed[0].status == "RESOLVED"
    assert not any(t.id == "WORM-999" or t.id == "BUG-999" for t in tags_mixed)


def test_regression_worm_014_repo_smartlog_no_ghost_bugs() -> None:
    """Verify WORM-014: The repository's smartlog does not display ghost bug tags."""
    workspace_root = Path(__file__).resolve().parent.parent
    engine = GitEngine(repo_root=workspace_root)
    nodes = engine.get_smartlog_dag()

    # Load valid bug IDs from DB and feedback files
    valid_ids = set()
    sqlite_path = workspace_root / "build" / "bugs.sqlite"
    if sqlite_path.exists():
        try:
            conn = sqlite3.connect(str(sqlite_path))
            for row in conn.execute("SELECT id FROM bugs"):
                valid_ids.add(row[0].upper().replace("_", "-"))
            conn.close()
        except Exception:
            pass
    feedback_dir = workspace_root / "feedback"
    if feedback_dir.exists():
        for p in feedback_dir.glob("BUG_*.md"):
            clean = p.stem.replace("BUG_", "")
            valid_ids.add(f"BUG-{clean}".upper())
            if clean.isdigit():
                valid_ids.add(f"BUG-{int(clean):03d}")

    ghost_tags = []
    for node in nodes:
        for tag in node.bug_tags:
            norm = tag.id.upper().replace("_", "-")
            if norm not in valid_ids and tag.status == "OPEN":
                ghost_tags.append((node.short_hash, tag.id, tag.status))

    assert not ghost_tags, f"Found ghost bug tags in repository smartlog: {ghost_tags}"


def test_regression_worm_015_workstation_modal_dom_hierarchy_and_rendering() -> None:
    """Verify WORM-015: workstationModal is NOT nested inside modalBranchPicker or hidden modals."""
    from bs4 import BeautifulSoup
    from html.parser import HTMLParser
    import jinja2
    from model.vcs import BranchInfoModel, DiffViewSessionModel

    tpl_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(tpl_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    template = env.get_template("diff_view.html.j2")

    dummy_session = DiffViewSessionModel(
        title="VCS Dashboard",
        current_user="testuser",
        active_commit="working",
        branches=[
            BranchInfoModel(name="main", is_current=True, is_remote=False),
        ],
        smartlog_tree=[],
        working_files=[],
        selected_commits=[],
    )
    rendered_html = template.render(
        session=dummy_session,
        active_branch="main",
        active_commit="working",
    )

    soup = BeautifulSoup(rendered_html, "html.parser")

    # 1. workstationModal must exist
    workstation_modal = soup.find(id="workstationModal")
    assert workstation_modal is not None, "workstationModal not found in rendered diff_view"

    # 2. modalBranchPicker must exist
    branch_modal = soup.find(id="modalBranchPicker")
    assert branch_modal is not None, "modalBranchPicker not found in rendered diff_view"

    # 3. workstationModal must NOT be a child or descendant of modalBranchPicker or any other modal
    assert branch_modal.find(id="workstationModal") is None, (
        "workstationModal is incorrectly nested inside modalBranchPicker, causing it to be hidden by display: none"
    )
    for overlay in soup.find_all(class_="quake-modal-overlay"):
        if overlay.get("id") != "workstationModal":
            assert overlay.find(id="workstationModal") is None, (
                f"workstationModal is incorrectly nested inside {overlay.get('id')}"
            )

    # 4. Check for tag balance (no unclosed div tags leaking through the template)
    class DivBalanceChecker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.div_depth = 0
            self.mismatches = []

        def handle_starttag(self, tag, attrs):
            if tag == "div":
                self.div_depth += 1

        def handle_endtag(self, tag):
            if tag == "div":
                self.div_depth -= 1
                if self.div_depth < 0:
                    self.mismatches.append("Extra closing </div> encountered")

    checker = DivBalanceChecker()
    checker.feed(rendered_html)
    assert checker.div_depth == 0, f"Unbalanced <div> tags in diff_view.html.j2: depth is {checker.div_depth}"
    assert len(checker.mismatches) == 0, f"Encountered div mismatches: {checker.mismatches}"


def test_regression_bug_278_working_tree_actions_visible_on_load() -> None:
    """Verify BUG-278 / WORM-017: Working tree actions are visible on initial load when active_commit is 'working'."""
    import jinja2
    from bs4 import BeautifulSoup

    tpl_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(tpl_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    template = env.get_template("diff_view.html.j2")

    # 1. When active_commit is "working", workingTreeCommitArea must be visible (display: flex)
    session_working = DiffViewSessionModel(
        title="VCS Dashboard",
        current_user="testuser",
        active_commit="working",
        branches=[
            BranchInfoModel(name="main", is_current=True, is_remote=False),
        ],
        smartlog_tree=[],
        working_files=[],
        selected_commits=[],
    )
    html_working = template.render(
        session=session_working,
        active_branch="main",
        active_commit="working",
    )
    soup_working = BeautifulSoup(html_working, "html.parser")
    commit_area_working = soup_working.find(id="workingTreeCommitArea")
    assert commit_area_working is not None, "workingTreeCommitArea element must exist"
    style_working = commit_area_working.get("style", "")
    assert "display: flex" in style_working or "display:flex" in style_working, (
        f"workingTreeCommitArea must have display: flex when active_commit is 'working', but got: '{style_working}'"
    )
    assert "display: none" not in style_working and "display:none" not in style_working, (
        f"workingTreeCommitArea must NOT be hidden when active_commit is 'working', but got: '{style_working}'"
    )

    # 2. When active_commit is a specific commit hash, workingTreeCommitArea must be hidden (display: none)
    session_commit = DiffViewSessionModel(
        title="VCS Dashboard",
        current_user="testuser",
        active_commit="12345678",
        branches=[
            BranchInfoModel(name="main", is_current=True, is_remote=False),
        ],
        smartlog_tree=[],
        working_files=[],
        selected_commits=[],
    )
    html_commit = template.render(
        session=session_commit,
        active_branch="main",
        active_commit="12345678",
    )
    soup_commit = BeautifulSoup(html_commit, "html.parser")
    commit_area_commit = soup_commit.find(id="workingTreeCommitArea")
    assert commit_area_commit is not None, "workingTreeCommitArea element must exist"
    style_commit = commit_area_commit.get("style", "")
    assert "display: none" in style_commit or "display:none" in style_commit, (
        f"workingTreeCommitArea must have display: none when active_commit is a commit hash, but got: '{style_commit}'"
    )


def test_regression_bug_subterranean_vinegarworm_291_dashboard_upload_collision(tmp_path: Path) -> None:
    """Verify BUG-SUBTERRANEAN-VINEGARWORM-291: DashboardServer file upload endpoint assigns unique filenames.

    Ensures that when multiple files or screenshots are uploaded with identical names,
    subsequent uploads do not overwrite earlier files on disk.
    """
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    att_dir = repo_dir / "attachments"
    att_dir.mkdir(parents=True, exist_ok=True)

    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()

        # First upload
        payload1 = {
            "bug_id": "BUG-DASH-291",
            "filename": "image.png",
            "file_type": "screenshot",
            "content_base64": base64.b64encode(b"DASHBOARD_SCREENSHOT_1").decode("utf-8"),
            "description": "First pasted screenshot in dashboard",
        }
        req1 = urllib.request.Request(
            f"{base_url}/api/upload",
            data=json.dumps(payload1).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req1) as resp1:
            assert resp1.status == 200
            res1 = json.loads(resp1.read().decode("utf-8"))

        # Second upload with the same filename image.png
        payload2 = {
            "bug_id": "BUG-DASH-291",
            "filename": "image.png",
            "file_type": "screenshot",
            "content_base64": base64.b64encode(b"DASHBOARD_SCREENSHOT_2").decode("utf-8"),
            "description": "Second pasted screenshot in dashboard",
        }
        req2 = urllib.request.Request(
            f"{base_url}/api/upload",
            data=json.dumps(payload2).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req2) as resp2:
            assert resp2.status == 200
            res2 = json.loads(resp2.read().decode("utf-8"))

        assert res1["filename"] == "image.png"
        assert res2["filename"] == "image_1.png"
        assert res1["file_path"] != res2["file_path"]

        # Check files on disk
        f1 = att_dir / "BUG-DASH-291" / "image.png"
        f2 = att_dir / "BUG-DASH-291" / "image_1.png"
        assert f1.exists()
        assert f2.exists()
        assert f1.read_bytes() == b"DASHBOARD_SCREENSHOT_1"
        assert f2.read_bytes() == b"DASHBOARD_SCREENSHOT_2"
    finally:
        server.shutdown()
        server.server_close()


def test_ensure_feedback_worktree_migration(tmp_path: Path) -> None:
    """Verify ensure_feedback_worktree automatically configures feedback/ worktree and preserves data."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "User"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "user@workspace"], cwd=repo_dir, check=True)
    (repo_dir / ".gitignore").write_text("feedback\nfeedback/\nattachments\nattachments/\n", encoding="utf-8")
    (repo_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)

    # Create bugs branch with legacy nested feedback/ and attachments/
    subprocess.run(["git", "checkout", "--orphan", "bugs"], cwd=repo_dir, check=True)
    subprocess.run(["git", "rm", "-rf", "."], cwd=repo_dir, check=True)
    (repo_dir / "feedback").mkdir()
    (repo_dir / "feedback" / "BUG_001.md").write_text("# Bug 001\n", encoding="utf-8")
    (repo_dir / "attachments" / "BUG-001").mkdir(parents=True)
    (repo_dir / "attachments" / "BUG-001" / "log.txt").write_text("Log data\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial bugs branch"], cwd=repo_dir, check=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo_dir, check=True)

    # Create uncommitted local feedback and attachments on main
    (repo_dir / "feedback").mkdir(exist_ok=True)
    (repo_dir / "feedback" / "BUG_001.md").write_text("# Bug 001 with local edits\n", encoding="utf-8")
    (repo_dir / "feedback" / "BUG_002.md").write_text("# Bug 002 uncommitted\n", encoding="utf-8")
    (repo_dir / "attachments" / "BUG-002").mkdir(parents=True, exist_ok=True)
    (repo_dir / "attachments" / "BUG-002" / "data.txt").write_text("Attachment data\n", encoding="utf-8")

    # Mock provider/bug_report presence so it detects 'bugs'
    (repo_dir / "provider" / "bug_report").mkdir(parents=True)

    engine = GitEngine(repo_root=repo_dir)
    res = engine.ensure_feedback_worktree()
    assert res is True

    # 1. Verify worktree active (.git is a file)
    assert (repo_dir / "feedback" / ".git").is_file()

    # 2. Verify worktree branch is bugs
    wt_branch = subprocess.run(
        ["git", "-C", "feedback", "branch", "--show-current"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert wt_branch == "bugs"

    # 3. Verify local modifications and untracked files are preserved
    assert (repo_dir / "feedback" / "BUG_001.md").read_text(encoding="utf-8") == "# Bug 001 with local edits\n"
    assert (repo_dir / "feedback" / "BUG_002.md").read_text(encoding="utf-8") == "# Bug 002 uncommitted\n"

    # 4. Verify attachments symlink and accessibility
    assert (repo_dir / "attachments").is_symlink()
    assert (repo_dir / "attachments" / "BUG-001" / "log.txt").read_text(encoding="utf-8") == "Log data\n"
    assert (repo_dir / "attachments" / "BUG-002" / "data.txt").read_text(encoding="utf-8") == "Attachment data\n"

    # 5. Verify root repository working tree remains clean on main
    root_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert root_status == ""

    # 6. Verify idempotency
    res_second = engine.ensure_feedback_worktree()
    assert res_second is True


def test_regression_bug_creeping_waterstrider_835_working_cr_committed(tmp_path: Path) -> None:
    """Verify BUG-CREEPING-WATERSTRIDER-835: Working tree CR feedback moves to CR_<sha>.md upon commit."""
    import sqlite3

    repo_dir, _ = create_isolated_git_repo(tmp_path)
    # Modify a file in working tree
    (repo_dir / "file1.txt").write_text("working tree change\n", encoding="utf-8")

    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_dir,
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        port = server.server_address[1]
        base_url = f"http://127.0.0.1:{port}"

        # 1. Add working tree review comment via /api/comment
        payload = {
            "commit_hash": "working",
            "file_path": "file1.txt",
            "start_line": 1,
            "end_line": 1,
            "body": "Fix this working change",
            "severity": "proposal",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/comment",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

        cr_working = repo_dir / "feedback" / "CR_working.md"
        assert cr_working.exists(), "CR_working.md should exist after adding working comment"
        assert "Fix this working change" in cr_working.read_text(encoding="utf-8")

        # 2. Commit working tree changes via /api/commit
        commit_payload = {
            "message": "commit foo",
            "files": ["file1.txt"],
        }
        commit_data = json.dumps(commit_payload).encode("utf-8")
        commit_req = urllib.request.Request(
            f"{base_url}/api/commit",
            data=commit_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(commit_req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            new_sha = res["commit_hash"]

        # 3. Trigger feedback sync (simulating reload / file watch / sync_feedback)
        server.sync_feedback()

        # 4. Verify CR_working.md is gone, and CR_<new_sha>.md exists with feedback
        assert not cr_working.exists(), "CR_working.md should not exist after commit and sync"
        cr_new = repo_dir / "feedback" / f"CR_{new_sha}.md"
        assert cr_new.exists(), f"CR_{new_sha}.md should exist after commit"
        assert "Fix this working change" in cr_new.read_text(encoding="utf-8")

        # 5. Verify SQLite comments table updated commit_hash to new_sha
        sqlite_file = repo_dir / "build" / "code_review.sqlite"
        assert sqlite_file.exists()
        with sqlite3.connect(str(sqlite_file)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT commit_hash FROM comments").fetchall()
            assert len(rows) >= 1
            for row in rows:
                assert row["commit_hash"] == new_sha, (
                    f"Comment commit_hash should be {new_sha}, got {row['commit_hash']}"
                )

        # 6. Verify subsequent session recovery loads comment with new_sha
        recovered_session = server.get_review_session([new_sha])
        assert any(c.commit == new_sha for c in recovered_session.comments)
    finally:
        server.shutdown()
        server.server_close()
