# CLI Tools, Build & Workstation Workflows

This guide covers environment setup, target syntax, CAD/PCB compilation, interactive visualization in Scope (`tools/scope.py`), VCS/review/bug tracking in Forge (`tools/forge.py`), and pre-commit verification (`./tools/verify.sh`).

---

## 1. Environment Setup

This repository uses [conda](https://conda-forge.org/download/) / Mamba for dependency management:

```bash
mamba env create -f environment.yml
conda activate cq
```

All commands below should be run from the repository root.

---

## 2. Target Specification Format

All CLI utilities accept a standardized target specification format:

```text
[provider/target][_subassembly][:action[/mode]]
```

- **Target**: Project and part/view name (e.g., `exhaust_manifolds/driver` or wildcard `exhaust_manifolds/*`).
- **Subassembly**: Optional variant (e.g., `exhaust_manifolds/driver_left`).
- **Action / Mode**: Optional overrides (e.g., `exhaust_manifolds/driver:part/print`, `carrier_board/carrier_board:pcb`, `cat_fountain/product:simulate`).

### Listing Targets and Build Outputs (`tools/list.py`)

Inspect discoverable targets or preview exact build artifacts without compiling geometry:

```bash
# List all valid targets across all actions and modes
python tools/list.py targets

# List all files the build will export without building them
python tools/list.py outputs

# List build outputs for specific targets
python tools/list.py outputs 'exhaust_manifolds/*'
```

---

## 3. Interactive CAD, PCB, Diagram & Simulation Workstation (`tools/scope.py`)

Use **Scope** (`tools/scope.py`) to inspect 3D B-rep assemblies, multi-layer KiCad PCBs (rendered via GPU SDF instancing and 2× Retina Canvas2D), exploded/wiring diagrams, and undecimated SPH/LBM fluid simulations, with 2D/3D viewport markups and one-click **Target Bug** filing into Forge:

```bash
# Launch Scope workstation with the interactive Target Chooser modal
python tools/scope.py

# Inspect a 3D CAD target
python tools/scope.py exhaust_manifolds/driver
python tools/scope.py exhaust_manifolds/wire
python tools/scope.py 'exhaust_manifolds/*:part/print'

# Inspect a multi-layer PCB with layer visibility, net highlighting, mm ruler, and Open in KiCad
python tools/scope.py carrier_board/carrier_board:pcb

# Inspect 2D wiring or 3D isometric exploded diagrams
python tools/scope.py cat_fountain/wiring --mode diagram
python tools/scope.py cat_fountain/product --mode diagram

# Run or scrub physical & SPH fluid simulations in Scope
python tools/scope.py cat_fountain/product:simulate

# Headless simulation capture to Rerun (.rrd) or MP4
python tools/scope.py cat_fountain/product:view/simulate -s 500 --save-rrd recordings/cat_fountain.rrd

# Stop background Scope server
python tools/scope.py stop
```

---

## 4. Building CAD, Diagrams, URDFs & PCBs (`tools/build.py`)

### Building 3D Geometry & Diagrams

```bash
# Build all parts, diagrams, URDFs, and PCBs into build/
python tools/build.py

# Build all targets in a specific project
python tools/build.py 'exhaust_manifolds/*'
python tools/build.py 'cat_fountain/*'

# Build only diagrams for a project
python tools/build.py 'valve_actuator_limiter/*:diagram'
```

### Geometry Configuration & Optimization (`tools/config.py`)

When measurements or layout parameters change, run `tools/config.py` to optimize part placement, text logos, or PCB routing:

```bash
# Configure and optimize all projects
python tools/config.py

# Configure only a specific target or mode
python tools/config.py exhaust_manifolds/driver
python tools/config.py -m text
```

### Declarative Wiring & KiCad PCB Manufacturing

The declarative PCB engine compiles Python board/schematic definitions directly into `.kicad_pcb` / `.kicad_sch` and invokes `kicad-cli` (v7+) to emit RS-274X Gerbers, Excellon drills, DRC reports, BOM/CPL spreadsheets, vector schematics, and 3D STEP models:

```bash
# Build PCB board, schematics, CAM Gerbers, DRC report, and BOM/CPL
python tools/build.py carrier_board:pcb

# Build system wiring diagrams
python tools/build.py cat_fountain/wiring
```

Generated manufacturing archives in `build/board/<project>/` can be inspected in `python tools/scope.py <project>/<board>:pcb`, opened in KiCad (`[📂 Open in KiCad]`), or previewed in [tracespace.io/view](https://tracespace.io/view/). See [Declarative Wiring & PCB Engine](declarative_wiring_pcb.md) for full DSL details.

---

## 5. Unified VCS, Code Review & Bug Tracker Workstation (`tools/forge.py`)

Launch the Quake-styled **Forge** workstation (`/` Diff View & Smartlog DAG, `/review` Code Review, `/bugs` Bug Tracker) or run CLI queries:

```bash
# Launch interactive Forge web workstation
python tools/forge.py

# Inspect smartlog DAG, open code reviews, and open bugs from the CLI
python tools/forge.py list-commits
python tools/forge.py list-reviews --open
python tools/forge.py list-bugs --open
```

See [VCS Workstation, Code Review & Quake HUD Templates](vcs_code_review.md) and [CONTRIBUTING.md](../CONTRIBUTING.md) for full CLI subcommands.

---

## 6. Pre-Commit Verification, Testing & Cloud Execution

Run `./tools/verify.sh` before committing changes to execute Python syntax compilation, Ruff formatting & linting, JavaScript zero-globals & Jinja2 template validation (`tools/validate_js.py`), parallel `node --test` suites, and parallel `pytest`:

```bash
# Full pre-commit verification (auto-resolves the cq conda environment)
./tools/verify.sh

# Auto-format & auto-fix Ruff lint issues before running checks
./tools/verify.sh --fix

# Fast static + JS lint + parallel JS unit tests only (skips pytest)
./tools/verify.sh --quick

# Include @pytest.mark.slow 3D CAD boolean & PyBullet/JAX SPH simulation suites
./tools/verify.sh --slow

# Include end-to-end CLI & HTTP workstation smoke tests (python tools/smoke.py)
./tools/verify.sh --smoke

# Offload verification, pytest, or GPU fluid simulations to the remote anvil cloud server
tools/anvil verify
tools/anvil smoke
```

Individual test suites can also be run directly (`conda activate cq`):

```bash
node --test --test-concurrency=4 tests/js/*.test.mjs
pytest
pytest -m "slow"
```

See [Remote Cloud Runner (`anvil` / Vast.ai)](remote_cloud_runner.md) for remote GPU provisioning and lifecycle commands.
