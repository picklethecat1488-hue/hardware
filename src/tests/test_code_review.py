"""Comprehensive unit tests for the Quake Code Review tool and Markdown Exporter.

Validates Git diff parsing, side-by-side line alignment, Markdown rendering,
REST API endpoints, and session persistence.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from model.code_review import (
    CommentModel,
    FileReviewStatus,
    ReviewSessionModel,
    ReviewSeverity,
    ReviewStatus,
)
from provider.code_review.git_utils import (
    GitReviewEngine,
    extract_line_snippet,
    get_git_root,
)
from provider.code_review.markdown_exporter import MarkdownReviewExporter
from provider.code_review.server import ReviewServer
from code_review import launch_browser, parse_arguments


def test_git_review_engine_basics() -> None:
    """Verify GitReviewEngine correctly discovers repository and queries commits."""
    root = get_git_root()
    assert root.exists()
    assert (root / "pyproject.toml").exists()

    engine = GitReviewEngine(repo_root=root)
    commits = engine.get_commits(limit=5)
    assert len(commits) > 0
    assert commits[0].commit_hash != ""
    assert commits[0].short_hash != ""


def test_git_review_engine_diff_and_snippets() -> None:
    """Verify GitReviewEngine parses diff hunks and extracts source snippets."""
    root = get_git_root()
    engine = GitReviewEngine(repo_root=root)

    # Check diff for pyproject.toml
    diff_model = engine.get_file_diff("HEAD", "pyproject.toml")
    assert diff_model.file_path == "pyproject.toml"
    assert not diff_model.is_binary
    assert len(diff_model.side_by_side) > 0

    snippet = extract_line_snippet("pyproject.toml", start_line=1, end_line=5, commit="HEAD", repo_root=root)
    assert "[project]" in snippet


def test_markdown_exporter_rendering(tmp_path: Path) -> None:
    """Verify MarkdownReviewExporter formats review findings with links, snippets, and action items."""
    exporter = MarkdownReviewExporter(repo_root=tmp_path)

    session = ReviewSessionModel(
        title="Test Review",
        verdict=ReviewStatus.CHANGES_REQUESTED,
        summary="Found 1 critical architectural issue.",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        comments=[
            CommentModel(
                id="c1",
                file_path="src/model/pcb.py",
                start_line=10,
                end_line=15,
                severity=ReviewSeverity.MUST_FIX,
                body="Critical null pointer risk on unrouted trace.",
                code_snippet="def route_trace():\n    pass",
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
            CommentModel(
                id="c2",
                file_path="src/model/pcb.py",
                start_line=20,
                end_line=20,
                severity=ReviewSeverity.NIT,
                body="Rename parameter for clarity.",
                code_snippet="x = 1",
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
            CommentModel(
                id="c3",
                file_path="src/model/pcb.py",
                start_line=25,
                end_line=30,
                severity=ReviewSeverity.PROPOSAL,
                body="Consider using coplanar waveguide solver.",
                code_snippet="def calculate_cpw():\n    pass",
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        ],
        files={
            "src/model/pcb.py": {
                "path": "src/model/pcb.py",
                "status": FileReviewStatus.REVIEWED,
                "notes": "LGTM otherwise",
            },
        },
    )

    output_file = tmp_path / "build" / "CR.md"
    exported_path = exporter.export_markdown(session, output_file, total_repo_files=1)

    assert exported_path.exists()
    content = exported_path.read_text(encoding="utf-8")

    assert "# Code Review Report: Test Review" in content
    assert "**`CHANGES_REQUESTED`**" in content
    assert "[MUST FIX]" in content
    assert "[PROPOSAL]" in content
    assert "[NIT]" in content
    assert "src/model/pcb.py" in content
    assert "Critical null pointer risk on unrouted trace." in content
    assert "```python" in content
    assert "- [ ] **[MUST FIX]**" in content


def test_session_json_persistence(tmp_path: Path) -> None:
    """Verify review session state correctly serializes and deserializes to JSON."""
    exporter = MarkdownReviewExporter(repo_root=tmp_path)
    state_file = tmp_path / "cr_feedback.json"

    session = ReviewSessionModel(
        title="Persistent Review",
        verdict=ReviewStatus.APPROVED,
        created_at=datetime.now(timezone.utc).isoformat(),
        comments=[
            CommentModel(
                id="abc123",
                file_path="src/build.py",
                start_line=5,
                end_line=10,
                severity=ReviewSeverity.MUST_FIX,
                body="Ensure build lock is released.",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        ],
    )

    exporter.save_session_json(session, state_file)
    assert state_file.exists()

    loaded = exporter.load_session_json(state_file)
    assert loaded is not None
    assert loaded.title == "Persistent Review"
    assert loaded.verdict == ReviewStatus.APPROVED
    assert len(loaded.comments) == 1
    assert loaded.comments[0].id == "abc123"


def test_review_server_api_flow(tmp_path: Path) -> None:
    """Verify ReviewServer endpoints: UI serving, diff query, comment addition, and markdown sync."""
    repo_root = get_git_root()
    md_out = tmp_path / "CR.md"
    state_out = tmp_path / "cr_state.json"

    server = ReviewServer(
        host="127.0.0.1",
        port=0,  # Ephemeral port
        repo_root=repo_root,
        markdown_output=md_out,
        state_file=state_out,
    )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = server.get_url()

    try:
        # 1. Test GET / serves UI HTML
        req = urllib.request.Request(base_url)
        with urllib.request.urlopen(req) as response:
            assert response.status == 200
            html_body = response.read().decode("utf-8")
            assert "QUAKE // CODE REVIEW TERMINAL" in html_body
            assert "GLQUAKE v1.09" in html_body

        # 2. Test GET /api/session
        with urllib.request.urlopen(f"{base_url}api/session") as response:
            assert response.status == 200
            session_data = json.loads(response.read().decode("utf-8"))
            assert session_data["verdict"] == "IN_REVIEW"

        # 3. Test GET /api/commits
        with urllib.request.urlopen(f"{base_url}api/commits") as response:
            assert response.status == 200
            commits_data = json.loads(response.read().decode("utf-8"))
            assert isinstance(commits_data, list)
            assert len(commits_data) > 0

        # 4. Test GET /api/files
        with urllib.request.urlopen(f"{base_url}api/files?commit=HEAD") as response:
            assert response.status == 200
            files_data = json.loads(response.read().decode("utf-8"))
            assert isinstance(files_data, list)

        # 5. Test POST /api/comment
        comment_payload = {
            "file_path": "pyproject.toml",
            "start_line": 1,
            "end_line": 3,
            "severity": "MUST_FIX",
            "body": "Test comment via API",
            "author": "TestReviewer",
        }
        post_req = urllib.request.Request(
            f"{base_url}api/comment",
            data=json.dumps(comment_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(post_req) as response:
            assert response.status == 200
            res_data = json.loads(response.read().decode("utf-8"))
            assert res_data["status"] == "ok"
            comment_id = res_data["comment"]["id"]

        # Verify markdown file and JSON state were synchronized immediately
        assert md_out.exists()
        assert state_out.exists()
        md_text = md_out.read_text(encoding="utf-8")
        assert "Test comment via API" in md_text
        assert "[MUST FIX]" in md_text

        # 6. Test POST /api/file_status
        status_req = urllib.request.Request(
            f"{base_url}api/file_status",
            data=json.dumps({"path": "pyproject.toml", "status": "REVIEWED"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(status_req) as response:
            assert response.status == 200
            status_data = json.loads(response.read().decode("utf-8"))
            assert status_data["file"]["status"] == "REVIEWED"

        # 7. Test DELETE /api/comment
        del_req = urllib.request.Request(
            f"{base_url}api/comment?id={comment_id}",
            method="DELETE",
        )
        with urllib.request.urlopen(del_req) as response:
            assert response.status == 200
            del_data = json.loads(response.read().decode("utf-8"))
            assert del_data["status"] == "ok"

        # 8. Test POST /api/verdict
        verdict_req = urllib.request.Request(
            f"{base_url}api/verdict",
            data=json.dumps({"verdict": "APPROVED", "summary": "Looks great!", "terminate": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(verdict_req) as response:
            assert response.status == 200
            verdict_data = json.loads(response.read().decode("utf-8"))
            assert verdict_data["session"]["verdict"] == "APPROVED"
            assert verdict_data["exported_to"] != ""

    finally:
        server.shutdown()
        server.server_close()


def test_review_status_lifecycle_and_auto_reset_to_in_review(tmp_path: Path) -> None:
    """Verify reviewer can approve right away and adding comments resets status to IN_REVIEW."""
    repo_root = get_git_root()
    server = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR.md",
        state_file=tmp_path / "cr_state.json",
    )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = server.get_url()

    try:
        # 1. Approve right away
        verdict_req = urllib.request.Request(
            f"{base_url}api/verdict",
            data=json.dumps({"verdict": "APPROVED", "terminate": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(verdict_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["session"]["verdict"] == "APPROVED"

        # 2. Type/post comments into the feedback window -> resets status to IN_REVIEW
        comment_payload = {
            "file_path": "pyproject.toml",
            "start_line": 1,
            "end_line": 2,
            "severity": "PROPOSAL",
            "body": "Add new linter rule",
        }
        comment_req = urllib.request.Request(
            f"{base_url}api/comment",
            data=json.dumps(comment_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(comment_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["verdict"] == "IN_REVIEW"

        # Verify session model reflects IN_REVIEW
        assert server.session.verdict == ReviewStatus.IN_REVIEW
    finally:
        server.shutdown()
        server.server_close()


def test_static_assets_and_diff_syntax_highlighting_content(tmp_path: Path) -> None:
    """Verify static assets are served and FileDiffModel contains old and new content."""
    repo_root = get_git_root()
    server = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR.md",
        state_file=tmp_path / "cr_state.json",
    )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    base_url = server.get_url()

    try:
        # 1. Test GET /static/highlight.min.js
        with urllib.request.urlopen(f"{base_url}static/highlight.min.js") as resp:
            assert resp.status == 200
            content = resp.read()
            assert len(content) > 10000
            assert resp.headers.get("Content-Type") == "application/javascript; charset=utf-8"

        # 2. Test GET /api/diff returns old_content and new_content
        with urllib.request.urlopen(f"{base_url}api/diff?commit=working&file=pyproject.toml") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert "old_content" in data
            assert "new_content" in data
            assert "full_content" in data

        # 3. Test UI rendering includes syntax highlighting CSS and scripts
        with urllib.request.urlopen(base_url) as resp:
            html = resp.read().decode("utf-8")
            assert "highlight.min.js" in html
            assert "hljs-keyword" in html
            assert "activeFileLang" in html
            assert "btnVerdictApprove" in html
            assert "btnVerdictChanges" in html
    finally:
        server.shutdown()
        server.server_close()


def test_parse_at_file_references_in_markdown_and_ui(tmp_path: Path) -> None:
    """Verify @ file references are parsed into markdown links and UI badges."""
    repo_root = get_git_root()
    exporter = MarkdownReviewExporter(repo_root=repo_root)

    # 1. Test markdown parsing of @path:line, @[path], and bare mentions
    text = "Please check @src/model/pcb.py:42 and @[build/CR.md] and @build/. Ask @author or email user@test.com."
    formatted = exporter._format_file_references(text)
    assert "[`@src/model/pcb.py:42`](file://" in formatted
    assert "#L42" in formatted
    assert "[`@build/CR.md`](file://" in formatted
    assert "[`@build/`](file://" in formatted
    assert "@author" in formatted  # bare author untouched
    assert "user@test.com" in formatted  # email untouched

    # 2. Test UI rendering contains file reference parsing and CLI suggestions
    server = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR.md",
        state_file=tmp_path / "cr_state.json",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        with urllib.request.urlopen(base_url) as resp:
            html = resp.read().decode("utf-8")
            assert "parseFileReferences" in html
            assert "quake-file-ref" in html
            assert "cliSuggestions" in html
    finally:
        server.shutdown()
        server.server_close()


def test_review_server_termination_and_auto_export_on_approve_and_reject(tmp_path: Path) -> None:
    """Verify that approving or requesting changes auto-exports CR.md and gracefully terminates server."""
    repo_root = get_git_root()

    # 1. Test APPROVE termination
    md_approve = tmp_path / "CR_approve.md"
    state_approve = tmp_path / "cr_approve.json"
    server1 = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=md_approve,
        state_file=state_approve,
    )
    thread1 = threading.Thread(target=server1.serve_forever, daemon=True)
    thread1.start()
    time.sleep(0.1)

    try:
        base_url1 = server1.get_url()
        # Verify UI does not contain legacy IN_REVIEW or PROVIDE FEEDBACK buttons, but contains terminationOverlay
        with urllib.request.urlopen(base_url1) as resp:
            html = resp.read().decode("utf-8")
            assert "btnVerdictInReview" not in html
            assert "PROVIDE FEEDBACK" not in html
            assert "EXPORT CR.md" not in html
            assert "terminationOverlay" in html
            assert "handleSessionTermination" in html

        verdict_req = urllib.request.Request(
            f"{base_url1}api/verdict",
            data=json.dumps({"verdict": "APPROVED"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(verdict_req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["terminating"] is True
            assert data["session"]["verdict"] == "APPROVED"
            assert data["exported_to"] == str(md_approve)

        # Verify automated Markdown report export
        assert md_approve.exists()
        assert state_approve.exists()
        md_text = md_approve.read_text(encoding="utf-8")
        assert "APPROVED" in md_text

        # Verify server thread terminates and releases terminal
        thread1.join(timeout=3.0)
        assert not thread1.is_alive()
        assert not server1.is_serving
    finally:
        server1.server_close()

    # 2. Test CHANGES_REQUESTED termination
    md_reject = tmp_path / "CR_reject.md"
    state_reject = tmp_path / "cr_reject.json"
    server2 = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=md_reject,
        state_file=state_reject,
    )
    thread2 = threading.Thread(target=server2.serve_forever, daemon=True)
    thread2.start()
    time.sleep(0.1)

    try:
        base_url2 = server2.get_url()
        verdict_req = urllib.request.Request(
            f"{base_url2}api/verdict",
            data=json.dumps({"verdict": "CHANGES_REQUESTED", "summary": "Needs design changes."}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(verdict_req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["terminating"] is True
            assert data["session"]["verdict"] == "CHANGES_REQUESTED"
            assert data["exported_to"] == str(md_reject)

        # Verify automated Markdown report export
        assert md_reject.exists()
        assert state_reject.exists()
        md_text = md_reject.read_text(encoding="utf-8")
        assert "CHANGES_REQUESTED" in md_text
        assert "Needs design changes." in md_text

        # Verify server thread terminates and releases terminal
        thread2.join(timeout=3.0)
        assert not thread2.is_alive()
        assert not server2.is_serving
    finally:
        server2.server_close()


def test_launch_browser_and_webpage_title(tmp_path: Path) -> None:
    """Verify webpage title formatting and browser launch defaults to VS Code."""
    repo_root = get_git_root()
    server = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR.md",
        state_file=tmp_path / "cr_state.json",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        base_url = server.get_url()
        with urllib.request.urlopen(base_url) as resp:
            html = resp.read().decode("utf-8")
            assert f"<title>Code Review: {repo_root.name}</title>" in html

        # Test CLI arguments default to VS Code
        with patch("sys.argv", ["code_review.py"]):
            args = parse_arguments()
            assert args.browser == "vscode"
            assert not args.no_browser

        with patch("sys.argv", ["code_review.py", "--no-browser"]):
            args_no = parse_arguments()
            assert args_no.no_browser

        with patch("sys.argv", ["code_review.py", "--browser", "system"]):
            args_sys = parse_arguments()
            assert args_sys.browser == "system"

        # Test launch_browser with VS Code does not spawn system browser or external process
        with patch("webbrowser.open") as mock_wb:
            launch_browser("http://127.0.0.1:8765/", target="vscode")
            mock_wb.assert_not_called()

        # Test launch_browser target='none' does nothing
        with patch("webbrowser.open") as mock_wb:
            launch_browser("http://127.0.0.1:8765/", target="none")
            mock_wb.assert_not_called()

        # Test launch_browser target='system' invokes webbrowser.open
        with patch("webbrowser.open") as mock_wb:
            launch_browser("http://127.0.0.1:8765/", target="system")
            mock_wb.assert_called_once_with("http://127.0.0.1:8765/")
    finally:
        server.shutdown()
        server.server_close()


def test_commit_stream_collapsed_when_single_commit(tmp_path: Path) -> None:
    """Verify that the commit stream pane defaults to collapsed when only one commit is reviewed."""
    repo_root = get_git_root()

    # 1. Single commit: paneCommits should be collapsed
    server_single = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR_single.md",
        state_file=tmp_path / "cr_single.json",
        revisions=["542007da5e1e120a3376fc8b3081fbb06112a78c"],
    )
    thread_single = threading.Thread(target=server_single.serve_forever, daemon=True)
    thread_single.start()
    time.sleep(0.1)

    try:
        with urllib.request.urlopen(server_single.get_url()) as resp:
            html = resp.read().decode("utf-8")
            assert 'id="paneCommits" class="pane-commits collapsed"' in html
            assert "commits: false, files: true, cli: true" in html
    finally:
        server_single.shutdown()
        server_single.server_close()

    # 2. Multiple commits: paneCommits should NOT be collapsed
    server_multi = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR_multi.md",
        state_file=tmp_path / "cr_multi.json",
        revisions=["HEAD~1", "HEAD"],
    )
    thread_multi = threading.Thread(target=server_multi.serve_forever, daemon=True)
    thread_multi.start()
    time.sleep(0.1)

    try:
        with urllib.request.urlopen(server_multi.get_url()) as resp:
            html = resp.read().decode("utf-8")
            assert 'id="paneCommits" class="pane-commits"' in html
            assert "commits: true, files: true, cli: true" in html
    finally:
        server_multi.shutdown()
        server_multi.server_close()


def test_diff_navigation_and_next_prev_change_cli(tmp_path: Path) -> None:
    """Verify that the review UI and CLI support next/prev change navigation across diff hunks."""
    repo_root = get_git_root()

    server = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR_nav.md",
        state_file=tmp_path / "cr_nav.json",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        with urllib.request.urlopen(server.get_url()) as resp:
            html = resp.read().decode("utf-8")
            # Verify toolbar buttons for change navigation exist
            assert 'id="btnPrevChange"' in html
            assert 'id="btnNextChange"' in html
            assert "navigateChange(-1)" in html
            assert "navigateChange(1)" in html

            # Verify CLI commands and helper functions are defined in frontend logic
            assert "navigateChange" in html
            assert "getFileChanges" in html
            assert 'case "next_change":' in html
            assert 'case "prev_change":' in html
            assert 'case "nc":' in html
            assert 'case "pc":' in html
            assert "next change / nc" in html
            assert "prev change / pc" in html
    finally:
        server.shutdown()
        server.server_close()


def test_untracked_files_diff_and_working_tree_handling(tmp_path: Path) -> None:
    """Verify that untracked and uncommitted files are properly diffed with additions."""
    repo_root = get_git_root()
    engine = GitReviewEngine(repo_root=repo_root)

    # Create a temporary untracked file in the repo
    temp_untracked = repo_root / "test_untracked_sample.txt"
    try:
        temp_untracked.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
        assert engine.has_working_tree_changes()

        working_files = engine.get_changed_files("working")
        match_untracked = [f for f in working_files if f["path"] == "test_untracked_sample.txt"]
        assert len(match_untracked) == 1
        assert match_untracked[0]["status"] == "??"
        assert int(match_untracked[0]["additions"]) == 3

        # Verify synthetic diff generation for untracked file
        diff = engine.get_file_diff("working", "test_untracked_sample.txt")
        assert not diff.is_binary
        assert diff.additions == 3
        assert diff.deletions == 0
        assert len(diff.hunks) == 1
        assert "+line 1" in diff.raw_diff
    finally:
        if temp_untracked.exists():
            temp_untracked.unlink()


def test_code_review_comment_editing_and_custom_snippet(tmp_path: Path) -> None:
    """Verify that comments can be edited via API and custom code snippets/commits are preserved."""
    repo_root = get_git_root()
    server = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR_edit.md",
        state_file=tmp_path / "cr_edit.json",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        # Add comment with explicit code snippet and commit
        add_req = urllib.request.Request(
            f"{server.get_url()}/api/comment",
            data=json.dumps(
                {
                    "file_path": "pyproject.toml",
                    "start_line": 1,
                    "end_line": 2,
                    "severity": "MUST_FIX",
                    "body": "Initial comment text",
                    "code_snippet": "[project]\nname = 'hardware'",
                    "commit": "HEAD",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(add_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"
            comment = data["comment"]
            cid = comment["id"]
            assert comment["body"] == "Initial comment text"
            assert "[project]" in comment["code_snippet"]

        # Edit the comment via /api/comment/edit
        edit_req = urllib.request.Request(
            f"{server.get_url()}/api/comment/edit",
            data=json.dumps(
                {
                    "id": cid,
                    "body": "Updated comment text via CLI",
                    "severity": "PROPOSAL",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(edit_req) as resp:
            edit_data = json.loads(resp.read().decode("utf-8"))
            assert edit_data["status"] == "ok"
            updated_c = edit_data["comment"]
            assert updated_c["body"] == "Updated comment text via CLI"
            assert updated_c["severity"] == "PROPOSAL"
    finally:
        server.shutdown()
        server.server_close()


def test_code_review_stale_session_reset_on_startup(tmp_path: Path) -> None:
    """Verify that concluded reviews (APPROVED or CHANGES_REQUESTED) do not leak stale feedback."""
    repo_root = get_git_root()
    state_file = tmp_path / "cr_stale.json"

    # Write a concluded session
    stale_session = ReviewSessionModel(
        title="Concluded Review",
        verdict=ReviewStatus.APPROVED,
        comments=[
            CommentModel(
                id="old1",
                file_path="src/build.py",
                start_line=1,
                end_line=1,
                severity=ReviewSeverity.MUST_FIX,
                body="Old feedback",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        ],
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    state_file.write_text(stale_session.model_dump_json(), encoding="utf-8")

    # Launch ReviewServer without fresh flag: should automatically start fresh because previous review concluded
    server = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR_clean.md",
        state_file=state_file,
    )
    assert len(server.session.comments) == 0
    assert server.session.verdict == ReviewStatus.IN_REVIEW
    server.server_close()


def test_code_review_ui_cli_focus_and_edit_button(tmp_path: Path) -> None:
    """Verify that the served UI template contains the Edit button and CLI console focus handler."""
    repo_root = get_git_root()
    server = ReviewServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        markdown_output=tmp_path / "CR_ui.md",
        state_file=tmp_path / "cr_ui.json",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        with urllib.request.urlopen(server.get_url()) as resp:
            html = resp.read().decode("utf-8")
            assert "editCommentViaCli" in html
            assert "Edit ✎" in html
            assert 'case "edit":' in html
            assert "editComment(" in html
            assert 'cliDrawer.addEventListener("click"' in html
    finally:
        server.shutdown()
        server.server_close()
