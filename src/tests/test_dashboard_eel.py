"""Regression tests for BUG-281: Port dashboard to Eel standalone app window."""

from pathlib import Path
import sys
import threading
import time
import urllib.request
from unittest.mock import patch

import pytest

# Ensure src is on path
_src_dir = Path(__file__).resolve().parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from dashboard import parse_arguments, launch_browser
from provider.dashboard.server import DashboardServer
from provider.eel.launcher import launch_eel
from provider.vcs.git_engine import get_git_root


def test_cli_eel_arguments_and_defaults() -> None:
    """Verify CLI arguments strictly default to Eel standalone app mode and reject other browsers."""
    # 1. Default should be 'eel' standalone window
    with patch("sys.argv", ["dashboard.py"]):
        args = parse_arguments()
        assert args.browser == "eel", "Dashboard CLI should default to 'eel' standalone window mode"
        assert not args.no_browser

    # 2. --eel flag sets browser to eel
    with patch("sys.argv", ["dashboard.py", "--eel"]):
        args = parse_arguments()
        assert args.browser == "eel"

    # 3. --app flag sets browser to eel
    with patch("sys.argv", ["dashboard.py", "--app"]):
        args = parse_arguments()
        assert args.browser == "eel"

    # 4. Explicit --browser eel
    with patch("sys.argv", ["dashboard.py", "--browser", "eel"]):
        args = parse_arguments()
        assert args.browser == "eel"

    # 5. Non-Eel browser targets are strictly rejected (dropped support for non-Eel targets)
    with pytest.raises(SystemExit):
        with patch("sys.argv", ["dashboard.py", "--browser", "vscode"]):
            parse_arguments()

    with pytest.raises(SystemExit):
        with patch("sys.argv", ["dashboard.py", "--browser", "system"]):
            parse_arguments()

    # 6. --no-browser and --no-app disable launching the window
    with patch("sys.argv", ["dashboard.py", "--no-browser"]):
        args = parse_arguments()
        assert args.no_browser

    with patch("sys.argv", ["dashboard.py", "--no-app"]):
        args = parse_arguments()
        assert args.no_browser


def test_launch_browser_invokes_eel() -> None:
    """Verify launch_browser invokes Eel standalone app launcher."""
    with patch("provider.eel.launcher.launch_eel") as mock_launch_eel:
        launch_browser("http://127.0.0.1:8877/")
        mock_launch_eel.assert_called_once_with("http://127.0.0.1:8877/")


def test_launch_eel_no_webbrowser_fallback() -> None:
    """Verify launch_eel does not fall back to webbrowser when no Chromium browser is found."""
    with patch("provider.eel.launcher.find_eel_app_browser", return_value=None):
        result = launch_eel("http://127.0.0.1:8877/")
        assert result is False


def test_dashboard_server_serves_eel_js(tmp_path: Path) -> None:
    """Verify DashboardServer serves /eel.js with JavaScript MIME type for Eel integration."""
    repo_root = get_git_root()
    server = DashboardServer(
        host="127.0.0.1",
        port=0,
        repo_root=repo_root,
        sqlite_bug_file=tmp_path / "bugs.sqlite",
        sqlite_review_file=tmp_path / "cr.sqlite",
        bind_and_activate=True,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    try:
        url = f"{server.get_url()}/eel.js"
        with urllib.request.urlopen(url) as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "javascript" in content_type
            body = resp.read().decode("utf-8")
            assert "eel" in body
    finally:
        server.shutdown()
        server.server_close()
