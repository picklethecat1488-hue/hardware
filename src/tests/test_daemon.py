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

pytestmark = pytest.mark.slow

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
    """Verify that calling daemon.py with log-path prints the correct log path."""
    import daemon

    monkeypatch.setattr("sys.argv", ["daemon.py", "log-path"])
    with pytest.raises(SystemExit) as excinfo:
        daemon.main()
    assert excinfo.value.code == 0
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


def test_daemon_spawn_tools():
    """Verify that the daemon can spawn build, config, and view tools via the client."""
    temp_sock = Path(tempfile.gettempdir()) / "test_daemon_tools.sock"
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass

    server = DaemonServer(socket_path=temp_sock)
    t = threading.Thread(target=server.run, daemon=True)
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

    client = DaemonClient(socket_path=temp_sock)

    # Test running each tool with help argument
    for tool in ["build", "config", "view"]:
        try:
            client.run(tool, ["--help"])
        except SystemExit as e:
            # Help exits client too, which is code 0
            assert e.code == 0
        except Exception as e:
            pytest.fail(f"Tool {tool} failed to run through client: {e}")

    # Stop the daemon
    try:
        with daemon_connection(temp_sock) as client_socket:
            client_socket.sendall(cbor2.dumps({RequestField.COMMAND: DaemonCommand.STOP}))
            client_socket.recv(BUFFER_SIZE)
    except Exception:
        pass

    t.join(timeout=3.0)
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass


def test_daemon_ttl_shutdown():
    """Verify that the daemon shuts down automatically after a TTL timeout."""
    temp_sock = Path(tempfile.gettempdir()) / "test_daemon_ttl.sock"
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass

    server = DaemonServer(socket_path=temp_sock)
    # Configure tiny timeouts to trigger TTL shutdown almost immediately
    server.socket_timeout = 0.1
    server.ttl_duration = 0.2

    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    # Wait for the thread to automatically terminate via TTL
    t.join(timeout=2.0)

    assert not t.is_alive(), "Daemon thread did not terminate on TTL timeout."
    assert not temp_sock.exists(), "Socket file was not cleaned up on TTL shutdown."


def test_daemon_client_propagates_tool_failure(monkeypatch):
    """Verify that client propagates tool non-zero exit codes correctly."""
    temp_sock = Path(tempfile.gettempdir()) / "test_daemon_propagate.sock"
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass

    server = DaemonServer(socket_path=temp_sock)
    t = threading.Thread(target=server.run, daemon=True)
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

    client = DaemonClient(socket_path=temp_sock)

    # Mock sys.exit to track what exit code was called
    exited = False
    exit_code = 0

    def mock_exit(code):
        nonlocal exited, exit_code
        exited = True
        exit_code = code
        raise SystemExit(code)

    import sys

    monkeypatch.setattr(sys, "exit", mock_exit)

    # Run a non-existent target to make it fail (code 1)
    with pytest.raises(SystemExit) as excinfo:
        client.run("build", ["invalid_target_xyz"])

    assert exited
    assert exit_code == 1
    assert excinfo.value.code == 1

    # Stop the daemon
    try:
        with daemon_connection(temp_sock) as client_socket:
            client_socket.sendall(cbor2.dumps({RequestField.COMMAND: DaemonCommand.STOP}))
            client_socket.recv(BUFFER_SIZE)
    except Exception:
        pass

    t.join(timeout=3.0)
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass


def test_daemon_sad_cases():
    """Verify that daemon server shuts down immediately on receiving invalid request inputs."""
    temp_sock = Path(tempfile.gettempdir()) / "test_daemon_sad.sock"
    if temp_sock.exists():
        try:
            temp_sock.unlink()
        except OSError:
            pass

    server = DaemonServer(socket_path=temp_sock)
    t = threading.Thread(target=server.run, daemon=True)
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

    # Send raw non-CBOR corrupted junk bytes
    try:
        with daemon_connection(temp_sock) as client_socket:
            client_socket.sendall(b"corrupted raw junk bytes 12345")
            client_socket.recv(1024)
    except Exception:
        pass

    # The server should break the loop and shut down automatically to prevent stale state
    t.join(timeout=3.0)
    assert not t.is_alive(), "Daemon did not shut down on corrupted request input."
    assert not temp_sock.exists(), "Socket file was not cleaned up on shutdown."
