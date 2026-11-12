"""Regression unit test for WORM-027: Native window theme configuration in webview launcher."""

from unittest.mock import MagicMock, patch

from provider.webview.launcher import apply_native_window_theme, run_webview_window


def test_apply_native_window_theme_execution() -> None:
    """Verify apply_native_window_theme configures Cocoa window appearance and titlebar transparency."""
    mock_window = MagicMock()
    mock_native = MagicMock()
    mock_window.native = mock_native

    mock_apphelper = MagicMock()
    mock_pyobjc = MagicMock()
    mock_pyobjc.AppHelper = mock_apphelper

    with (
        patch("sys.platform", "darwin"),
        patch.dict("sys.modules", {"PyObjCTools": mock_pyobjc, "PyObjCTools.AppHelper": mock_apphelper}),
    ):
        apply_native_window_theme(mock_window, "#291a10")
        assert mock_apphelper.callAfter.called

        # Invoke the callback passed to callAfter
        callback = mock_apphelper.callAfter.call_args[0][0]
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
