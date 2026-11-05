# Remote Cloud Runner & Vast.ai Architecture

## Architectural Purpose
To provide on-demand, cost-effective, high-throughput cloud compute via Vast.ai GPU/container instances for resource-intensive workloads, parameter sweeps, fluid dynamics simulations, cargo builds, and test verification across `firmware`, `hardware`, and `SSD`.

---

## Core Invariants & Shared Workstation Configuration

### 1. Centralized Instance Configuration (`~/.anvil.env`)
* **Single Source of Truth**: Active Vast.ai rental parameters are stored in `~/.anvil.env` in `$HOME`, shared transparently across `firmware`, `hardware`, and `SSD`.
* **Local Override**: An optional `.anvil.env` file in the workspace root overrides global settings for workspace-specific experiments.
* **Tracked Variables**:
  - `VAST_INSTANCE_ID`: Contract/instance ID on Vast.ai.
  - `REMOTE_HOST`: Dynamic SSH host (e.g. `ssh5.vast.ai`).
  - `REMOTE_PORT`: Dynamic high port forwarded to container SSH daemon (e.g. `34567`).
  - `REMOTE_USER`: Container user (default `root`).
  - `REMOTE_KEY`: SSH private key path.
  - `REMOTE_DIR`: Optional override for remote target folder.

### 2. Global Shared Runner (`~/.local/bin/anvil`)
* **Global Installation**: The canonical runner script resides at `~/.local/bin/anvil` (symlinked to `~/bin/anvil`).
* **Repository Delegation**: Each repository maintains a lightweight `bin/anvil` script that detects the local `REPO_DIR`, sets `REPO_NAME`, and shares the unified codebase and lifecycle subcommands.
* **Bidirectional Cross-Patching Mandate**: Any enhancements, bug fixes, or argument handling updates made to `bin/anvil` or `tools/vast_manager.py` in one repository MUST be automatically mirrored into the other repositories.

### 3. Dynamic Remote Filesystem Geometry
* **Persistent Volume Detection**: Vast.ai provides persistent container storage under `/workspace`.
* **Automatic Target Selection**: Remote commands and `rsync` dynamically target `/workspace/<repo>` (e.g. `/workspace/firmware`, `/workspace/hardware`, `/workspace/SSD`) if `/workspace` exists; otherwise they fall back to `$HOME/<repo>`.

---

## Instance Lifecycle & Bootstrapping Protocols

### 1. Provisioning & Discovery (`bin/anvil provision`)
* **Offer Search & Hardware Guardrails**: Queries the Vast.ai REST API (`https://cloud.vast.ai/api/v0/bundles/`) for rentable, verified instances with disk space $\ge 40$GB, strictly enforcing hardware throughput and cost constraints to prevent claiming old or overpriced junk hardware:
  - `MIN_TOPS` ($\ge 50.0$ TOPS / TFLOPS, e.g. modern RTX 3090/4090/5090 tiers, filtering out underpowered legacy cards).
  - `MAX_COST` ($\le \$1.50/\text{hr}$, capping hourly rental spend).
* **Base Image**: Deploys the basic Ubuntu container image (`ubuntu:22.04`).
* **Connection Handshake**: Polls instance status until `actual_status == "running"`, extracts dynamic `ssh_host` and `ssh_port`, and atomically updates `~/.anvil.env` (persisting `MIN_TOPS` and `MAX_COST`).
* **Automated Bootstrap**: Automatically triggers remote bootstrapping upon successful SSH connection.

### 2. Remote Dependency Bootstrapping (`bin/anvil bootstrap`)
Prepares clean Ubuntu containers for firmware, hardware, and machine learning workloads:
* **System & Toolchains**: Installs `build-essential`, `pkg-config`, `libssl-dev`, `cmake`, `clang`, `git`, `curl`, `wget`, `rsync`, and `jq` via `apt-get`.
* **Rust & Cargo**: Installs `rustup` stable toolchain and `cargo-nextest` into `$HOME/.cargo/bin`.
* **Persistent Conda**: Installs Miniforge directly to `/workspace/miniforge3` so conda environments survive container restarts.
* **Environment Configuration**:
  - `firmware-env`: Python 3.11, `pytest`, `pytest-mock`, `pydantic`, `jinja2`, `defmt` CLI tools.
  - `cq`: Python 3.11, `cadquery`, `jax`, `jaxlib`, `pybullet`, `pytest-xdist`, `rerun-sdk`.
  - `predict-env`: Python 3.10, PyTorch + CUDA (`cu121`), `ultralytics`, `opencv-python`, `transformers`, `rerun-sdk`.
* **Idempotency**: Skips components and environments already present on disk.

### 3. Instance Teardown (`bin/anvil release`)
* Destroys the active rental contract via the Vast.ai REST API.
* Atomically clears `VAST_INSTANCE_ID` and connection parameters from `~/.anvil.env`.
* Cleans up lingering lock files in `~/.anvil.lock`.

---

## Execution, Concurrency & Resource Hygiene

### 1. Activity Lock Tracking (`~/.anvil.lock`)
* **Registration**: All active dispatches (`sync`, `pytest`, `verify`, `cargo`, `cli`, `host`, `simulate`, `smoke`, `run`) register a lock entry containing `<PID> <TIMESTAMP> <REPO> <COMMAND>`.
* **Automatic Deregistration**: A bash `trap` handler on `EXIT INT TERM` removes the active PID upon command completion.

### 2. Close of Business (COB) Auto-Release Mandate
* **Overnight Spend Prevention**: Rented Vast.ai instances MUST NOT be left running unattended or overnight.
* **Auto-Release Logic (`bin/anvil auto-release`)**:
  - Prunes dead PIDs from `~/.anvil.lock` via `kill -0 <PID>`.
  - If any active jobs remain, aborts release and logs the active processes.
  - If no active jobs remain and either the instance is idle past threshold (default 30 min), `--force` is given, or current time is past COB ($\ge \text{18:00}$ local time), automatically calls `release` to tear down the cloud VM.

### 3. Preceding Run Cancellation
* Before initiating new test suites or builds (`pytest`, `verify`, `simulate`), `bin/anvil` issues remote `pkill -9` commands targeting preceding runs to eliminate duplicate GPU allocations and cloud resource contention.

### 4. Reverse Proxying (`bin/anvil cli` / `host`)
* Binds remote port 8899 to the developer's local workstation daemon (`ssh -R 8899:127.0.0.1:8899`), allowing remote test scripts to interact with physically attached MCU targets.
