"""Unit tests for bin/anvil remote execution, synchronization runner, and Vast.ai lifecycle in hardware."""

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.vast_manager import (
    DEFAULT_MAX_COST,
    DEFAULT_MIN_TOPS,
    build_bootstrap_script,
    load_env_file,
    provision_instance,
    prune_locks,
    record_lock,
    remove_lock,
    search_offers,
    write_env_file,
)


def test_anvil_runner_executable_and_syntax() -> None:
    """Verify bin/anvil exists, has executable permissions, and passes bash syntax validation."""
    script_path = REPO_ROOT / "bin" / "anvil"
    assert script_path.exists(), "bin/anvil runner script must exist"

    file_stat = script_path.stat()
    assert bool(file_stat.st_mode & stat.S_IXUSR), "bin/anvil must be executable"

    result = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True)
    assert result.returncode == 0, f"bin/anvil syntax error: {result.stderr}"


def test_anvil_runner_usage_without_args() -> None:
    """Verify bin/anvil without arguments prints usage instructions."""
    script_path = REPO_ROOT / "bin" / "anvil"

    result = subprocess.run([str(script_path)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "Usage: bin/anvil" in result.stdout or "Usage: bin/anvil" in result.stderr
    assert "provision" in result.stdout
    assert "bootstrap" in result.stdout
    assert "release" in result.stdout
    assert "auto-release" in result.stdout
    assert "status" in result.stdout
    assert "simulate" in result.stdout
    assert "--min-tops" in result.stdout
    assert "--max-cost" in result.stdout


def test_anvil_runner_hardware_commands_mocked(tmp_path: Path) -> None:
    """Verify bin/anvil sync, pytest, simulate, and smoke dispatch appropriate commands with proper flags."""
    script_path = REPO_ROOT / "bin" / "anvil"

    mock_bin_dir = tmp_path / "bin"
    mock_bin_dir.mkdir(parents=True, exist_ok=True)
    log_file = tmp_path / "calls.log"

    mock_ssh = mock_bin_dir / "ssh"
    mock_ssh.write_text(
        f"""#!/usr/bin/env bash
echo "MOCK_SSH: $@" >> "{log_file}"
if [[ "$*" == *"-e"* ]] || [[ "$*" == *"-f"* ]] || [[ "$*" == *"-d"* ]]; then
    exit 0
fi
exit 0
""",
        encoding="utf-8",
    )
    mock_ssh.chmod(0o755)

    mock_rsync = mock_bin_dir / "rsync"
    mock_rsync.write_text(
        f"""#!/usr/bin/env bash
echo "MOCK_RSYNC: $@" >> "{log_file}"
exit 0
""",
        encoding="utf-8",
    )
    mock_rsync.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{mock_bin_dir}:{env.get('PATH', '')}"
    env["REMOTE_HOST"] = "ssh5.vast.ai"
    env["REMOTE_PORT"] = "34567"
    env["REMOTE_USER"] = "root"
    env["REMOTE_DIR"] = "/workspace/hardware"

    # 1. Sync
    res_sync = subprocess.run([str(script_path), "sync"], env=env, capture_output=True, text=True)
    assert res_sync.returncode == 0

    # 2. Pytest
    res_pytest = subprocess.run(
        [str(script_path), "pytest", "-k", "test_mock"], env=env, capture_output=True, text=True
    )
    assert res_pytest.returncode == 0

    # 3. Simulate
    res_sim = subprocess.run([str(script_path), "simulate", "--speed", "10"], env=env, capture_output=True, text=True)
    assert res_sim.returncode == 0

    # 4. Smoke
    res_smoke = subprocess.run([str(script_path), "smoke"], env=env, capture_output=True, text=True)
    assert res_smoke.returncode == 0

    # 5. Stop
    res_stop = subprocess.run([str(script_path), "stop"], env=env, capture_output=True, text=True)
    assert res_stop.returncode == 0

    calls = log_file.read_text(encoding="utf-8")
    assert "-p 34567" in calls
    assert "root@ssh5.vast.ai" in calls
    assert "tools/view.py --speed 10" in calls
    assert "tools/smoke.py" in calls
    assert "pkill" in calls


def test_vast_manager_bootstrap_target_hardware() -> None:
    """Verify bootstrap script contains cq conda environment provisioning for hardware."""
    script = build_bootstrap_script(target="hardware")
    assert "build-essential" in script
    assert "cq" in script
    assert "cadquery" in script


def test_search_offers_filters_min_tops_and_max_cost(monkeypatch) -> None:
    """Verify search_offers rejects offers below min_tops or above max_cost."""
    mock_offers = [
        {"id": 1, "gpu_name": "GTX 1080", "total_flops": 12.0, "dph_total": 0.15},  # Low TOPS (junk)
        {"id": 2, "gpu_name": "H100 SXM", "total_flops": 700.0, "dph_total": 4.50},  # Overpriced
        {"id": 3, "gpu_name": "RTX 4090", "total_flops": 82.5, "dph_total": 0.45},  # Ideal match
        {"id": 4, "gpu_name": "RTX 3090", "total_flops": 71.0, "dph_total": 0.28},  # Ideal match
    ]

    import tools.vast_manager as vm

    monkeypatch.setattr(vm, "api_request", lambda endpoint, **kwargs: {"offers": mock_offers})

    results = search_offers(min_tops=50.0, max_cost=1.50)
    assert [o["id"] for o in results] == [3, 4]


def test_provision_instance_rejects_junk_and_overpriced_offers(monkeypatch, tmp_path: Path) -> None:
    """Verify provision_instance refuses to claim machines when only junk or overpriced hardware is available."""
    junk_offers = [
        {"id": 101, "gpu_name": "GTX 1060", "total_flops": 8.0, "dph_total": 0.10},
        {"id": 102, "gpu_name": "Tesla T4", "total_flops": 25.0, "dph_total": 0.35},
        {"id": 103, "gpu_name": "A100 80GB", "total_flops": 312.0, "dph_total": 3.80},
    ]

    import tools.vast_manager as vm

    monkeypatch.setattr(vm, "get_api_key", lambda: "mock_api_key_12345")
    monkeypatch.setattr(vm, "api_request", lambda endpoint, **kwargs: {"offers": junk_offers})

    env_file = tmp_path / ".anvil.env"
    res = provision_instance(min_tops=50.0, max_cost=1.50, env_file=env_file)
    assert "error" in res


def test_provision_instance_respects_config_and_writes_hardware_limits(monkeypatch, tmp_path: Path) -> None:
    """Verify provision_instance resolves min_tops and max_cost from env_file and records them."""
    good_offers = [
        {"id": 201, "gpu_name": "RTX 4090", "total_flops": 82.5, "dph_total": 0.42},
    ]

    import tools.vast_manager as vm

    monkeypatch.setattr(vm, "get_api_key", lambda: "mock_api_key_12345")
    monkeypatch.setattr(
        vm,
        "api_request",
        lambda endpoint, method="GET", data=None, **kwargs: (
            {"new_contract": 99999}
            if method == "PUT"
            else (
                {
                    "instances": [
                        {
                            "id": 99999,
                            "actual_status": "running",
                            "ssh_host": "ssh8.vast.ai",
                            "ssh_port": 22222,
                            "gpu_name": "RTX 4090",
                            "total_flops": 82.5,
                            "dph_total": 0.42,
                        }
                    ]
                }
                if "instances" in endpoint
                else {"offers": good_offers}
            )
        ),
    )

    env_file = tmp_path / ".anvil.env"
    write_env_file(env_file, {"MIN_TOPS": "60.0", "MAX_COST": "1.20"})

    res = provision_instance(env_file=env_file)
    assert "error" not in res
    assert res["instance_id"] == 99999

    loaded = load_env_file(env_file)
    assert loaded["VAST_INSTANCE_ID"] == "99999"
    assert loaded["MIN_TOPS"] == "60.0"
    assert loaded["MAX_COST"] == "1.20"
