"""Regression unit tests for Diff View performance optimization and granular progress bars.

Verifies:
1. GitEngine changed files caching for immutable commits and invalidation behavior.
2. GitEngine remote PR numbers local-first resolution without blocking network ls-remote calls.
3. DashboardRequestHandler file-watch check debouncing and static asset bypass.
4. Continuous asymptotic progress bar logic and descriptive contextual stage transitions in templates.
"""

from pathlib import Path
import subprocess
import time
from unittest.mock import MagicMock, patch

import jinja2
import pytest

from model.vcs import FileDiffModel
from provider.dashboard.server import DashboardRequestHandler, DashboardServer
from provider.vcs.git_engine import GitEngine


def test_git_engine_commit_files_caching(tmp_path: Path) -> None:
    """Verify GitEngine caches changed files for immutable commits and invalidates on clear_diff_cache."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)

    test_file = repo / "hello.txt"
    test_file.write_text("Hello World\n")
    subprocess.run(["git", "add", "hello.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)

    engine = GitEngine(repo_root=repo)
    head_sha = engine.get_head_commit()
    assert head_sha

    # First call: populates cache
    files_1 = engine.get_changed_files(head_sha)
    assert len(files_1) == 1
    assert files_1[0]["path"] == "hello.txt"
    assert (head_sha, False) in engine._commit_files_cache

    # Second call: served from cache without invoking diff-tree
    with patch("provider.vcs.git_engine.run_git_command") as mock_git:
        files_2 = engine.get_changed_files(head_sha)
        assert files_2 == files_1
        mock_git.assert_not_called()

    # Working tree files should NOT be cached in _commit_files_cache
    working_files = engine.get_changed_files("working")
    assert ("working", False) not in engine._commit_files_cache

    # clear_diff_cache flushes cache
    engine.clear_diff_cache()
    assert (head_sha, False) not in engine._commit_files_cache


def test_git_engine_remote_prs_local_ref_resolution(tmp_path: Path) -> None:
    """Verify GitEngine resolves remote PR numbers from local tracking refs without blocking ls-remote."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)

    engine = GitEngine(repo_root=repo)

    with patch("provider.vcs.git_engine.run_git_command") as mock_git:
        mock_git.return_value = "refs/remotes/origin/pr/42\nrefs/remotes/origin/pr/108\nrefs/remotes/origin/main"
        prs = engine.get_remote_pr_numbers(force_refresh=False)
        assert prs == {42, 108}
        # Assert ls-remote was not called
        for call_args in mock_git.call_args_list:
            args = call_args[0][0]
            assert "ls-remote" not in args

    # When force_refresh=True, verifies it can contact ls-remote
    with patch.object(engine, "get_repo_web_url", return_value="https://github.com/workspace/hardware"):
        with patch("provider.vcs.git_engine.run_git_command") as mock_git:
            mock_git.return_value = "abc1234\trefs/pull/555/head\n"
            prs_refresh = engine.get_remote_pr_numbers(force_refresh=True)
            assert 555 in prs_refresh


def test_dashboard_request_handler_throttling_and_static_bypass(tmp_path: Path) -> None:
    """Verify DashboardRequestHandler skips check_file_watch on static assets and throttles on dynamic routes."""
    mock_server = MagicMock()
    mock_server.review_server = MagicMock()
    mock_server.bug_server = MagicMock()
    mock_server._last_file_watch_check = 0.0

    handler = DashboardRequestHandler.__new__(DashboardRequestHandler)
    handler.server = mock_server
    handler._handle_serve_static = MagicMock()

    # 1. Static asset request: check_file_watch must NOT be called
    handler.path = "/static/css/quake.css"
    handler._do_get_impl()
    handler._handle_serve_static.assert_called_once_with("/static/css/quake.css")
    mock_server.review_server.check_file_watch.assert_not_called()
    mock_server.bug_server.check_file_watch.assert_not_called()

    # Favicon request: check_file_watch must NOT be called
    handler._handle_serve_static.reset_mock()
    handler.path = "/favicon.ico"
    handler._do_get_impl()
    handler._handle_serve_static.assert_called_once_with("/static/favicon.ico")
    mock_server.review_server.check_file_watch.assert_not_called()

    # 2. Dynamic route request: check_file_watch is invoked on first call
    handler._send_json = MagicMock()
    handler.path = "/api/version"
    handler._do_get_impl()
    assert mock_server.review_server.check_file_watch.call_count == 1
    assert mock_server.bug_server.check_file_watch.call_count == 1
    first_check_time = mock_server._last_file_watch_check
    assert first_check_time > 0

    # 3. Immediate subsequent dynamic route request (< 2.5s): check_file_watch should be throttled
    handler.path = "/api/version"
    handler._do_get_impl()
    # Call count should not increase
    assert mock_server.review_server.check_file_watch.call_count == 1
    assert mock_server.bug_server.check_file_watch.call_count == 1


def test_template_progress_bar_granularity_and_stages() -> None:
    """Verify template sources contain granular progress, asymptotic tail, and dynamic stage indicators."""
    templates_dir = Path(__file__).resolve().parents[1] / "provider" / "templates"

    # diff_view.html.j2 checks
    diff_view = (templates_dir / "diff_view.html.j2").read_text(encoding="utf-8")
    assert "syncProgressBar" in diff_view
    assert "syncProgressPercent" in diff_view
    assert "updateProgress" in diff_view
    assert "getStageMessage" in diff_view
    assert "actionProgressElapsed" in diff_view
    assert "elapsedSec.toFixed(1)" in diff_view
    assert "prSubmitProgressBar" in diff_view
    assert "prSubmitProgressPercent" in diff_view

    # bug_report.html.j2 checks
    bug_report = (templates_dir / "bug_report.html.j2").read_text(encoding="utf-8")
    assert "feedback-loading-modal" in bug_report
    assert "loading-progress-bar" in bug_report
    assert "loading-progress-percent" in bug_report
    # Ensure static 30% width was removed in favor of dynamic animation
    assert "width:30%" not in bug_report and "width: 30%" not in bug_report
    assert "showFeedbackLoading" in bug_report
    assert "hideFeedbackLoading" in bug_report


def test_bug_server_isolation_with_temporary_sqlite(tmp_path: Path) -> None:
    """Verify BugReportServer and DashboardServer with a test SQLite file isolate feedback to temp dir."""
    from provider.bug_report.server import BugReportServer
    from model.bug_report import BugReportModel, BugStatus, BugSeverity, BugCategory

    db_file = tmp_path / "isolated_test_bugs.sqlite"
    server = BugReportServer(sqlite_file=db_file, bind_and_activate=False)

    assert str(tmp_path) in str(server.feedback_dir)
    assert server.feedback_dir != Path.cwd() / "feedback"

    # Add a bug and save_and_sync
    b = BugReportModel(
        id="BUG-TEST-999",
        title="Isolated Test Bug",
        status=BugStatus.OPEN,
        severity=BugSeverity.LOW,
        category=BugCategory.PCB,
    )
    server.save_bug(b)

    # File should exist in temp dir feedback, NEVER in workspace feedback/
    assert (server.feedback_dir / "BUG_TEST-999.md").exists()
    assert not (Path.cwd() / "feedback" / "BUG_TEST-999.md").exists()


def test_bug_server_feedback_mtime_synchronization(tmp_path: Path) -> None:
    """Verify save_and_sync records post-commit feedback mtime, preventing false-positive check_file_watch."""
    from provider.bug_report.server import BugReportServer
    from model.bug_report import BugReportModel, BugStatus, BugSeverity, BugCategory

    db_file = tmp_path / "test_mtime.sqlite"
    server = BugReportServer(sqlite_file=db_file, bind_and_activate=False)

    b = BugReportModel(
        id="BUG-TEST-001",
        title="Mtime sync bug",
        status=BugStatus.OPEN,
        severity=BugSeverity.LOW,
        category=BugCategory.PCB,
    )
    server.save_bug(b)

    # Immediately after save_and_sync, check_file_watch must be False (no infinite loop)
    assert not server.check_file_watch()


def test_shared_common_js_library_integrated() -> None:
    """Verify common.js exists in static assets, contains valid JS, and is linked across templates."""
    import shutil
    import subprocess

    static_dir = Path(__file__).resolve().parent.parent / "provider" / "code_review" / "static"
    common_js = static_dir / "common.js"
    assert common_js.is_file(), "static/common.js must exist in code_review static assets"

    content = common_js.read_text(encoding="utf-8")
    assert "AsymptoticProgressBar" in content
    assert "performActionWithProgress" in content
    assert "setupPanelResizer" in content
    assert "sanitizeAuthor" in content

    node_bin = shutil.which("node")
    if node_bin:
        res = subprocess.run([node_bin, "--check", str(common_js)], capture_output=True, text=True)
        assert res.returncode == 0, f"common.js has JavaScript syntax errors: {res.stderr}"

    templates_dir = Path(__file__).resolve().parent.parent / "provider" / "templates"
    for tpl_name in ("diff_view.html.j2", "bug_report.html.j2", "code_review.html.j2"):
        tpl_path = templates_dir / tpl_name
        assert tpl_path.is_file()
        tpl_text = tpl_path.read_text(encoding="utf-8")
        assert '<script src="/static/common.js"></script>' in tpl_text, (
            f'{tpl_name} must include <script src="/static/common.js"></script>'
        )
