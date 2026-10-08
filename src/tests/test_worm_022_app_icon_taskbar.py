"""Regression unit test for WORM-022: Cross-platform native application icon and themed window.

Verifies:
1. PWA manifest.json exists with theme_color, background_color, and icons.
2. Themed app.icns exists in static asset directory for macOS Dock/taskbar.
3. get_app_icon_path resolves platform icon (app.icns on macOS, favicon.ico on Windows, icon-512.png on Linux).
4. run_webview_window configures native window with theme background_color, dimensions, text selection, and icon.
5. launch_webview spawns a detached subprocess running the native webview GUI.
6. launch_browser defaults to native webview.
"""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

from dashboard import launch_browser
from provider.webview.launcher import (
    DEFAULT_BG_COLOR,
    DEFAULT_WINDOW_SIZE,
    get_app_icon_path,
    get_webview_storage_path,
    launch_webview,
    run_webview_window,
)


def test_manifest_theme_and_icons() -> None:
    """Verify manifest.json defines theme_color, display standalone, and icons."""
    manifest_path = Path(__file__).resolve().parent.parent / "provider" / "code_review" / "static" / "manifest.json"
    assert manifest_path.exists(), f"manifest.json not found at {manifest_path}"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "theme_color" in data
    assert "background_color" in data
    assert data.get("display") == "standalone"
    assert "icons" in data and len(data["icons"]) > 0


def test_static_app_icns_exists() -> None:
    """Verify pregenerated app.icns exists in static directory."""
    icns_path = Path(__file__).resolve().parent.parent / "provider" / "code_review" / "static" / "app.icns"
    assert icns_path.exists(), f"app.icns not found at {icns_path}"
    assert icns_path.stat().st_size > 1000, "app.icns must not be empty"


def test_get_app_icon_path_resolution() -> None:
    """Verify get_app_icon_path resolves platform-appropriate icon files."""
    static_dir = Path(__file__).resolve().parent.parent / "provider" / "code_review" / "static"

    with patch("sys.platform", "darwin"):
        icon = get_app_icon_path(static_dir)
        assert icon is not None
        assert icon.name == "app.icns"

    with patch("sys.platform", "win32"):
        icon = get_app_icon_path(static_dir)
        assert icon is not None
        assert icon.name == "favicon.ico"

    with patch("sys.platform", "linux"):
        icon = get_app_icon_path(static_dir)
        assert icon is not None
        assert icon.name in ("icon-512.png", "favicon.ico")


def test_run_webview_window_parameters() -> None:
    """Verify run_webview_window configures create_window and start with theme and icon."""
    mock_webview = MagicMock()
    with patch.dict("sys.modules", {"webview": mock_webview}):
        run_webview_window(
            url="http://127.0.0.1:8767/",
            title="Quake Workstation",
            width=1400,
            height=900,
            bg_color=DEFAULT_BG_COLOR,
            icon_path="/mock/app.icns",
            storage_path="/mock/storage",
        )

        mock_webview.create_window.assert_called_once_with(
            title="Quake Workstation",
            url="http://127.0.0.1:8767/",
            width=1400,
            height=900,
            min_size=(800, 600),
            background_color="#291a10",
            text_select=True,
            zoomable=True,
        )

        with patch("pathlib.Path.exists", return_value=True):
            mock_webview.reset_mock()
            run_webview_window(
                url="http://127.0.0.1:8767/",
                title="Quake Workstation",
                width=1400,
                height=900,
                bg_color="#291a10",
                icon_path="/mock/app.icns",
                storage_path="/mock/storage",
            )
            mock_webview.start.assert_called_once_with(
                private_mode=False,
                icon="/mock/app.icns",
                storage_path="/mock/storage",
            )


def test_launch_webview_spawns_process() -> None:
    """Verify launch_webview executes child process with webview CLI arguments."""
    with patch("subprocess.Popen") as mock_popen, \
         patch("pathlib.Path.exists", return_value=True):
        res = launch_webview("http://127.0.0.1:8767/")
        assert res is True
        assert mock_popen.called

        cmd_args, kwargs = mock_popen.call_args
        cmd = cmd_args[0]
        assert "--url" in cmd
        assert "http://127.0.0.1:8767/" in cmd
        assert "--title" in cmd
        assert "Quake Workstation" in cmd
        assert "--bg" in cmd
        assert DEFAULT_BG_COLOR in cmd


def test_launch_browser_defaults_to_webview() -> None:
    """Verify launch_browser invokes native webview launcher by default."""
    with patch("provider.webview.launcher.launch_webview") as mock_webview:
        mock_webview.return_value = True
        res = launch_browser("http://127.0.0.1:8767/")
        assert res is True
        mock_webview.assert_called_once_with("http://127.0.0.1:8767/")
