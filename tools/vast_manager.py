#!/usr/bin/env python3
"""Vast.ai Cloud Instance Lifecycle and Resource Manager for Anvil.

Provides instance provisioning, remote bootstrapping, SSH discovery,
activity lock tracking, and Close of Business (COB) auto-release.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

VAST_API_BASE = "https://cloud.vast.ai/api/v0"
HOME_DIR = Path.home()
DEFAULT_GLOBAL_ENV_FILE = HOME_DIR / ".anvil.env"
DEFAULT_LOCK_FILE = HOME_DIR / ".anvil.lock"
DEFAULT_VAST_KEY_FILE = HOME_DIR / ".vast_api_key"
DEFAULT_UBUNTU_IMAGE = "ubuntu:22.04"
DEFAULT_DISK_SIZE_GB = 40
DEFAULT_COB_HOUR = 18  # 18:00 (6:00 PM)
DEFAULT_IDLE_TIMEOUT_SEC = 1800  # 30 minutes


def get_api_key() -> Optional[str]:
    """Retrieve Vast.ai API key from environment, key file, or anvil.env."""
    if os.environ.get("VAST_API_KEY"):
        return os.environ["VAST_API_KEY"].strip()
    if DEFAULT_VAST_KEY_FILE.exists():
        key = DEFAULT_VAST_KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    env_vars = load_env_file(DEFAULT_GLOBAL_ENV_FILE)
    if "VAST_API_KEY" in env_vars and env_vars["VAST_API_KEY"].strip():
        return env_vars["VAST_API_KEY"].strip()
    return None


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Parse bash-style KEY=VALUE or KEY="VALUE" environment file."""
    env: Dict[str, str] = {}
    if not env_path.exists():
        return env
    try:
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                env[key] = val
    except Exception:
        pass
    return env


def write_env_file(env_path: Path, updates: Dict[str, Optional[str]]) -> None:
    """Atomically update environment file, preserving unedited keys and comments."""
    existing = load_env_file(env_path)
    for k, v in updates.items():
        if v is None:
            existing.pop(k, None)
        else:
            existing[k] = v

    lines = [
        "# ==============================================================================",
        "# Vast.ai Shared Instance Configuration (Managed by bin/anvil)",
        f"# Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
    ]
    for k, v in sorted(existing.items()):
        lines.append(f'{k}="{v}"')
    lines.append("")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = env_path.with_suffix(".tmp")
    temp_file.write_text("\n".join(lines), encoding="utf-8")
    temp_file.replace(env_path)


def api_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Execute authenticated HTTP request to Vast.ai REST API."""
    key = api_key or get_api_key()
    if not key:
        return {
            "error": "VAST_API_KEY is not configured. Set VAST_API_KEY environment variable or write to ~/.vast_api_key"
        }

    url = f"{VAST_API_BASE}/{endpoint.lstrip('/')}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {key}",
    }

    url_parts = list(urllib.parse.urlparse(url))
    query = dict(urllib.parse.parse_qsl(url_parts[4]))
    query["api_key"] = key
    url_parts[4] = urllib.parse.urlencode(query)
    full_url = urllib.parse.urlunparse(url_parts)

    body_bytes = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(full_url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            resp_body = response.read().decode("utf-8")
            if not resp_body:
                return {"success": True}
            return json.loads(resp_body)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return {"error": f"HTTP {e.code}: {err_msg or e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def search_offers(
    gpu_name: Optional[str] = None,
    min_disk_gb: int = DEFAULT_DISK_SIZE_GB,
    max_dph: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Search available rentable machines on Vast.ai."""
    query: Dict[str, Any] = {
        "rentable": {"eq": True},
        "disk_space": {"gte": min_disk_gb},
        "verified": {"eq": True},
    }
    if gpu_name:
        query["gpu_name"] = {"eq": gpu_name}
    if max_dph is not None:
        query["dph_total"] = {"lte": max_dph}

    q_param = urllib.parse.quote(json.dumps(query))
    res = api_request(f"bundles/?q={q_param}")
    if "offers" in res and isinstance(res["offers"], list):
        return res["offers"]
    if isinstance(res, list):
        return res
    return []


def get_instance_info(instance_id: int) -> Dict[str, Any]:
    """Retrieve status and connection parameters for a specific instance."""
    res = api_request(f"instances/{instance_id}/")
    if "instances" in res and isinstance(res["instances"], list) and res["instances"]:
        return res["instances"][0]
    if "error" not in res and "id" in res:
        return res
    res_all = api_request("instances/")
    if "instances" in res_all and isinstance(res_all["instances"], list):
        for inst in res_all["instances"]:
            if str(inst.get("id")) == str(instance_id):
                return inst
    return res


def provision_instance(
    image: str = DEFAULT_UBUNTU_IMAGE,
    disk_gb: int = DEFAULT_DISK_SIZE_GB,
    offer_id: Optional[int] = None,
    gpu: Optional[str] = None,
    max_dph: Optional[float] = None,
    env_file: Path = DEFAULT_GLOBAL_ENV_FILE,
) -> Dict[str, Any]:
    """Provision a new instance on Vast.ai and write connection details to ~/.anvil.env."""
    api_key = get_api_key()
    if not api_key:
        print("❌ Error: Vast.ai API key not found.", file=sys.stderr)
        print("Please export VAST_API_KEY='<key>' or save your key in ~/.vast_api_key", file=sys.stderr)
        return {"error": "Missing API key"}

    selected_offer = offer_id
    if not selected_offer:
        print(f"🔍 Searching available Vast.ai offers (disk >= {disk_gb}GB, image: {image})...")
        offers = search_offers(gpu_name=gpu, min_disk_gb=disk_gb, max_dph=max_dph)
        if not offers:
            print("⚠️ No matching offers found with strict criteria; retrying unverified/any GPU...", file=sys.stderr)
            q_param = urllib.parse.quote(json.dumps({"rentable": {"eq": True}, "disk_space": {"gte": disk_gb}}))
            res = api_request(f"bundles/?q={q_param}")
            offers = res.get("offers", []) if isinstance(res, dict) else res

        if not offers:
            print("❌ No rentable machines available matching criteria.", file=sys.stderr)
            return {"error": "No offers available"}

        # Sort by total dollars-per-hour
        offers.sort(key=lambda o: float(o.get("dph_total", 999.0)))
        chosen = offers[0]
        selected_offer = chosen.get("id") or chosen.get("ask_id")
        gpu_model = chosen.get("gpu_name", "GPU/CPU")
        dph = chosen.get("dph_total", 0.0)
        print(f"🎯 Selected offer #{selected_offer}: {gpu_model} @ ${dph:.3f}/hr")

    print(f"🚀 Creating Vast.ai instance from offer #{selected_offer}...")
    payload = {
        "image": image,
        "disk": disk_gb,
        "runtype": "ssh",
    }
    create_res = api_request(f"asks/{selected_offer}/", method="PUT", data=payload)
    if "error" in create_res:
        print(f"❌ Failed to create instance: {create_res['error']}", file=sys.stderr)
        return create_res

    instance_id = create_res.get("new_contract") or create_res.get("instance_id")
    if not instance_id:
        # Check if list of instances has our new rental
        inst_list = api_request("instances/").get("instances", [])
        if inst_list:
            instance_id = inst_list[-1].get("id")

    print(f"⏳ Waiting for instance #{instance_id} to enter 'running' state and establish SSH...")
    ssh_host = None
    ssh_port = None
    start_time = time.time()
    while time.time() - start_time < 300:  # 5 min timeout
        time.sleep(6)
        info = get_instance_info(instance_id)
        status = info.get("actual_status") or info.get("status_msg") or "unknown"
        cur_host = info.get("ssh_host")
        cur_port = info.get("ssh_port")
        print(f"   Status: {status} | SSH: {cur_host}:{cur_port}")
        if cur_host and cur_port and (status == "running" or status == "loaded"):
            ssh_host = cur_host
            ssh_port = str(cur_port)
            break

    if not ssh_host or not ssh_port:
        print("⚠️ Instance provisioned but SSH port mapping not ready yet.", file=sys.stderr)
        print(f"Instance ID: {instance_id}. Check status via 'bin/anvil status'.", file=sys.stderr)
    else:
        print(f"✅ Instance is running! SSH connection: ssh -p {ssh_port} root@{ssh_host}")

    # Write connection details to ~/.anvil.env
    env_updates: Dict[str, Optional[str]] = {
        "VAST_INSTANCE_ID": str(instance_id) if instance_id else None,
        "REMOTE_HOST": ssh_host or "ssh.vast.ai",
        "REMOTE_PORT": ssh_port or "22",
        "REMOTE_USER": "root",
        "REMOTE_IMAGE": image,
    }
    write_env_file(env_file, env_updates)
    print(f"📝 Updated shared configuration: {env_file}")

    return {
        "instance_id": instance_id,
        "ssh_host": ssh_host,
        "ssh_port": ssh_port,
        "image": image,
        "env_file": str(env_file),
    }


def release_instance(
    instance_id: Optional[int] = None,
    env_file: Path = DEFAULT_GLOBAL_ENV_FILE,
    lock_file: Path = DEFAULT_LOCK_FILE,
) -> bool:
    """Destroy rented instance on Vast.ai, update ~/.anvil.env, and clear lock file."""
    env = load_env_file(env_file)
    target_id = instance_id or env.get("VAST_INSTANCE_ID")
    if not target_id:
        print("⚠️ No active Vast.ai instance ID found in configuration.", file=sys.stderr)
        return False

    print(f"🛑 Destroying Vast.ai instance #{target_id}...")
    api_res = api_request(f"instances/{target_id}/", method="DELETE")
    if "error" in api_res:
        print(f"⚠️ Warning from Vast.ai API: {api_res['error']}", file=sys.stderr)

    # Clean up environment variables
    write_env_file(
        env_file,
        {
            "VAST_INSTANCE_ID": None,
            "REMOTE_HOST": "anvil",
            "REMOTE_PORT": None,
            "REMOTE_USER": None,
        },
    )

    # Clean lock file
    if lock_file.exists():
        try:
            lock_file.unlink()
        except Exception:
            pass

    print(f"✅ Successfully released instance #{target_id} and reset {env_file}.")
    return True


def record_lock(
    command_str: str,
    repo_name: str,
    pid: Optional[int] = None,
    lock_file: Path = DEFAULT_LOCK_FILE,
) -> None:
    """Register active process PID in ~/.anvil.lock."""
    pid = pid or os.getpid()
    ts = int(time.time())
    record = f"{pid} {ts} {repo_name} {command_str}\n"
    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_file, "a", encoding="utf-8") as f:
            f.write(record)
    except Exception as e:
        print(f"⚠️ Failed to register lock entry: {e}", file=sys.stderr)


def remove_lock(pid: Optional[int] = None, lock_file: Path = DEFAULT_LOCK_FILE) -> None:
    """Remove active process PID from ~/.anvil.lock."""
    pid = pid or os.getpid()
    if not lock_file.exists():
        return
    try:
        lines = lock_file.read_text(encoding="utf-8").splitlines()
        remaining = [line for line in lines if line.strip() and not line.startswith(f"{pid} ")]
        if remaining:
            lock_file.write_text("\n".join(remaining) + "\n", encoding="utf-8")
        else:
            lock_file.unlink()
    except Exception:
        pass


def prune_locks(lock_file: Path = DEFAULT_LOCK_FILE) -> List[Dict[str, Any]]:
    """Inspect and prune dead PIDs from ~/.anvil.lock, returning list of active jobs."""
    if not lock_file.exists():
        return []

    active_jobs: List[Dict[str, Any]] = []
    lines = lock_file.read_text(encoding="utf-8").splitlines()
    remaining_lines: List[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 3)
        if len(parts) < 3:
            continue
        pid_str, ts_str, repo = parts[0], parts[1], parts[2]
        cmd = parts[3] if len(parts) > 3 else ""

        try:
            pid = int(pid_str)
            ts = int(ts_str)
        except ValueError:
            continue

        # Check if process is still running locally
        is_running = False
        try:
            os.kill(pid, 0)
            is_running = True
        except OSError:
            is_running = False

        if is_running:
            remaining_lines.append(line)
            active_jobs.append(
                {
                    "pid": pid,
                    "timestamp": ts,
                    "age_sec": int(time.time() - ts),
                    "repo": repo,
                    "command": cmd,
                }
            )

    if remaining_lines:
        lock_file.write_text("\n".join(remaining_lines) + "\n", encoding="utf-8")
    else:
        try:
            lock_file.unlink()
        except Exception:
            pass

    return active_jobs


def auto_release(
    force: bool = False,
    cob_hour: int = DEFAULT_COB_HOUR,
    idle_timeout_sec: int = DEFAULT_IDLE_TIMEOUT_SEC,
    env_file: Path = DEFAULT_GLOBAL_ENV_FILE,
    lock_file: Path = DEFAULT_LOCK_FILE,
) -> bool:
    """Evaluate activity lock and release instance if idle or past Close of Business (COB)."""
    env = load_env_file(env_file)
    instance_id = env.get("VAST_INSTANCE_ID")
    if not instance_id:
        print("ℹ️ No active Vast.ai instance configured; nothing to auto-release.")
        return False

    active_jobs = prune_locks(lock_file)
    if active_jobs:
        print(f"🔒 Instance #{instance_id} is currently in use by {len(active_jobs)} active job(s):")
        for job in active_jobs:
            print(f"   - PID {job['pid']} ({job['repo']}): {job['command']} (started {job['age_sec']}s ago)")
        print("⏭️ Skipping auto-release.")
        return False

    now = datetime.now()
    is_cob = now.hour >= cob_hour

    should_release = force
    reason = "Forced release"

    if not should_release and is_cob:
        should_release = True
        reason = f"Past Close of Business ({now.strftime('%H:%M')} >= {cob_hour:02d}:00) and no active jobs"
    elif not should_release:
        # Check file modification time of lock file or anvil.env
        check_time = lock_file.stat().st_mtime if lock_file.exists() else env_file.stat().st_mtime
        idle_duration = time.time() - check_time
        if idle_duration >= idle_timeout_sec:
            should_release = True
            reason = f"Instance idle for {idle_duration / 60:.1f} minutes (threshold: {idle_timeout_sec / 60:.0f} min)"

    if should_release:
        print(f"⏰ Triggering auto-release: {reason}.")
        return release_instance(int(instance_id), env_file=env_file, lock_file=lock_file)

    print(f"ℹ️ Instance #{instance_id} is idle, but before COB ({cob_hour:02d}:00). Active and retained.")
    return False


def get_status(
    env_file: Path = DEFAULT_GLOBAL_ENV_FILE,
    lock_file: Path = DEFAULT_LOCK_FILE,
) -> Dict[str, Any]:
    """Compile comprehensive status of active cloud instance, credentials, and locks."""
    env = load_env_file(env_file)
    active_jobs = prune_locks(lock_file)
    instance_id = env.get("VAST_INSTANCE_ID")

    status: Dict[str, Any] = {
        "configured": bool(instance_id or env.get("REMOTE_HOST")),
        "instance_id": instance_id,
        "remote_host": env.get("REMOTE_HOST", "anvil"),
        "remote_port": env.get("REMOTE_PORT", "22"),
        "remote_user": env.get("REMOTE_USER", "root"),
        "active_jobs": active_jobs,
        "is_locked": len(active_jobs) > 0,
    }

    if instance_id and get_api_key():
        info = get_instance_info(int(instance_id))
        status["vast_status"] = info.get("actual_status", "unknown")
        status["gpu_name"] = info.get("gpu_name")
        status["dph_total"] = info.get("dph_total")

    return status


def print_status_table(status: Dict[str, Any]) -> None:
    """Render human-readable status table to stdout."""
    print("=" * 60)
    print(" ☁️  ANVIL CLOUD SERVER (VAST.AI) STATUS")
    print("=" * 60)
    print(f" Rented Instance ID: {status.get('instance_id') or 'None (Not provisioned)'}")
    print(f" Remote Host:        {status.get('remote_host')}:{status.get('remote_port')}")
    print(f" Remote User:        {status.get('remote_user')}")
    if "vast_status" in status:
        print(f" Vast.ai State:      {status.get('vast_status')}")
        print(f" GPU Model:          {status.get('gpu_name', 'N/A')}")
        if status.get("dph_total"):
            print(f" Cost Rate:          ${float(status['dph_total']):.3f}/hour")
    print(
        f" Active Lock:        {'🔒 YES (' + str(len(status['active_jobs'])) + ' running)' if status['is_locked'] else '🔓 Idle'}"
    )
    if status["active_jobs"]:
        for j in status["active_jobs"]:
            print(f"   -> PID {j['pid']} [{j['repo']}]: {j['command']}")
    print("=" * 60)


def build_bootstrap_script(target: str = "all") -> str:
    """Generate remote bash script to bootstrap toolchains, Rust, Miniforge, and Conda."""
    script = (
        """#!/usr/bin/env bash
set -e
export DEBIAN_FRONTEND=noninteractive

echo "🔧 [1/5] Updating apt repositories and installing core compiler toolchains..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libssl-dev \
    cmake \
    clang \
    git \
    curl \
    wget \
    rsync \
    jq \
    htop \
    ca-certificates

# 2. Rust & Cargo
echo "🦀 [2/5] Configuring Rust & Cargo..."
if ! command -v cargo &>/dev/null && [ ! -f "$HOME/.cargo/bin/cargo" ]; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal
fi
export PATH="$HOME/.cargo/bin:$PATH"
if command -v cargo &>/dev/null; then
    if ! command -v cargo-nextest &>/dev/null; then
        echo "Installing cargo-nextest..."
        cargo install cargo-nextest --locked 2>/dev/null || true
    fi
fi

# 3. Persistent Miniforge on /workspace
echo "🐍 [3/5] Configuring Miniforge Conda..."
CONDA_DIR="/workspace/miniforge3"
if [ ! -d /workspace ]; then
    CONDA_DIR="$HOME/miniforge3"
fi

if [ ! -f "${CONDA_DIR}/bin/conda" ]; then
    echo "Downloading Miniforge installer..."
    MINIFORGE_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
    curl -fsSL -o /tmp/miniforge.sh "${MINIFORGE_URL}"
    bash /tmp/miniforge.sh -b -p "${CONDA_DIR}"
    rm -f /tmp/miniforge.sh
fi

source "${CONDA_DIR}/etc/profile.d/conda.sh"
echo "source ${CONDA_DIR}/etc/profile.d/conda.sh" >> "$HOME/.bashrc"

# 4. NVIDIA GPU verification
echo "⚡ [4/5] Checking GPU acceleration..."
if command -v nvidia-smi &>/dev/null; then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true
else
    echo "ℹ️ No NVIDIA GPU detected or driver not mapped; CPU-only execution."
fi

# 5. Conda Environments Provisioning
echo "📦 [5/5] Provisioning repository environments (Target: """
        + target
        + """)..."

TARGET="\""""
        + target
        + """\""

# Firmware environment
if [ "$TARGET" = "all" ] || [ "$TARGET" = "firmware" ]; then
    if ! conda env list | grep -q "^firmware-env "; then
        echo "Creating firmware-env..."
        conda create -y -n firmware-env python=3.11
        conda run -n firmware-env pip install --no-cache-dir \
            pytest pytest-mock pydantic jinja2 requests
    else
        echo "firmware-env already exists, skipping."
    fi
fi

# Hardware (cq) environment
if [ "$TARGET" = "all" ] || [ "$TARGET" = "hardware" ] || [ "$TARGET" = "cq" ]; then
    if ! conda env list | grep -q "^cq "; then
        echo "Creating cq environment..."
        conda create -y -n cq python=3.11 -c conda-forge
        conda run -n cq pip install --no-cache-dir \
            cadquery pytest pytest-xdist rerun-sdk opencv-python pybullet
    else
        echo "cq environment already exists, skipping."
    fi
fi

# SSD / Stalking environment
if [ "$TARGET" = "all" ] || [ "$TARGET" = "ssd" ] || [ "$TARGET" = "stalking" ]; then
    if ! conda env list | grep -q "^predict-env " && ! conda env list | grep -q "^stalking-env "; then
        echo "Creating predict-env with PyTorch & CUDA..."
        conda create -y -n predict-env python=3.10
        conda run -n predict-env pip install --no-cache-dir \
            torch torchvision --index-url https://download.pytorch.org/whl/cu121
        conda run -n predict-env pip install --no-cache-dir \
            ultralytics opencv-python transformers rerun-sdk eel jinja2 pandas
    else
        echo "predict-env already exists, skipping."
    fi
fi

echo "✅ Remote bootstrap complete!"
"""
    )
    return script


def main() -> int:
    """CLI entrypoint for vast_manager."""
    parser = argparse.ArgumentParser(description="Vast.ai Cloud Instance Lifecycle Manager")
    subparsers = parser.add_subparsers(dest="subcommand", help="Action to perform")

    # provision
    prov_p = subparsers.add_parser("provision", help="Provision new Vast.ai instance")
    prov_p.add_argument("--image", default=DEFAULT_UBUNTU_IMAGE, help="Container image")
    prov_p.add_argument("--disk", type=int, default=DEFAULT_DISK_SIZE_GB, help="Disk space in GB")
    prov_p.add_argument("--offer", type=int, default=None, help="Explicit offer ID to rent")
    prov_p.add_argument("--gpu", default=None, help="GPU model filter (e.g. RTX_4090, RTX_3090)")
    prov_p.add_argument("--max-dph", type=float, default=None, help="Maximum dollars per hour")
    prov_p.add_argument("--env-file", type=Path, default=DEFAULT_GLOBAL_ENV_FILE, help="Path to write config")

    # release
    rel_p = subparsers.add_parser("release", help="Release/destroy Vast.ai instance")
    rel_p.add_argument("instance_id", nargs="?", type=int, default=None, help="Instance ID to destroy")
    rel_p.add_argument("--env-file", type=Path, default=DEFAULT_GLOBAL_ENV_FILE, help="Path to config")

    # auto-release
    auto_p = subparsers.add_parser("auto-release", help="Check lock file and release if idle or past COB")
    auto_p.add_argument("--force", action="store_true", help="Force release if no active locks")
    auto_p.add_argument("--cob-hour", type=int, default=DEFAULT_COB_HOUR, help="COB hour threshold (0-23)")
    auto_p.add_argument("--idle-sec", type=int, default=DEFAULT_IDLE_TIMEOUT_SEC, help="Idle timeout in seconds")
    auto_p.add_argument("--env-file", type=Path, default=DEFAULT_GLOBAL_ENV_FILE, help="Path to config")
    auto_p.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK_FILE, help="Path to lock file")

    # lock / unlock
    lock_p = subparsers.add_parser("lock", help="Register active job lock")
    lock_p.add_argument("--pid", type=int, default=None, help="Process ID to lock")
    lock_p.add_argument("--repo", default="workspace", help="Active repository name")
    lock_p.add_argument("cmd", nargs=argparse.REMAINDER, help="Running command string")

    unlock_p = subparsers.add_parser("unlock", help="Unregister active job lock")
    unlock_p.add_argument("--pid", type=int, default=None, help="Process ID to unlock")

    # status
    stat_p = subparsers.add_parser("status", help="Show active instance and lock status")
    stat_p.add_argument("--json", action="store_true", help="Output JSON format")
    stat_p.add_argument("--env-file", type=Path, default=DEFAULT_GLOBAL_ENV_FILE, help="Path to config")
    stat_p.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK_FILE, help="Path to lock file")

    # bootstrap-script
    boot_p = subparsers.add_parser("bootstrap-script", help="Emit remote bootstrap bash script")
    boot_p.add_argument("--target", default="all", choices=["all", "firmware", "hardware", "ssd"], help="Target repo")

    args = parser.parse_args()

    if args.subcommand == "provision":
        res = provision_instance(
            image=args.image,
            disk_gb=args.disk,
            offer_id=args.offer,
            gpu=args.gpu,
            max_dph=args.max_dph,
            env_file=args.env_file,
        )
        return 0 if "error" not in res else 1

    elif args.subcommand == "release":
        success = release_instance(instance_id=args.instance_id, env_file=args.env_file)
        return 0 if success else 1

    elif args.subcommand == "auto-release":
        auto_release(
            force=args.force,
            cob_hour=args.cob_hour,
            idle_timeout_sec=args.idle_sec,
            env_file=args.env_file,
            lock_file=args.lock_file,
        )
        return 0

    elif args.subcommand == "lock":
        cmd_str = " ".join(args.cmd) if args.cmd else "anvil"
        record_lock(cmd_str, args.repo, pid=args.pid)
        return 0

    elif args.subcommand == "unlock":
        remove_lock(pid=args.pid)
        return 0

    elif args.subcommand == "status":
        stat = get_status(env_file=args.env_file, lock_file=args.lock_file)
        if args.json:
            print(json.dumps(stat, indent=2))
        else:
            print_status_table(stat)
        return 0

    elif args.subcommand == "bootstrap-script":
        print(build_bootstrap_script(target=args.target))
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
