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

from unittest.mock import MagicMock
import pytest

from dashboard import main, parse_arguments, print_cli_smartlog
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
    """Verify BUG-178: standalone bug_report/code_review tools are removed and integrated into dashboard.py."""
    repo_root = get_git_root()

    # 1. Standalone scripts MUST NOT exist
    assert not (repo_root / "src" / "bug_report.py").exists()
    assert not (repo_root / "src" / "code_review.py").exists()
    assert not (repo_root / "src" / "diff_view.py").exists()

    # 2. Unified dashboard script MUST exist
    dashboard_script = repo_root / "src" / "dashboard.py"
    assert dashboard_script.exists()

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
    """Verify BUG-185: commit modal UI, amend button, file selection, and multi-file discard."""
    # 1. Verify template elements
    template_path = Path(__file__).parent.parent / "provider" / "templates" / "diff_view.html.j2"
    assert template_path.exists()
    html_content = template_path.read_text(encoding="utf-8")
    assert 'id="btnCommitModal"' in html_content
    assert 'id="btnAmendModal"' in html_content
    assert 'id="commitModalOverlay"' in html_content
    assert 'id="modalFilesList"' in html_content
    assert 'id="modalCommitMessage"' in html_content
    assert "working-file-cb" in html_content
    assert "discardFromModal" in html_content
    assert "discardSelectedFromModal" in html_content

    # 2. Verify GitEngine commit_files, amend, and discard operations
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
    root_repo = Path(__file__).resolve().parent.parent.parent
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
    """Verify BUG-194: Separate group for LFS tracked files in changed files column with unique color."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_dir)

    # 1. Verify template HTML contains LFS styling, group headers, and badges
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")
    assert ".status-lfs" in tpl_text
    assert ".lfs-file-item" in tpl_text
    assert "📦 LFS Tracked Files" in tpl_text
    assert 'class="file-status-badge status-lfs">LFS</span>' in tpl_text

    # 2. Create LFS tracked file under attachments/ and a regular file
    att_dir = repo_dir / "attachments"
    att_dir.mkdir(parents=True, exist_ok=True)
    lfs_file = att_dir / "diagram.png"
    lfs_file.write_bytes(b"\x89PNG\r\n\x1a\ntestdiagram")

    reg_file = repo_dir / "main.py"
    reg_file.write_text("print('hello')\n", encoding="utf-8")

    # Ensure .gitattributes has LFS pattern
    ga = repo_dir / ".gitattributes"
    ga.write_text("attachments/* filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")

    # 3. Check get_working_tree_files identifies is_lfs
    working = engine.get_working_tree_files()
    lfs_items = [w for w in working if w.is_lfs]
    reg_items = [w for w in working if not w.is_lfs and not w.is_feedback]
    assert any(w.path == "attachments/diagram.png" for w in lfs_items)
    assert any(w.path == "main.py" for w in reg_items)

    # 4. Check get_changed_files identifies is_lfs
    changed = engine.get_changed_files("working", include_feedback=False)
    lfs_changed = [c for c in changed if c.get("is_lfs")]
    reg_changed = [c for c in changed if not c.get("is_lfs")]
    assert any(c["path"] == "attachments/diagram.png" for c in lfs_changed)
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
            assert any(f["path"] == "attachments/diagram.png" for f in lfs_api)
            assert any(f["path"] == "main.py" for f in reg_api)
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_187_collapsible_file_and_commit_panes(tmp_path: Path) -> None:
    """Verify BUG-187: file and commit panes can be collapsed in VCS UI like code_review."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)

    # 1. Verify template contains collapse rules, buttons, and shortcuts
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")

    assert ".pane-smartlog" in tpl_text
    assert ".pane-smartlog.collapsed" in tpl_text
    assert ".pane-files" in tpl_text
    assert ".pane-files.collapsed" in tpl_text
    assert 'id="btnToggleSmartlog"' in tpl_text
    assert 'id="btnToggleFiles"' in tpl_text
    assert "togglePane('smartlog')" in tpl_text
    assert "togglePane('files')" in tpl_text
    assert 'e.key === "["' in tpl_text
    assert 'e.key === "]"' in tpl_text

    # 2. Verify DashboardServer serves HTML with collapsible panes
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
            assert 'id="paneSmartlog"' in html
            assert 'id="paneFiles"' in html
            assert 'id="btnToggleSmartlog"' in html
            assert 'id="btnToggleFiles"' in html
            assert "togglePane" in html
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_188_initial_sqlite_sync_loading_modal(tmp_path: Path) -> None:
    """Verify BUG-188: initial SQLite sync loading screen and feedback synchronization."""
    repo_dir, _ = create_isolated_git_repo(tmp_path)

    # 1. Verify template contains loading modal elements and functions
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")

    assert 'id="syncModalOverlay"' in tpl_text
    assert 'id="syncProgressBar"' in tpl_text
    assert 'id="syncProgressPercent"' in tpl_text
    assert 'id="syncStatusText"' in tpl_text
    assert 'id="btnSync"' in tpl_text
    assert 'id="btnSyncFeedback"' not in tpl_text
    assert "performInitialSync" in tpl_text
    assert "INITIAL_SYNC_DONE" in tpl_text

    # 2. Start server without prior sync
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
    """Verify BUG-190: PR branch tags like origin/pr520 are clickable links that open the PR in GitHub."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    # 1. Create a branch matching PR tag pattern (e.g. pr520 or origin/pr520)
    run_git_command(["branch", "pr520", shas[1]], cwd=repo_dir)

    # 2. Verify template has onBranchBadgeClick and pr-tag-link
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")
    assert "onBranchBadgeClick" in tpl_text
    assert "pr-tag-link" in tpl_text
    assert "/pull/" in tpl_text
    assert "repoBase" in tpl_text or "pull" in tpl_text

    # 3. Serve via DashboardServer and assert HTML contains clickable branch tag
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
            assert "onBranchBadgeClick(event, 'pr520'" in html
            assert "pr-tag-link" in html
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_192_pr_highlight_on_commit_element(tmp_path: Path) -> None:
    """Verify BUG-192: Commit element has distinct PR highlight area with PR number text and color."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    # 1. Create PR branch to associate PR with commit
    run_git_command(["branch", "pr520", shas[1]], cwd=repo_dir)

    # Verify GitEngine detects pr_number and pr_url on the CommitNodeModel
    nodes = engine.get_smartlog_dag(limit=10)
    pr_node = next(n for n in nodes if n.commit_hash == shas[1])
    assert pr_node.pr_number == 520
    assert pr_node.pr_status == "PR #520"
    assert "pull/520" in (pr_node.pr_url or "")

    # 2. Verify template has .pr-highlight-badge, .smartlog-node.has-pr styling
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")
    assert ".pr-highlight-badge" in tpl_text
    assert ".smartlog-node.has-pr" in tpl_text
    assert "#a855f7" in tpl_text  # Distinct PR purple highlight color

    # 3. Serve via DashboardServer and assert HTML contains PR highlight badge and has-pr class
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
            assert "pr-highlight-badge" in html
            assert "PR #520" in html
            assert "has-pr" in html
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_193_create_and_unlink_pr_buttons_and_ancestors(tmp_path: Path) -> None:
    """Verify BUG-193: Create PR and Unlink PR buttons, ancestor preservation, and validation."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    # 1. Verify UI template contains buttons and client handlers
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")
    assert 'id="btnCreatePR"' in tpl_text
    assert 'id="btnUnlinkPR"' in tpl_text
    assert "onCreatePR" in tpl_text
    assert "onUnlinkPR" in tpl_text
    assert "/api/pr/create" in tpl_text
    assert "/api/pr/unlink" in tpl_text

    # 2. Test PR submission via submit_prs()
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
    """Verify BUG-190: PR branch tags in Smartlog render as clickable links to GitHub PR."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    # 1. Test get_branch_url on GitEngine
    pr_branch_url = engine.get_branch_url("origin/pr520")
    assert pr_branch_url.endswith("/pull/520"), f"Expected PR URL for origin/pr520, got {pr_branch_url}"

    norm_branch_url = engine.get_branch_url("origin/feature-xyz")
    assert norm_branch_url.endswith("/tree/feature-xyz"), f"Expected branch tree URL, got {norm_branch_url}"

    # 2. Test branch tag rendered as anchor link in diff_view.html.j2
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")
    assert '<a href="{{ br_url }}"' in tpl_text
    assert "pr-tag-link" in tpl_text
    assert "onBranchBadgeClick" in tpl_text


def test_regression_bug_200_diff_view_single_bottom_scrollbar_and_max_line_length() -> None:
    """Verify BUG-200: diff view has a single bottom scrollbar, no per-line scrollbars, and enforces max line length."""
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_component.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")

    # 1. Verify diff-code-cell does NOT have overflow-x: auto (no per-row scrollbars)
    assert ".diff-code-cell {\n    overflow-x: hidden;" in tpl_text
    assert "overflow-x: auto;\n    font-family: inherit;\n    width: calc(50% - 64px);" not in tpl_text

    # 2. Verify diff-scroll-body provides horizontal scrollbar at bottom
    assert ".diff-scroll-body {\n    flex: 1;\n    overflow-x: auto;\n    overflow-y: auto;" in tpl_text
    assert ".diff-scroll-body::-webkit-scrollbar" in tpl_text

    # 3. Verify maximum line length enforcement
    assert "MAX_LINE_LENGTH:" in tpl_text
    assert "truncateLine(text, maxLen)" in tpl_text
    assert "… [line truncated]" in tpl_text


def test_regression_bug_201_single_diff_viewer_and_bug_tabs_reuse() -> None:
    """Verify BUG-201: Cross-station links reuse named window targets instead of spawning endless tabs."""
    diff_view_tpl = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    diff_text = diff_view_tpl.read_text(encoding="utf-8")

    # Diff View uses named window targets for code review and bug tracker
    assert "_code_review`" in diff_text or "_code_review" in diff_text
    assert "_bug_tracker`" in diff_text or "_bug_tracker" in diff_text

    # Bug report workstation reuses diff viewer window target or closes to focus opener
    bug_report_tpl = Path(__file__).resolve().parent.parent / "provider" / "templates" / "bug_report.html.j2"
    bug_text = bug_report_tpl.read_text(encoding="utf-8")
    assert 'target="hardware_vcs_diff_viewer"' in bug_text
    assert "returnToDashboard" in bug_text
    assert "window.opener.focus()" in bug_text

    # Code review workstation reuses diff viewer window target or closes to focus opener
    cr_tpl = Path(__file__).resolve().parent.parent / "provider" / "templates" / "code_review.html.j2"
    cr_text = cr_tpl.read_text(encoding="utf-8")
    assert 'target="hardware_vcs_diff_viewer"' in cr_text
    assert "returnToDashboard" in cr_text


def test_regression_bug_202_smartlog_and_files_vertical_scrollbars_visible() -> None:
    """Verify BUG-202: Smartlog and file view columns have permanently visible Quake scrollbars."""
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")

    # 1. Custom Quake-styled scrollbars defined
    assert "/* Visible Quake Scrollbars (BUG-202) */" in tpl_text
    assert "scrollbar-width: thin;" in tpl_text
    assert "::-webkit-scrollbar" in tpl_text
    assert "::-webkit-scrollbar-thumb" in tpl_text

    # 2. column-scroll has overflow-y: scroll and scrollbar-gutter: stable
    assert "overflow-y: scroll;" in tpl_text
    assert "scrollbar-gutter: stable;" in tpl_text


def test_regression_bug_196_vertical_panels_resizable_and_persisted() -> None:
    """Verify BUG-196: Vertical panels (smartlog, files, diff) have draggable resizers and localStorage persistence."""
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")

    # Resizer elements between panels
    assert 'id="resizerSmartlog"' in tpl_text
    assert 'id="resizerFiles"' in tpl_text
    assert "column-resizer" in tpl_text

    # Resizer initialization and localStorage persistence logic
    assert "initPanelResizers()" in tpl_text
    assert 'localStorage.getItem("diffview_smartlog_width")' in tpl_text
    assert 'localStorage.getItem("diffview_files_width")' in tpl_text
    assert "localStorage.setItem(storageKey, newWidth)" in tpl_text
    assert "col-resize" in tpl_text

    # togglePane updates resizers when panes are collapsed or expanded
    assert 'document.getElementById("resizerSmartlog")' in tpl_text
    assert 'document.getElementById("resizerFiles")' in tpl_text


def test_regression_bug_197_branch_formatting_groups_and_search() -> None:
    """Verify BUG-197: Branch UI separates main/release branches at top, has search, and filters other users."""
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")

    # Branch picker button and modal
    assert 'id="btnBranchDropdown"' in tpl_text
    assert 'id="modalBranchPicker"' in tpl_text
    assert 'id="branchSearchInput"' in tpl_text
    assert 'id="chkHideOtherUsers"' in tpl_text
    assert 'id="mainReleaseBranchList"' in tpl_text
    assert 'id="featureBranchList"' in tpl_text

    # Optgroup structure in branchSelect
    assert '<optgroup label="⭐ Main &amp; Release Branches">' in tpl_text
    assert '<optgroup label="🌿 Feature &amp; PR Branches">' in tpl_text

    # Client-side filtering logic
    assert "renderBranchLists()" in tpl_text
    assert "filterBranchList()" in tpl_text
    assert "hideOtherUsers" in tpl_text


def test_regression_bug_199_jump_to_cr_icon_button_and_comment_counter() -> None:
    """Verify BUG-199: Commit actions row has Jump to CR button with open/total count and reviewed styling."""
    from model.vcs import CommitNodeModel

    # Verify CommitNodeModel has CR tracking attributes
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

    # Verify template contains jump-cr-btn with dynamic counter and reviewed class
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")
    assert "jump-cr-btn" in tpl_text
    assert "jumpToCR" in tpl_text
    assert "cr-badge" in tpl_text
    assert "cr-reviewed" in tpl_text
    assert "node.cr_open_count" in tpl_text


def test_regression_bug_203_multi_commit_shift_click_selection() -> None:
    """Verify BUG-203: Smartlog commit checkboxes and rows support Shift-Click contiguous range selection."""
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")

    # Shift-click event handler on checkboxes
    assert "onCommitCheckChanged(event, this)" in tpl_text
    assert "event.shiftKey" in tpl_text
    assert "lastCheckedCommitIndex" in tpl_text

    # Smartlog nodes carry data-hash and accept event parameter in selectCommit
    assert 'data-hash="{{ node.commit_hash }}"' in tpl_text
    assert "selectCommit('{{ node.commit_hash }}', event)" in tpl_text


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

    # 5. Verify template contains pr-local-badge and local fallback toast
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")
    assert "pr-local-badge" in tpl_text
    assert "has not been created on GitHub yet" in tpl_text


def test_regression_bug_211_code_review_panel_resizing_and_lfs_styling() -> None:
    """Verify BUG-211: Code review panels support draggable resizing and LFS files have special UI formatting."""
    cr_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "code_review.html.j2"
    cr_text = cr_path.read_text(encoding="utf-8")

    # 1. Column resizers present in HTML
    assert 'id="resizerCommits"' in cr_text
    assert 'id="resizerFiles"' in cr_text
    assert 'class="column-resizer"' in cr_text

    # 2. Resizer setup and localStorage persistence in JS
    assert "initPanelResizers()" in cr_text
    assert "codereview_commits_width" in cr_text
    assert "codereview_files_width" in cr_text
    assert "setupResizer(resizerCommits" in cr_text
    assert "setupResizer(resizerFiles" in cr_text

    # 3. LFS badges and classes in CSS and templates
    assert ".quake-badge-lfs" in cr_text
    assert ".lfs-file-item" in cr_text
    assert 'id="activeFileLfs"' in cr_text
    assert "f.is_lfs" in cr_text
    assert "📦 LFS" in cr_text

    # 4. FileDiffModel supports is_lfs field
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

    # 5. Verify diff_view template has rebase button and ancestor top badge
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")
    assert 'id="btnRebase"' in tpl_text
    assert "onRebaseClicked()" in tpl_text
    assert "ancestor-top-node" in tpl_text
    assert "node-badge-ancestor" in tpl_text


def test_regression_bug_215_diff_view_css_syntax() -> None:
    """Verify BUG-215 regression: CSS inside diff_view.html.j2 style block has balanced braces.

    A missing closing brace in .node-badge-pr.pr-tag-link caused subsequent modal overlay rules
    (.quake-modal-overlay) to fail to parse, rendering the commit dialog inline with giant unstyled fonts.
    """
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")

    # Extract style block
    start_tag = "<style>"
    end_tag = "</style>"
    start_idx = tpl_text.find(start_tag)
    end_idx = tpl_text.find(end_tag)
    assert start_idx != -1 and end_idx != -1

    css_content = tpl_text[start_idx + len(start_tag) : end_idx]

    # Check brace balance
    open_braces = css_content.count("{")
    close_braces = css_content.count("}")
    assert open_braces == close_braces, f"Mismatched braces in diff_view CSS: {open_braces} '{{' vs {close_braces} '}}'"

    # Verify .node-badge-pr.pr-tag-link block is properly terminated before .pr-local-badge
    assert ".node-badge-pr.pr-tag-link:hover {" in css_content
    node_badge_idx = css_content.find(".node-badge-pr.pr-tag-link:hover {")
    local_badge_idx = css_content.find(".pr-local-badge {", node_badge_idx)
    assert local_badge_idx != -1
    intermediate = css_content[node_badge_idx:local_badge_idx]
    assert intermediate.count("{") == intermediate.count("}"), (
        "CSS block between .node-badge-pr.pr-tag-link:hover and .pr-local-badge must have matching braces"
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


def test_regression_bug_217_textarea_bidirectional_and_autoresize() -> None:
    """Verify BUG-217 regression: Bug report text controls support horizontal/vertical resize and auto-expansion.

    Ensures:
    1. textarea CSS rules specify resize: both !important.
    2. input[type="text"] supports horizontal resize.
    3. autoResizeTextarea and autoResizeAllTextareas are present in JavaScript.
    4. Input event listener actively triggers autoResizeTextarea on textarea input.
    5. loadActiveBug and init trigger autoResizeAllTextareas.
    """
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "bug_report.html.j2"
    assert template_path.exists()
    content = template_path.read_text(encoding="utf-8")

    # 1. CSS styling checks
    assert "resize: both !important;" in content
    assert 'input[type="text"] {\n      resize: horizontal;' in content or "resize: horizontal;" in content

    # 2. JS function definitions
    assert "function autoResizeTextarea(" in content
    assert "function autoResizeAllTextareas()" in content

    # 3. Dynamic resizing invocation
    assert "autoResizeAllTextareas();" in content
    assert "autoResizeTextarea(e.target);" in content


def test_regression_bug_218_pr_creation_points_at_and_merged_commits_hidden(tmp_path: Path) -> None:
    """Verify BUG-218: PR creation uses --points-at instead of --contains and merged commits are detected and hidden."""
    # 1. Template validation
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    assert template_path.exists()
    content = template_path.read_text(encoding="utf-8")

    assert 'id="btnToggleMerged"' in content
    assert "toggleMergedCommits()" in content
    assert "updateMergedVisibility()" in content
    assert "isHideMergedEnabled()" in content
    assert "merged-commit" in content
    assert "hide-merged" in content
    assert "node-badge-merged" in content

    # 2. GitEngine verification with isolated git repo
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
    """Verify BUG-221: main branch and release branches v1..v6 appear correctly in branch viewer.

    Asserts that:
    1. Template properly classifies and sorts main and release branches.
    2. GitEngine.get_branches parses refs/heads/main as 'main' even when ambiguous tag exists.
    3. GitEngine.get_branches fetches both local and remote branches.
    4. Release branches (v1, v2, v3, etc.) are included in branch list.
    """
    # 1. Template validation
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    assert template_path.exists()
    content = template_path.read_text(encoding="utf-8")

    assert "mainReleaseBranches.sort" in content
    assert "heads/main" in content or ".endswith('/main')" in content

    # 2. Isolated repo with ambiguous tag and remote tracking branches
    repo_dir, shas = create_isolated_git_repo(tmp_path)
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


def test_regression_bug_224_225_horizontal_resizers_split_views() -> None:
    """Verify BUG-224 and BUG-225: horizontal resizers for split commit views in VCS UI and Code Review UI.

    Asserts that:
    1. diff_component.html.j2 defines .sbs-split-resizer with col-resize cursor.
    2. diff_component.html.j2 renders colgroup with col-old-code and col-new-code.
    3. diff_component.html.j2 implements setupSbsResizer with localStorage persistence.
    4. code_review.html.j2 defines .sbs-split-resizer with col-resize cursor.
    5. code_review.html.j2 renders colgroup with col-old-code and col-new-code.
    6. code_review.html.j2 implements setupSbsResizer with localStorage persistence.
    """
    templates_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    diff_comp_path = templates_dir / "diff_component.html.j2"
    cr_path = templates_dir / "code_review.html.j2"

    assert diff_comp_path.exists()
    assert cr_path.exists()

    diff_comp = diff_comp_path.read_text(encoding="utf-8")
    cr = cr_path.read_text(encoding="utf-8")

    # 1. diff_component assertions
    assert ".sbs-split-resizer" in diff_comp
    assert "col-resize" in diff_comp
    assert "col-old-code" in diff_comp
    assert "col-new-code" in diff_comp
    assert "setupSbsResizer" in diff_comp
    assert "vcs_sbs_split_ratio" in diff_comp

    # 2. code_review assertions
    assert ".sbs-split-resizer" in cr
    assert "col-resize" in cr
    assert "col-old-code" in cr
    assert "col-new-code" in cr
    assert "setupSbsResizer" in cr
    assert "cr_sbs_split_ratio" in cr


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


def test_regression_bug_227_toolbar_buttons_no_wrap_and_horizontal_scroll() -> None:
    """Verify BUG-227: Toolbar buttons do not wrap text, and toolbars have horizontal scrollers."""
    templates_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"

    # 1. diff_view.html.j2
    diff_view_text = (templates_dir / "diff_view.html.j2").read_text(encoding="utf-8")
    assert "white-space: nowrap !important;" in diff_view_text
    assert ".column-header {" in diff_view_text
    assert "overflow-x: auto;" in diff_view_text
    assert ".commit-toolbar {" in diff_view_text
    assert ".diff-toolbar {" in diff_view_text

    # 2. code_review.html.j2
    cr_text = (templates_dir / "code_review.html.j2").read_text(encoding="utf-8")
    assert "white-space: nowrap !important;" in cr_text
    assert "header.review-header {" in cr_text
    assert "flex-wrap: nowrap;" in cr_text
    assert "overflow-x: auto;" in cr_text

    # 3. diff_component.html.j2
    comp_text = (templates_dir / "diff_component.html.j2").read_text(encoding="utf-8")
    assert "overflow-x: auto;" in comp_text
    assert "flex-wrap: nowrap;" in comp_text

    # 4. bug_report.html.j2
    br_text = (templates_dir / "bug_report.html.j2").read_text(encoding="utf-8")
    assert "white-space: nowrap !important;" in br_text
    assert "header.quake-header {" in br_text
    assert "overflow-x: auto;" in br_text


def test_regression_bug_228_select_all_select_none_and_default_create_pr_stack() -> None:
    """Verify BUG-228: Select All and Select None buttons and default stack behavior for Create PR."""
    diff_view_text = (
        Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    ).read_text(encoding="utf-8")

    # Verify buttons in template
    assert 'id="btnSelectAll"' in diff_view_text
    assert 'id="btnSelectNone"' in diff_view_text
    assert "selectAllCommits()" in diff_view_text
    assert "selectNoneCommits()" in diff_view_text

    # Verify client implementation functions exist
    assert "function selectAllCommits()" in diff_view_text
    assert "function selectNoneCommits()" in diff_view_text
    assert "allCheckboxes.forEach" in diff_view_text

    # Verify default stack behavior in onCreatePR
    assert "BUG-228" in diff_view_text
    assert "targetCommits" in diff_view_text
    assert "smartlog-node:not(.merged-commit)" in diff_view_text


def test_regression_bug_229_pr_submit_interactive_modal_and_github_submission(tmp_path: Path) -> None:
    """Verify BUG-229: Interactive modal with progress bar and log display for PR submission."""
    diff_view_text = (
        Path(__file__).resolve().parent.parent / "provider" / "templates" / "diff_view.html.j2"
    ).read_text(encoding="utf-8")

    # 1. Verify modal UI elements exist
    assert 'id="prSubmitModalOverlay"' in diff_view_text
    assert 'id="prSubmitProgressBar"' in diff_view_text
    assert 'id="prSubmitProgressPercent"' in diff_view_text
    assert 'id="prSubmitLogOutput"' in diff_view_text
    assert 'id="btnPrSubmitDone"' in diff_view_text
    assert 'id="btnPrSubmitClose"' in diff_view_text
    assert "openPrSubmitModal" in diff_view_text
    assert "finishPrSubmitModal" in diff_view_text

    # 2. Test GitEngine.submit_prs backend execution
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


def test_regression_bug_232_file_action_buttons_copy_and_vscode(tmp_path: Path):
    """Verify BUG-232: Copy and Open in VS Code buttons are present next to file names."""
    template_dir = Path(__file__).parent.parent / "provider" / "templates"
    diff_view_html = (template_dir / "diff_view.html.j2").read_text(encoding="utf-8")
    code_review_html = (template_dir / "code_review.html.j2").read_text(encoding="utf-8")

    # In VCS diff viewer
    assert 'id="diffFileActions"' in diff_view_html
    assert 'onclick="copyActiveFilePath()"' in diff_view_html
    assert 'onclick="openInVsCode()"' in diff_view_html
    assert "vscode://file" in diff_view_html
    assert "btnOpenVsCode" in diff_view_html

    # In Code Review UI
    assert 'id="activeFileActions"' in code_review_html
    assert 'onclick="copyActiveFilePath()"' in code_review_html
    assert 'onclick="openInVsCode()"' in code_review_html
    assert "vscode://file" in code_review_html
    assert "btnOpenVsCode" in code_review_html

    # In runtime server rendering
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
        with urllib.request.urlopen(f"{base_url}/") as resp:
            content = resp.read().decode("utf-8")
            assert 'id="diffFileActions"' in content
            assert "btnOpenVsCode" in content
            assert str(repo_dir) in content or repo_dir.name in content

        with urllib.request.urlopen(f"{base_url}/review") as resp:
            content = resp.read().decode("utf-8")
            assert 'id="activeFileActions"' in content
            assert "btnOpenVsCode" in content
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_233_visible_high_contrast_scrollbars():
    """Verify BUG-233: All horizontal and vertical scrollbars are visible and high contrast."""
    template_dir = Path(__file__).parent.parent / "provider" / "templates"
    templates = [
        template_dir / "diff_view.html.j2",
        template_dir / "diff_component.html.j2",
        template_dir / "code_review.html.j2",
        template_dir / "bug_report.html.j2",
    ]

    for tmpl_path in templates:
        content = tmpl_path.read_text(encoding="utf-8")
        assert "scrollbar-color: var(--quake-copper, #c87a32) #1e130b;" in content, (
            f"Missing standard scrollbar-color in {tmpl_path.name}"
        )
        assert "::-webkit-scrollbar" in content, f"Missing webkit scrollbar in {tmpl_path.name}"
        assert "width: 10px;" in content, f"Scrollbar width too small / invisible in {tmpl_path.name}"
        assert "#965a25" in content, f"Missing copper thumb background in {tmpl_path.name}"
        assert "#ffb800" in content, f"Missing gold hover state in {tmpl_path.name}"


def test_regression_bug_234_pr_submit_no_git_sl_error(tmp_path: Path):
    """Verify BUG-234: GitEngine.submit_prs never runs git with sl binary."""
    repo_dir, shas = create_isolated_git_repo(tmp_path)
    engine = GitEngine(repo_root=repo_dir)

    res = engine.submit_prs()
    assert res["status"] == "ok"

    # Invariant: Never attempt to invoke `git <path-to-sl>`
    for line in res["logs"]:
        assert "is not a git command" not in line.lower(), f"Confusing git error in logs: {line}"
        assert "error running git" not in line.lower(), f"Confusing git error in logs: {line}"


def test_regression_bug_235_favicon_web_icon(tmp_path: Path):
    """Verify BUG-235: High-contrast Quake-themed favicon is created and served across dashboards."""
    static_favicon = Path(__file__).parent.parent / "provider" / "code_review" / "static" / "favicon.svg"
    assert static_favicon.exists(), "static/favicon.svg must exist"
    svg_content = static_favicon.read_text(encoding="utf-8")
    assert "<svg" in svg_content
    assert "#ffd700" in svg_content or "#ffb800" in svg_content
    assert "#c87a32" in svg_content

    # Check templates include the favicon link
    template_dir = Path(__file__).parent.parent / "provider" / "templates"
    for tmpl in ["diff_view.html.j2", "code_review.html.j2", "bug_report.html.j2"]:
        content = (template_dir / tmpl).read_text(encoding="utf-8")
        assert '<link rel="icon" type="image/svg+xml" href="/static/favicon.svg">' in content, (
            f"Missing favicon link in {tmpl}"
        )

    # Check DashboardServer serves favicon.ico and static/favicon.svg
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
            assert "image/svg+xml" in resp.headers.get("Content-Type")
            assert len(resp.read()) > 0

        with urllib.request.urlopen(f"{base_url}/static/favicon.svg") as resp:
            assert resp.status == 200
            assert "image/svg+xml" in resp.headers.get("Content-Type")
            assert len(resp.read()) > 0
    finally:
        server.shutdown()
        server.server_close()


def test_regression_bug_237_side_by_side_resizer_gripper():
    """Verify BUG-237: Split-pane resizer gripper is visible and uses containerRect with fixed table layout."""
    template_dir = Path(__file__).parent.parent / "provider" / "templates"
    diff_comp = (template_dir / "diff_component.html.j2").read_text(encoding="utf-8")
    code_rev = (template_dir / "code_review.html.j2").read_text(encoding="utf-8")

    # Invariant 1: Grip icon is present in both views
    assert ".sbs-split-resizer::before" in diff_comp
    assert 'content: "⋮"' in diff_comp
    assert ".sbs-split-resizer::before" in code_rev
    assert 'content: "⋮"' in code_rev

    # Invariant 2: VCS diff view uses fixed table layout to prevent inverted resizer motion
    assert "table-layout: fixed !important;" in diff_comp
    assert "width: 100% !important;" in diff_comp
    assert "min-width: max-content" in code_rev

    # Invariant 3: Mouse drag math uses containerRect, not tableRect
    assert "containerRect = container.getBoundingClientRect()" in diff_comp
    assert "moveEvent.clientX - containerRect.left" in diff_comp
    assert "containerRect = container.getBoundingClientRect()" in code_rev
    assert "moveEvent.clientX - containerRect.left" in code_rev


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


def test_regression_bug_242_code_review_toolbar_layout() -> None:
    """Verify BUG-242: Main review toolbar is placed above app-body panes across full width."""
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "code_review.html.j2"
    content = template_path.read_text(encoding="utf-8")

    # Invariant 1: diff-toolbar appears before app-body in template
    toolbar_idx = content.find('<div class="diff-toolbar">')
    app_body_idx = content.find('<div class="app-body">')
    assert toolbar_idx != -1 and app_body_idx != -1
    assert toolbar_idx < app_body_idx, "diff-toolbar must be placed above app-body"

    # Invariant 2: Toolbar styling enforces full width and prevents horizontal scrollbar
    toolbar_css = content.split(".diff-toolbar {")[1].split("}")[0]
    assert "overflow-x: hidden" in toolbar_css
    assert "width: 100%" in toolbar_css

    # Invariant 3: Toggle controls are in the toolbar
    assert "btnToggleCommits" in content
    assert "btnToggleFiles" in content
    assert "btnFocus" in content


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


def test_regression_bug_245_word_wrap_in_diff_views() -> None:
    """Verify BUG-245: Word wrap toggle button, persistence, and pre-wrap CSS in diff views."""
    templates_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    diff_comp_text = (templates_dir / "diff_component.html.j2").read_text(encoding="utf-8")
    diff_view_text = (templates_dir / "diff_view.html.j2").read_text(encoding="utf-8")
    cr_text = (templates_dir / "code_review.html.j2").read_text(encoding="utf-8")

    # 1. diff_component.html.j2 has .diff-word-wrap styling with pre-wrap and overflow-wrap
    assert ".diff-word-wrap" in diff_comp_text
    assert "white-space: pre-wrap !important;" in diff_comp_text
    assert (
        "overflow-wrap: anywhere !important;" in diff_comp_text
        or "word-break: break-word !important;" in diff_comp_text
    )

    # 2. diff_view.html.j2 has wrap button and toggle function
    assert 'id="btnToggleWrap"' in diff_view_text
    assert "toggleWordWrap" in diff_view_text
    assert "quake_diff_word_wrap" in diff_view_text

    # 3. code_review.html.j2 has wrap button, styles, and toggle function
    assert 'id="btnToggleWrap"' in cr_text
    assert ".diff-word-wrap" in cr_text
    assert "toggleWordWrap" in cr_text
    assert "quake_diff_word_wrap" in cr_text


def test_regression_bug_246_auto_sync_panes() -> None:
    """Verify BUG-246: Auto-sync polls repository changes to update working tree and commit panes automatically."""
    templates_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    diff_view_text = (templates_dir / "diff_view.html.j2").read_text(encoding="utf-8")
    cr_text = (templates_dir / "code_review.html.j2").read_text(encoding="utf-8")

    # 1. diff_view.html.j2 implements automatic background sync
    assert "startAutoSync" in diff_view_text
    assert "syncWorkingAndCommitsSilently" in diff_view_text or "autoSyncTimer" in diff_view_text
    assert "renderSmartlogList" in diff_view_text
    assert "startAutoSync()" in diff_view_text

    # 2. code_review.html.j2 implements auto-sync for commits and files
    assert "startAutoSync" in cr_text or "autoSyncTimer" in cr_text


def test_regression_bug_247_single_unified_sync_button() -> None:
    """Verify BUG-247: Remove redundant Sync DB button; keep a single unified Sync button that handles both git and DB sync."""
    templates_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    diff_view_text = (templates_dir / "diff_view.html.j2").read_text(encoding="utf-8")

    # 1. Single unified Sync button exists
    assert 'id="btnSync"' in diff_view_text

    # 2. Separate 'Sync DB' button is removed from UI
    assert 'id="btnSyncFeedback"' not in diff_view_text
    assert "⚡ Sync DB" not in diff_view_text


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


def test_regression_bug_248_bug_report_sort_and_filter_menus() -> None:
    """Verify BUG-248: Bug Report field contains sort and filter menus with session persistence."""
    template_path = Path(__file__).resolve().parent.parent / "provider" / "templates" / "bug_report.html.j2"
    tpl_text = template_path.read_text(encoding="utf-8")

    # 1. Sort and filter UI menus present in bug list sidebar
    assert 'id="select-bug-sort"' in tpl_text
    assert 'id="select-filter-category"' in tpl_text
    assert 'id="select-filter-severity"' in tpl_text

    # 2. Event handlers and sorting/filtering logic
    assert "onBugSortChanged" in tpl_text
    assert "onFilterCategoryChanged" in tpl_text
    assert "onFilterSeverityChanged" in tpl_text

    # 3. Session persistence for filter and sorting options
    assert "sessionStorage" in tpl_text
    assert "bug_sort" in tpl_text


def test_regression_bug_252_unified_diff_word_wrap_and_tag_balancing() -> None:
    """Verify BUG-252: Unified diff word-wrap containment and tag balancing in diff templates.

    Ensures:
    1. diff_component.html.j2 and code_review.html.j2 pin .diff-unified-text and .unified-text to column 4 with min-width: 0.
    2. diff_component.html.j2 balances syntax highlighting spans across lines and strips orphan closing spans.
    3. Unified diff text is rendered in a div rather than span so rogue inner closing spans cannot close the line container.
    """
    templates_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    diff_comp_text = (templates_dir / "diff_component.html.j2").read_text(encoding="utf-8")
    cr_text = (templates_dir / "code_review.html.j2").read_text(encoding="utf-8")

    # 1. Grid positioning and min-width containment for unified diff text
    assert "grid-column: 4" in diff_comp_text
    assert "min-width: 0" in diff_comp_text
    assert "grid-column: 4" in cr_text

    # 2. Div container for unified text preventing stray span closure
    assert '<div class="diff-unified-text hljs">' in diff_comp_text
    assert '<div class="unified-text hljs">' in cr_text

    # 3. Tag balancing and orphan tag stripping in diff engine
    assert "balanceLines" in diff_comp_text
    assert "openTags" in diff_comp_text


def test_regression_bug_257_copy_icons_in_dashboard() -> None:
    """Verify BUG-257: Copy icon buttons next to commit hashes, branch names, and bug IDs in dashboard."""
    templates_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    diff_view_text = (templates_dir / "diff_view.html.j2").read_text(encoding="utf-8")
    bug_report_text = (templates_dir / "bug_report.html.j2").read_text(encoding="utf-8")
    cr_text = (templates_dir / "code_review.html.j2").read_text(encoding="utf-8")

    # 1. diff_view.html.j2 copy buttons:
    # Commit SHA copy button
    assert "copy-sha-btn" in diff_view_text
    assert "copy-icon-btn" in diff_view_text
    assert "copyText" in diff_view_text
    # Branch name copy button (current branch & branch list items)
    assert "btnCopyCurrentBranch" in diff_view_text
    # Bug ID copy button on smartlog nodes
    assert "copy-badge-btn" in diff_view_text

    # 2. bug_report.html.j2 copy buttons:
    # Bug ID in sidebar list and active issue header
    assert "btn-copy-active-bug" in bug_report_text
    assert "active-bug-id-display" in bug_report_text
    assert "copy-icon-btn" in bug_report_text
    assert "copy-badge-btn" in bug_report_text
    assert "copyActiveBugId" in bug_report_text
    assert "copyText" in bug_report_text

    # 3. code_review.html.j2 copy buttons:
    # Commit SHA copy button in commit drawer
    assert "copy-sha-btn" in cr_text
    assert "copy-icon-btn" in cr_text
    assert "copyText" in cr_text


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


def test_regression_bug_274_workstations_modal_windows() -> None:
    """Verify BUG-274: Code review and bug report workstations are modal windows over VCS UI."""
    tpl_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    diff_text = (tpl_dir / "diff_view.html.j2").read_text(encoding="utf-8")
    cr_text = (tpl_dir / "code_review.html.j2").read_text(encoding="utf-8")
    bug_text = (tpl_dir / "bug_report.html.j2").read_text(encoding="utf-8")

    # 1. Diff view includes workstation modal overlay and iframe container
    assert 'id="workstationModal"' in diff_text
    assert 'id="workstationIframe"' in diff_text
    assert "workstation-modal-overlay" in diff_text
    assert "workstation-modal-container" in diff_text
    assert "workstation-modal-iframe" in diff_text

    # 2. Fixed size with tiny margin and darkened backdrop
    assert "rgba(0, 0, 0, 0.75)" in diff_text
    assert "calc(100vw - 36px)" in diff_text
    assert "calc(100vh - 36px)" in diff_text

    # 3. Diff view JavaScript exposes modal open and close
    assert "function openWorkstationModal(url, targetName)" in diff_text
    assert "function closeWorkstationModal()" in diff_text
    assert "window.closeWorkstationModal = closeWorkstationModal;" in diff_text
    assert "openWorkstationModal(res.url" in diff_text

    # 4. Code review header replaces back button with X close button
    assert "← Dashboard" not in cr_text
    assert "modal-close-btn" in cr_text
    assert "✕" in cr_text
    assert "closeWorkstation()" in cr_text
    assert "window.parent.closeWorkstationModal()" in cr_text

    # 5. Bug report header replaces back button with X close button
    assert "← Dashboard" not in bug_text
    assert "modal-close-btn" in bug_text
    assert "✕" in bug_text
    assert "closeWorkstation()" in bug_text
    assert "window.parent.closeWorkstationModal()" in bug_text
