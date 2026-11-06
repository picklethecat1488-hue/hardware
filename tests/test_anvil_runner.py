"""Unit tests for tools/anvil remote execution, synchronization runner, and Vast.ai lifecycle in hardware."""

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
    """Verify tools/anvil exists, has executable permissions, and passes bash syntax validation."""
    script_path = REPO_ROOT / "tools" / "anvil"
    assert script_path.exists(), "tools/anvil runner script must exist"

    file_stat = script_path.stat()
    assert bool(file_stat.st_mode & stat.S_IXUSR), "tools/anvil must be executable"

    result = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True)
    assert result.returncode == 0, f"tools/anvil syntax error: {result.stderr}"


def test_anvil_runner_usage_without_args() -> None:
    """Verify tools/anvil without arguments prints usage instructions."""
    script_path = REPO_ROOT / "tools" / "anvil"

    result = subprocess.run([str(script_path)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "Usage: tools/anvil" in result.stdout or "Usage: tools/anvil" in result.stderr
    assert "provision" in result.stdout
    assert "bootstrap" in result.stdout
    assert "release" in result.stdout
    assert "auto-release" in result.stdout
    assert "status" in result.stdout
    assert "simulate" in result.stdout
    assert "--min-tops" in result.stdout
    assert "--max-cost" in result.stdout


def test_anvil_runner_hardware_commands_mocked(tmp_path: Path) -> None:
    """Verify tools/anvil sync, pytest, simulate, and smoke dispatch appropriate commands with proper flags."""
    script_path = REPO_ROOT / "tools" / "anvil"

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
    assert "ruff" in script
    assert "build123d" in script


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
    monkeypatch.setattr(vm, "ensure_ssh_key_registered", lambda: True)
    monkeypatch.setattr(vm, "probe_ssh_connection", lambda h, p, **kw: True)
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
    monkeypatch.setattr(vm, "ensure_ssh_key_registered", lambda: True)
    monkeypatch.setattr(vm, "probe_ssh_connection", lambda h, p, **kw: True)
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


def test_api_request_routes_instances_list_to_v1(monkeypatch) -> None:
    """Verify api_request routes instances/ to v1 API and other endpoints to v0 API."""
    import urllib.request
    import tools.vast_manager as vm

    captured_urls = []

    class MockResponse:
        def __init__(self, data=b"{}"):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def read(self):
            return self.data

    def mock_urlopen(req, timeout=30):
        captured_urls.append(req.full_url)
        return MockResponse(b'{"success": true, "instances": []}')

    monkeypatch.setattr(vm, "get_api_key", lambda: "mock_key")
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    # 1. Instances listing -> v1
    vm.api_request("instances/")
    assert any("api/v1/instances" in u for u in captured_urls)

    # 2. Single instance query -> v0
    captured_urls.clear()
    vm.api_request("instances/555/")
    assert any("api/v0/instances/555" in u for u in captured_urls)

    # 3. Bundles query -> v0
    captured_urls.clear()
    vm.api_request("bundles/?q=test")
    assert any("api/v0/bundles" in u for u in captured_urls)


def test_check_instance_failure_patterns() -> None:
    """Verify check_instance_failure detects Docker daemon timeouts and fatal container states."""
    from tools.vast_manager import check_instance_failure

    # 1. User reported Docker registry timeout
    user_err = (
        'Error response from daemon: Head "https://registry-1.docker.io/v2/library/ubuntu/manifests/22.04": '
        'Get "https://auth.docker.io/token?scope=repository%3Alibrary%2Fubuntu%3Apull&service=registry.docker.io": '
        "net/http: request canceled while waiting for connection (Client.Timeout exceeded while awaiting headers)"
    )
    assert check_instance_failure({"actual_status": "loading", "status_msg": user_err}) == user_err

    # 2. Fatal status
    assert "offline" in str(check_instance_failure({"actual_status": "offline", "status_msg": "Host down"}))
    assert "failed" in str(check_instance_failure({"actual_status": "failed", "status_msg": "Boot failed"}))

    # 3. Healthy instance returns None
    assert check_instance_failure({"actual_status": "running", "cur_state": "running", "status_msg": None}) is None


def test_provision_instance_retries_and_cleans_up_on_daemon_error(monkeypatch, tmp_path: Path) -> None:
    """Verify provision_instance auto-releases broken instances on daemon pull error and retries with next host."""
    import tools.vast_manager as vm

    offers = [
        {"id": 1001, "machine_id": 133175, "gpu_name": "RTX 4090", "total_flops": 80.0, "dph_total": 0.30},
        {"id": 1002, "machine_id": 144200, "gpu_name": "RTX 4090", "total_flops": 80.0, "dph_total": 0.35},
    ]

    deleted_instances = []
    created_offers = []

    def mock_api_request(endpoint, method="GET", data=None, **kwargs):
        if method == "PUT" and "asks/" in endpoint:
            oid = int(endpoint.split("/")[1])
            created_offers.append(oid)
            if oid == 1001:
                return {"new_contract": 59343680}
            else:
                return {"new_contract": 59343681}
        elif method == "DELETE" and "instances/" in endpoint:
            iid = int(endpoint.split("/")[1])
            deleted_instances.append(iid)
            return {"success": True}
        elif "instances" in endpoint:
            # If asking about instance 59343680, report daemon timeout
            # If asking about instance 59343681, report healthy running state
            return {
                "instances": [
                    {
                        "id": 59343680,
                        "machine_id": 133175,
                        "actual_status": "loading",
                        "status_msg": 'Error response from daemon: Head "https://registry-1.docker.io/v2/": Client.Timeout exceeded',
                    },
                    {
                        "id": 59343681,
                        "machine_id": 144200,
                        "actual_status": "running",
                        "status_msg": None,
                        "ssh_host": "ssh3.vast.ai",
                        "ssh_port": 22233,
                    },
                ]
            }
        elif "bundles/" in endpoint:
            return {"offers": offers}
        return {}

    monkeypatch.setattr(vm, "get_api_key", lambda: "mock_api_key")
    monkeypatch.setattr(vm, "ensure_ssh_key_registered", lambda: True)
    monkeypatch.setattr(vm, "probe_ssh_connection", lambda h, p, **kw: True)
    monkeypatch.setattr(vm, "api_request", mock_api_request)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    env_file = tmp_path / ".anvil.env"
    res = provision_instance(min_tops=50.0, max_cost=1.50, env_file=env_file)

    assert "error" not in res
    assert res["instance_id"] == 59343681
    assert 59343680 in deleted_instances, "Broken instance must be destroyed immediately"
    assert created_offers == [1001, 1002], "Must try first offer, then retry with next offer"

    saved_env = vm.load_env_file(env_file)
    assert saved_env["VAST_INSTANCE_ID"] == "59343681"
    assert saved_env["REMOTE_HOST"] == "ssh3.vast.ai"
    assert saved_env["REMOTE_PORT"] == "22233"


def test_release_instance_cleans_unreferenced_instances(monkeypatch, tmp_path: Path) -> None:
    """Verify release_instance destroys orphaned account instances when ~/.anvil.env is unconfigured."""
    import tools.vast_manager as vm

    deleted_instances = []

    def mock_api_request(endpoint, method="GET", **kwargs):
        if method == "DELETE" and "instances/" in endpoint:
            iid = int(endpoint.split("/")[1])
            deleted_instances.append(iid)
            return {"success": True}
        elif "instances" in endpoint:
            return {
                "instances": [
                    {"id": 88888, "actual_status": "loading"},
                ]
            }
        return {}

    monkeypatch.setattr(vm, "get_api_key", lambda: "mock_key")
    monkeypatch.setattr(vm, "api_request", mock_api_request)

    env_file = tmp_path / ".anvil.env"
    assert not env_file.exists()

    success = vm.release_instance(env_file=env_file)
    assert success is True
    assert 88888 in deleted_instances


def test_probe_ssh_connection(monkeypatch) -> None:
    """Verify probe_ssh_connection executes non-interactive test and validates output."""
    import subprocess
    import tools.vast_manager as vm

    class MockResult:
        def __init__(self, code, out):
            self.returncode = code
            self.stdout = out

    # 1. Success case
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: MockResult(0, "READY\n"))
    assert vm.probe_ssh_connection("ssh.vast.ai", 12345) is True

    # 2. Failure case
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: MockResult(255, "Connection refused\n"))
    assert vm.probe_ssh_connection("ssh.vast.ai", 12345) is False
