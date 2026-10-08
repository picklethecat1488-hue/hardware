"""Regression tests for BUG-281: Port dashboard to Eel standalone app window."""

from pathlib import Path
import sys
import threading
import time
import urllib.request
from unittest.mock import patch, MagicMock

import pytest

# Ensure src is on path
_src_dir = Path(__file__).resolve().parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from dashboard import parse_arguments, launch_browser
from provider.dashboard.server import DashboardServer
from provider.vcs.git_engine import get_git_root


def test_cli_eel_arguments_and_defaults() -> None:
    """Verify CLI arguments default to Eel standalone app mode and support --eel/--app flags."""
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

    # 5. Backward-compatible explicit --browser vscode
    with patch("sys.argv", ["dashboard.py", "--browser", "vscode"]):
        args = parse_arguments()
        assert args.browser == "vscode"

    # 6. Explicit --browser system
    with patch("sys.argv", ["dashboard.py", "--browser", "system"]):
        args = parse_arguments()
        assert args.browser == "system"


def test_launch_browser_eel_target() -> None:
    """Verify launch_browser invokes Eel standalone app launcher when target='eel'."""
    with patch("provider.eel.launcher.launch_eel") as mock_launch_eel:
        launch_browser("http://127.0.0.1:8877/", target="eel")
        mock_launch_eel.assert_called_once_with("http://127.0.0.1:8877/")


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
