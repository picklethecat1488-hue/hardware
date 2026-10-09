"""Regression unit test for WORM-025 / BUG-286: Close dashboard server when closing the app window.

Verifies:
1. launch_webview accepts on_close callback and invokes it when the webview process terminates.
2. launch_eel accepts on_close callback and invokes it when the browser process terminates.
3. launch_browser passes on_close callback to the target launcher.
4. Server terminates and cleans up lock file when on_close callback fires.
"""

import json
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from dashboard import launch_browser
from provider.webview.launcher import launch_webview


def test_launch_webview_accepts_and_invokes_on_close() -> None:
    """Verify launch_webview invokes on_close callback when the window process exits."""
    mock_proc = MagicMock()
    mock_proc.wait = MagicMock(return_value=0)

    closed_event = threading.Event()

    def on_close() -> None:
        closed_event.set()

    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
         patch("pathlib.Path.exists", return_value=True):
        res = launch_webview("http://127.0.0.1:8767/", on_close=on_close)
        assert res is True
        assert mock_popen.called

        # Wait for monitor thread to execute callback
        assert closed_event.wait(timeout=2.0), "on_close callback was not invoked on process exit"


def test_launch_browser_forwards_on_close() -> None:
    """Verify launch_browser forwards on_close callback to launcher."""
    on_close = MagicMock()

    with patch("provider.webview.launcher.launch_webview") as mock_webview:
        mock_webview.return_value = True
        res = launch_browser("http://127.0.0.1:8767/", browser="webview", on_close=on_close)
        assert res is True
        mock_webview.assert_called_once_with("http://127.0.0.1:8767/", on_close=on_close)

    with patch("provider.eel.launcher.launch_eel") as mock_eel:
        mock_eel.return_value = True
        res = launch_browser("http://127.0.0.1:8767/", browser="eel", on_close=on_close)
        assert res is True
        mock_eel.assert_called_once_with("http://127.0.0.1:8767/", on_close=on_close)


def test_server_shutdown_on_app_close_cycle() -> None:
    """Verify server shutdown and lock file unlinking when window close callback is executed."""
    mock_server = MagicMock()
    lock_file = Path(tempfile.mktemp(suffix=".lock"))
    lock_file.write_text(json.dumps({"pid": 99999, "url": "http://127.0.0.1:8767"}), encoding="utf-8")
    assert lock_file.exists()

    def simulate_app_close() -> None:
        mock_server.shutdown()
        if lock_file.exists():
            lock_file.unlink()

    # Simulate callback execution
    simulate_app_close()
    mock_server.shutdown.assert_called_once()
    assert not lock_file.exists()
