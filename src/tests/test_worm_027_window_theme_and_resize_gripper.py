"""Regression unit test for WORM-027: Apply dashboard theme to Window UI & resize gripper.

Verifies:
1. All dashboard templates (diff_view.html.j2, code_review.html.j2, bug_report.html.j2) define
   a visible high-contrast themed border on <body>.
2. All dashboard templates contain a .window-resize-gripper element in the bottom-right corner
   with themed styling and nwse-resize cursor.
3. apply_native_window_theme configures native window appearance (dark theme and transparent titlebar)
   and is registered in run_webview_window.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from provider.webview.launcher import apply_native_window_theme, run_webview_window

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "provider" / "templates"


def test_templates_have_visible_window_resize_borders() -> None:
    """Verify that <body> has visible themed border and inset highlight across all main templates."""
    for tpl_name in ("diff_view.html.j2", "code_review.html.j2", "bug_report.html.j2"):
        tpl_path = TEMPLATES_DIR / tpl_name
        assert tpl_path.exists(), f"Template {tpl_name} not found"
        content = tpl_path.read_text(encoding="utf-8")
        assert "border: 2px solid var(--quake-border-mid)" in content or "border: 2px solid" in content, (
            f"{tpl_name} must specify visible themed border on window body"
        )
        assert "box-shadow:" in content, f"{tpl_name} must have box-shadow highlighting window borders"


def test_templates_have_window_resize_gripper() -> None:
    """Verify all main templates contain a .window-resize-gripper with nwse-resize cursor."""
    for tpl_name in ("diff_view.html.j2", "code_review.html.j2", "bug_report.html.j2"):
        tpl_path = TEMPLATES_DIR / tpl_name
        assert tpl_path.exists(), f"Template {tpl_name} not found"
        content = tpl_path.read_text(encoding="utf-8")
        assert 'class="window-resize-gripper"' in content, f"{tpl_name} must contain .window-resize-gripper element"
        assert ".window-resize-gripper" in content, f"{tpl_name} must contain CSS for .window-resize-gripper"
        assert "cursor: nwse-resize" in content, f"{tpl_name} gripper must have nwse-resize cursor"


def test_apply_native_window_theme_execution() -> None:
    """Verify apply_native_window_theme configures Cocoa window appearance and titlebar transparency."""
    mock_window = MagicMock()
    mock_native = MagicMock()
    mock_window.native = mock_native

    with patch("sys.platform", "darwin"), patch("PyObjCTools.AppHelper.callAfter") as mock_call_after:
        apply_native_window_theme(mock_window, "#291a10")
        assert mock_call_after.called

        # Invoke the callback passed to callAfter
        callback = mock_call_after.call_args[0][0]
        mock_appkit = MagicMock()
        with patch.dict("sys.modules", {"AppKit": mock_appkit}):
            callback()
            assert mock_native.setAppearance_.called
            assert mock_native.setTitlebarAppearsTransparent_.called
            assert mock_native.setBackgroundColor_.called


def test_run_webview_window_registers_theme_and_shown_event() -> None:
    """Verify run_webview_window hooks window.events.shown to apply native theme."""
    mock_webview = MagicMock()
    mock_window = MagicMock()
    mock_events = MagicMock()
    mock_shown = MagicMock()
    mock_shown.__iadd__.return_value = mock_shown
    mock_events.shown = mock_shown
    mock_window.events = mock_events
    mock_webview.create_window.return_value = mock_window

    with patch.dict("sys.modules", {"webview": mock_webview}):
        run_webview_window(
            url="http://127.0.0.1:8767/",
            title="Quake Workstation",
        )
        assert mock_shown.__iadd__.called
