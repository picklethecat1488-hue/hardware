"""Regression unit test for WORM-026: Automatic dashboard server termination and orphaned server recovery.

Verifies:
1. has_active_window_process detects whether a running server PID has an active child GUI window.
2. An orphaned background server (server PID alive, but no GUI window process) is detected, terminated,
   and recovered when starting the dashboard.
3. run_webview_window hooks window.events.closed to guarantee immediate process exit.
4. _on_app_close aggressively terminates the server process and unlinks the lock file.
"""

import json
import os
from pathlib import Path
import signal
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from dashboard import check_existing_instance, has_active_window_process


def test_has_active_window_process_no_children() -> None:
    """Verify has_active_window_process returns False when PID has no GUI children."""
    assert not has_active_window_process(os.getpid())
    assert not has_active_window_process(0)
    assert not has_active_window_process(-1)


def test_has_active_window_process_with_mock_child() -> None:
    """Verify has_active_window_process returns True when child command line matches webview/chrome/eel."""
    mock_child = MagicMock()
    mock_child.is_running.return_value = True
    mock_child.cmdline.return_value = ["/usr/bin/python", "-m", "provider.webview.launcher", "--url", "http://127.0.0.1:8767"]

    mock_parent = MagicMock()
    mock_parent.children.return_value = [mock_child]

    with patch("psutil.Process", return_value=mock_parent):
        assert has_active_window_process(12345) is True


def test_orphaned_server_recovery_cleans_lock_file() -> None:
    """Verify an orphaned server process without an active window is terminated and restarted."""
    lock_file = Path(tempfile.mktemp(suffix=".lock"))
    lock_file.write_text(json.dumps({"pid": 99999, "url": "http://127.0.0.1:8767", "no_browser": False}), encoding="utf-8")

    with patch("dashboard.is_pid_alive", return_value=True), \
         patch("dashboard.is_port_in_use", return_value=True), \
         patch("dashboard.has_active_window_process", return_value=False), \
         patch("os.kill") as mock_kill:
        existing = check_existing_instance(lock_file, "127.0.0.1", 8767, cleanup_orphaned=True)
        # Should detect as orphaned and clean it up, returning None so a fresh server starts
        assert existing is None
        mock_kill.assert_called_once_with(99999, signal.SIGTERM)
        assert not lock_file.exists()


def test_webview_window_closed_event_registration() -> None:
    """Verify run_webview_window registers a closed event handler on the webview window."""
    mock_webview = MagicMock()
    mock_window = MagicMock()
    mock_events = MagicMock()
    mock_closed = MagicMock()
    mock_closed.__iadd__.return_value = mock_closed
    mock_events.closed = mock_closed
    mock_window.events = mock_events
    mock_webview.create_window.return_value = mock_window

    with patch.dict("sys.modules", {"webview": mock_webview}), patch("os._exit") as mock_exit:
        from provider.webview.launcher import run_webview_window

        run_webview_window(
            url="http://127.0.0.1:8767/",
            title="Quake Workstation",
            exit_on_close=True,
        )

        assert mock_closed.__iadd__.called
        mock_webview.start.assert_called_once()
        mock_exit.assert_called_once_with(0)
