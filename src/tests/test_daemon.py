"""Unit and integration tests for the background build daemon."""

import cbor2
import os
import socket
import tempfile
import threading
import time
from pathlib import Path
import pytest
from pydantic import ValidationError

from daemon import (
    DaemonServer,
    DaemonClient,
    daemon_connection,
    DaemonCommand,
    RequestField,
    BUFFER_SIZE,
)


def test_daemon_connection_lifecycle():
    """Verify socket connection fails cleanly when no daemon is active."""
    temp_sock = Path(tempfile.gettempdir()) / "test_daemon_none.sock"
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass

    with pytest.raises((ConnectionRefusedError, FileNotFoundError, OSError)):
        with daemon_connection(temp_sock):
            pass


def test_daemon_server_start_stop():
    """Start the daemon in a background thread and verify basic operations."""
    temp_sock = Path(tempfile.gettempdir()) / "test_daemon_start_stop.sock"
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass

    server = DaemonServer(socket_path=temp_sock)

    # Start the daemon inside a background thread
    t = threading.Thread(target=server.run)
    t.daemon = True
    t.start()

    # Wait for the UDS socket to be created and accepting connections
    socket_ready = False
    for _ in range(30):
        try:
            with daemon_connection(temp_sock):
                socket_ready = True
                break
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            time.sleep(0.1)

    assert socket_ready, "Daemon did not start listening in time."

    # Send a status request and verify response
    try:
        with daemon_connection(temp_sock) as client_socket:
            client_socket.sendall(cbor2.dumps({RequestField.COMMAND: DaemonCommand.STATUS}))
            response = client_socket.recv(BUFFER_SIZE).decode("utf-8")
            assert "is running" in response
    except Exception as e:
        pytest.fail(f"Failed to communicate with daemon: {e}")

    # Send a stop request and verify shutdown
    try:
        with daemon_connection(temp_sock) as client_socket:
            client_socket.sendall(cbor2.dumps({RequestField.COMMAND: DaemonCommand.STOP}))
            response = client_socket.recv(BUFFER_SIZE).decode("utf-8")
            assert "stopping" in response
    except Exception as e:
        pytest.fail(f"Failed to send stop command to daemon: {e}")

    # Wait for daemon thread to join and clean up
    t.join(timeout=3.0)
    assert not temp_sock.exists(), "Socket file was not cleaned up on exit."


def test_daemon_client_local_fallback(monkeypatch):
    """Verify client correctly falls back to in-process execution."""
    temp_sock = Path(tempfile.gettempdir()) / "test_daemon_fallback.sock"
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass

    client = DaemonClient(socket_path=temp_sock)

    local_runs = []

    def mock_run_locally(tool_name, argv):
        local_runs.append((tool_name, argv))

    monkeypatch.setattr(client, "_run_locally", mock_run_locally)

    # Run with --no-daemon (should directly run locally)
    client.run("build", ["--no-daemon", "cat_fountain/bowl"])
    assert local_runs == [("build", ["cat_fountain/bowl"])]


def test_daemon_pydantic_validation():
    """Verify validation decorators catch incorrect argument types."""
    # DaemonClient method validations
    client = DaemonClient()

    with pytest.raises(ValidationError):
        # tool_name must be a string (passing int)
        client.run(12345, ["argv"])

    with pytest.raises(ValidationError):
        # argv must be a List (passing string)
        client.run("build", "not_a_list")

    # DaemonServer validations
    with pytest.raises(ValidationError):
        # socket_path must be a Path object (passing int)
        DaemonServer(socket_path=12345)


def test_daemon_log_path(capsys, monkeypatch):
    """Verify that calling daemon.py with --log-path prints the correct log path."""
    import daemon

    monkeypatch.setattr("sys.argv", ["daemon.py", "--log-path"])
    daemon.main()
    captured = capsys.readouterr()
    assert str(daemon.LOG_PATH) in captured.out.strip()


def test_daemon_client_connection_failure_exits(monkeypatch):
    """Verify that client exits with code 1 when it cannot connect to the daemon."""
    import sys

    temp_sock = Path(tempfile.gettempdir()) / "test_daemon_fail.sock"
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass

    client = DaemonClient(socket_path=temp_sock)

    exited = False

    def mock_exit(code):
        nonlocal exited
        exited = True
        raise SystemExit(code)

    monkeypatch.setattr(sys, "exit", mock_exit)

    with pytest.raises(SystemExit) as excinfo:
        client.run("build", ["cat_fountain/bowl"])

    assert exited
    assert excinfo.value.code == 1
