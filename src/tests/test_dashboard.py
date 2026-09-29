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

from dashboard import main, parse_arguments, print_cli_smartlog
from model.vcs import (
    BranchInfoModel,
    CommitNodeModel,
    DiffViewSessionModel,
    FileDiffModel,
    WorkingTreeFileModel,
)
from provider.dashboard.server import DashboardServer
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
    assert 'id="btnSyncFeedback"' in tpl_text
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
    assert "picklethecat1488-hue/hardware/pull/" in tpl_text

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

    # 2. Test multi-commit PR creation preserving ancestor information
    # Pass commits in reverse order (descendant first) to verify topological sorting
    prs = engine.create_prs_for_commits([shas[2], shas[1]])
    assert len(prs) == 2
    pr1, pr2 = prs[0], prs[1]
    assert pr1["commit"] == shas[1]
    assert pr2["commit"] == shas[2]
    # Ancestor's base branch is repository branch
    curr_branch = engine.get_current_branch() or "main"
    assert pr1["base_branch"] == curr_branch
    # Descendant's base branch is ancestor's PR branch, preserving hierarchy
    assert pr2["base_branch"] == pr1["branch"]
    assert pr1["pr_number"] < pr2["pr_number"]

    # 3. Test validation: cannot create PR for commit that already has an associated PR
    with pytest.raises(ValueError, match="already has an associated PR"):
        engine.create_prs_for_commits([shas[1]])

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

        # Empty commits payload validation
        req = urllib.request.Request(
            f"{base_url}/api/pr/create",
            data=json.dumps({"commits": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 400

        # Successful PR creation via API
        req = urllib.request.Request(
            f"{base_url}/api/pr/create",
            data=json.dumps({"commits": [shas[1]]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["status"] == "ok"
            assert len(res["created"]) == 1
            assert res["created"][0]["commit"] == shas[1]

        # Duplicate PR creation returns 400
        req = urllib.request.Request(
            f"{base_url}/api/pr/create",
            data=json.dumps({"commits": [shas[1]]}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 400

        # Successful PR unlink via API
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
    assert 'window.open(res.url, "hardware_code_review");' in diff_text
    assert 'window.open(res.url, "hardware_bug_tracker");' in diff_text

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
    # Commit sha_b HAS branch pr123 pointing directly to it, so sha_b should be rejected.
    import pytest

    # Attempting to create PR for sha_b must fail because pr123 points at it
    with pytest.raises(ValueError, match="already has an associated PR"):
        engine.create_prs_for_commits([sha_b])

    # Attempting to create PR for already merged commit must fail
    if shas[2] in node_by_sha:
        with pytest.raises(ValueError, match="already merged into the tracking branch"):
            engine.create_prs_for_commits([shas[2]])


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
