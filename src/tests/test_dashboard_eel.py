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


def test_dashboard_server_serves_manifest_and_icons(tmp_path: Path) -> None:
    """Verify DashboardServer serves Web App Manifest, favicon.ico, and PNG icons."""
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
        base = server.get_url()

        # 1. Manifest
        with urllib.request.urlopen(f"{base}/manifest.json") as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "manifest+json" in content_type or "json" in content_type
            data = resp.read().decode("utf-8")
            assert '"theme_color": "#291a10"' in data
            assert '"display": "standalone"' in data

        # 2. Favicon ICO
        with urllib.request.urlopen(f"{base}/favicon.ico") as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "x-icon" in content_type or "vnd.microsoft.icon" in content_type
            data = resp.read()
            assert len(data) > 0

        # 3. PNG icons
        for icon_path in ("/static/icon-192.png", "/static/icon-512.png", "/apple-touch-icon.png"):
            with urllib.request.urlopen(f"{base}{icon_path}") as resp:
                assert resp.status == 200
                content_type = resp.headers.get("Content-Type", "")
                assert "image/png" in content_type
                assert len(resp.read()) > 0
    finally:
        server.shutdown()
        server.server_close()


def test_templates_have_theme_color_and_manifest() -> None:
    """Verify all dashboard HTML templates define theme-color, dark scheme, manifest, and icons."""
    templates_dir = Path(__file__).parent.parent / "provider" / "templates"
    for tpl_name in ("diff_view.html.j2", "code_review.html.j2", "bug_report.html.j2"):
        tpl_path = templates_dir / tpl_name
        assert tpl_path.exists()
        content = tpl_path.read_text(encoding="utf-8")
        assert '<meta name="theme-color" content="#291a10">' in content
        assert '<meta name="color-scheme" content="dark">' in content
        assert '<link rel="manifest" href="/static/manifest.json">' in content
        assert '<link rel="shortcut icon" href="/static/favicon.ico">' in content
        assert '<link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png">' in content


def test_launch_eel_commandline_args_include_theme_and_scrollbars() -> None:
    """Verify launch_eel configures dark mode and overlay scrollbars in Chrome cmdline_args."""
    with (
        patch("provider.eel.launcher.find_eel_app_browser", return_value="/mock/chrome"),
        patch("eel.browsers.open") as mock_open,
    ):
        res = launch_eel("http://127.0.0.1:8877/")
        assert res is True
        args, kwargs = mock_open.call_args
        options = args[1]
        cmdline = options.get("cmdline_args", [])
        assert "--force-dark-mode" in cmdline
        assert "--enable-features=OverlayScrollbar" in cmdline
