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
