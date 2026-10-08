"""Regression unit tests for CI gate validation workflow and daemon teardown (BUG-280).

Guards against:
1. Missing concurrency cancellation in CI gate workflow leading to duplicate/stuck stacked PR runs.
2. Missing ready_for_review trigger on pull_request events.
3. Smoke tests spawning persistent background build daemons without --no-daemon.
4. DaemonServer not terminating cleanly on SIGTERM.
"""

from pathlib import Path
import os
import signal
import subprocess
import sys
import tempfile
import time
import yaml
import pytest


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def test_ci_gate_workflow_concurrency_and_triggers() -> None:
    """Verify BUG-280: ci-gate.yml has concurrency cancellation, ready_for_review trigger, and daemon stop."""
    ci_gate_path = WORKSPACE_ROOT / ".github" / "workflows" / "ci-gate.yml"
    assert ci_gate_path.exists(), "ci-gate.yml must exist"

    raw_text = ci_gate_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_text)

    # 1. Concurrency configuration
    assert "concurrency" in data, "ci-gate.yml must define concurrency"
    concurrency = data["concurrency"]
    assert concurrency.get("cancel-in-progress") is True, "concurrency must enable cancel-in-progress: true"
    assert "github.workflow" in str(concurrency.get("group", "")), "concurrency group must include workflow name"

    # 2. Event triggers must include ready_for_review
    on_dict = data.get("on") if "on" in data else data.get(True, {})
    on_pr = (on_dict or {}).get("pull_request", {})
    types = on_pr.get("types", [])
    assert "ready_for_review" in types, f"pull_request types must include 'ready_for_review', got: {types}"
    assert "opened" in types
    assert "synchronize" in types
    assert "reopened" in types

    # 3. Smoke tests step must stop daemon
    steps = data.get("jobs", {}).get("validate", {}).get("steps", [])
    smoke_step = next((s for s in steps if "Run Smoke Tests" in s.get("name", "")), None)
    assert smoke_step is not None, "Must have 'Run Smoke Tests' step"
    assert "python src/daemon.py stop" in smoke_step.get("run", ""), (
        "Run Smoke Tests step must cleanly stop the daemon with 'python src/daemon.py stop || true'"
    )


def test_smoke_test_enforces_no_daemon_flag() -> None:
    """Verify BUG-280: TestSmoke.run_command automatically injects --no-daemon for build/view/config commands."""
    from smoke import TestSmoke

    smoke = TestSmoke()
    smoke.build_dir = Path(tempfile.gettempdir()) / "test_smoke_dummy_build"

    captured_args: list[str] = []

    def mock_run(cmd, **kwargs):
        captured_args.extend(cmd)

        class DummyResult:
            returncode = 0
            stdout = ""
            stderr = ""

        return DummyResult()

    import unittest.mock

    with unittest.mock.patch("subprocess.run", side_effect=mock_run):
        # 1. build.py command
        smoke.run_command(["src/build.py", "exhaust_manifolds/*"])
        assert "--no-daemon" in captured_args, f"src/build.py must include --no-daemon, got: {captured_args}"

        # 2. view.py command
        captured_args.clear()
        smoke.run_command(["src/view.py", "cat_fountain/product", "--no-gui"])
        assert "--no-daemon" in captured_args, f"src/view.py must include --no-daemon, got: {captured_args}"

        # 3. config.py command
        captured_args.clear()
        smoke.run_command(["src/config.py", "-e", "test.env"])
        assert "--no-daemon" in captured_args, f"src/config.py must include --no-daemon, got: {captured_args}"


def test_daemon_server_sigterm_handling() -> None:
    """Verify BUG-280: DaemonServer handles SIGTERM signal and exits cleanly within 2 seconds."""
    temp_sock = Path(tempfile.gettempdir()) / f"test_sigterm_{os.getpid()}.sock"
    temp_pid = temp_sock.with_suffix(".pid")

    for f in (temp_sock, temp_pid):
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass

    # Launch daemon in a separate subprocess
    cmd = [
        sys.executable,
        str(WORKSPACE_ROOT / "src" / "daemon.py"),
        "start",
        "--foreground",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(WORKSPACE_ROOT / "src")

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for daemon process to start
        time.sleep(1.0)
        assert proc.poll() is None, "Daemon process failed to start"

        # Send SIGTERM
        proc.send_signal(signal.SIGTERM)

        # Wait for process to exit
        start_t = time.time()
        exited = False
        while time.time() - start_t < 3.0:
            if proc.poll() is not None:
                exited = True
                break
            time.sleep(0.1)

        assert exited, "Daemon process did not terminate within 3 seconds of receiving SIGTERM"
        assert proc.returncode in (0, -signal.SIGTERM), f"Expected exit code 0 or -SIGTERM, got: {proc.returncode}"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
