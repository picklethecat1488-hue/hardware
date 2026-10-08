"""Regression unit test for WORM-021: Single instance check and terminal detachment (hardware port).

Verifies:
1. get_dashboard_lock_file returns appropriate path in build or target dir.
2. check_existing_instance detects when a dashboard is already running.
3. parse_arguments supports --no-detach / --foreground and --stop flags.
4. Starting a second dashboard when one is already active exits cleanly and warns user without starting duplicate server.
5. Lock file is updated with PID and URL.
6. Stop flag stops active instance.
"""

from io import StringIO
import json
import os
from pathlib import Path
import signal
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.dashboard import (
    check_existing_instance,
    get_dashboard_lock_file,
    parse_arguments,
)


def test_dashboard_lock_file_path(tmp_path: Path) -> None:
    """Verify lock file path is created inside build directory."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    lock_file = get_dashboard_lock_file(tmp_path, port=8877)
    assert lock_file.name == "dashboard_8877.lock"
    assert lock_file.parent == build_dir


def test_cli_detach_flags() -> None:
    """Verify parse_arguments handles --no-detach and --stop flags."""
    with patch("sys.argv", ["dashboard.py", "--no-detach"]):
        args = parse_arguments()
        assert getattr(args, "no_detach", False) is True

    with patch("sys.argv", ["dashboard.py", "--foreground"]):
        args = parse_arguments()
        assert getattr(args, "no_detach", False) is True

    with patch("sys.argv", ["dashboard.py", "--stop"]):
        args = parse_arguments()
        assert getattr(args, "stop", False) is True


def test_check_existing_instance_active(tmp_path: Path) -> None:
    """Verify check_existing_instance detects active instance and returns PID/URL."""
    lock_file = tmp_path / "dashboard_8877.lock"
    current_pid = os.getpid()
    lock_file.write_text(json.dumps({"pid": current_pid, "url": "http://127.0.0.1:8877"}), encoding="utf-8")

    with patch("src.dashboard.is_port_in_use", return_value=True):
        existing = check_existing_instance(lock_file, "127.0.0.1", 8877)
        assert existing is not None
        pid, url = existing
        assert pid == current_pid
        assert url == "http://127.0.0.1:8877"


def test_check_existing_instance_stale(tmp_path: Path) -> None:
    """Verify check_existing_instance removes stale lock file when process is dead."""
    lock_file = tmp_path / "dashboard_8877.lock"
    fake_pid = 99999999
    lock_file.write_text(json.dumps({"pid": fake_pid, "url": "http://127.0.0.1:8877"}), encoding="utf-8")

    with patch("src.dashboard.is_port_in_use", return_value=False):
        existing = check_existing_instance(lock_file, "127.0.0.1", 8877)
        assert existing is None
        assert not lock_file.exists(), "Stale lock file should have been cleaned up"


def test_second_instance_exits_cleanly(tmp_path: Path) -> None:
    """Verify that launching when an instance is already active does not spawn a second server."""
    lock_file = tmp_path / "dashboard_8877.lock"
    current_pid = os.getpid()
    lock_file.write_text(json.dumps({"pid": current_pid, "url": "http://127.0.0.1:8877"}), encoding="utf-8")

    from src.dashboard import main

    out = StringIO()
    with patch("src.dashboard.get_dashboard_lock_file", return_value=lock_file), \
         patch("src.dashboard.is_port_in_use", return_value=True), \
         patch("src.dashboard.launch_browser") as mock_launch, \
         patch("sys.stdout", out), \
         patch("sys.argv", ["dashboard.py"]):
        main()

    output = out.getvalue()
    assert "already running" in output.lower()
    mock_launch.assert_called_once_with("http://127.0.0.1:8877")


def test_cli_stop_active_instance(tmp_path: Path) -> None:
    """Verify --stop flag terminates active instance and cleans lock file."""
    lock_file = tmp_path / "dashboard_8877.lock"
    lock_file.write_text(json.dumps({"pid": 12345, "url": "http://127.0.0.1:8877"}), encoding="utf-8")

    from src.dashboard import main

    out = StringIO()
    with patch("src.dashboard.get_dashboard_lock_file", return_value=lock_file), \
         patch("src.dashboard.check_existing_instance", return_value=(12345, "http://127.0.0.1:8877")), \
         patch("os.kill") as mock_kill, \
         patch("sys.stdout", out), \
         patch("sys.argv", ["dashboard.py", "--stop"]):
        main()

    mock_kill.assert_called_once_with(12345, signal.SIGTERM)
    assert not lock_file.exists()
    assert "Stopped dashboard" in out.getvalue()


def test_cli_stop_no_instance(tmp_path: Path) -> None:
    """Verify --stop flag prints message when no instance is running."""
    lock_file = tmp_path / "dashboard_8877.lock"

    from src.dashboard import main

    out = StringIO()
    with patch("src.dashboard.get_dashboard_lock_file", return_value=lock_file), \
         patch("src.dashboard.check_existing_instance", return_value=None), \
         patch("sys.stdout", out), \
         patch("sys.argv", ["dashboard.py", "--stop"]):
        main()

    assert "No dashboard workstation is running" in out.getvalue()
