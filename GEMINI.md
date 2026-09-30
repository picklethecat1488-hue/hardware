# Workspace Rules: Pre-Commit Validation

Before finalizing any task, committing changes, or proposing modifications to the codebase, you MUST run formatting, linting, compile check, and the tests to ensure the codebase remains healthy:

```bash
# 1. Activate the conda environment
conda activate cq

# 2. Check Python syntax/compilation errors
python -m compileall -q .

# 3. Check code formatting
ruff format --check .

# 4. Check linting rules
ruff check .

# 5. Run the fast test suite (excludes slow tests)
pytest
```

## Validation Guidelines
1. **Execution**: Prefer offloading test suites (`pytest`, `pytest -m "slow"`, `python src/smoke.py`) and pre-commit validation to the `anvil` cloud server (e.g., via `bin/anvil run "PYTHONPATH=src /home/ubuntu/miniforge3/envs/cq/bin/pytest"` or `ssh anvil`) to free up local CPU/GPU compute for rapid iteration, CAD generation, and interactive experiments. When running locally, activate the `cq` conda environment.
2. **Outcome Verification**: Confirm that all checks (format, lint, compile, and pytest) pass with exit code `0`.
3. **Resolution**: If any component fails (such as syntax error, ruff failure, or failing test), you must address the failure and re-run the check before concluding your work.
4. **Integration Smoke Tests**: The integration smoke tests (`python src/smoke.py`) are highly resource-intensive and should always be run on `anvil`.
5. **Process Management & Rerun Hygiene**: When restarting or re-running test suites (`pytest`, `pytest -m "slow"`, `bin/anvil pytest`, `python src/smoke.py`, etc.), you MUST explicitly terminate/kill any preceding running instances of that test or task before launching a new execution. Never allow multiple overlapping runs of the same test command.
6. **GitHub CI Monitoring & Local Stack Remediation**: When commits have been pushed to a remote feature branch or when instructed to inspect CI, you may inspect GitHub Actions CI workflow results (e.g. via `gh run list --limit 5`, `gh pr checks`, or `gh run view <run-id> --log-failed`) and resolve any reported failures. However, the agent MUST NOT autonomously create pull requests (`gh pr create`) or merge pull requests (`gh pr merge`).

---

## Remote Cloud Server (`anvil`)

For resource-intensive workloads, parameter sweeps, fluid dynamics simulations, integration smoke tests (`python src/smoke.py`), validation experiments, and data collection, the `anvil` cloud server is available:

```ssh-config
Host anvil
  HostName <anvil-ip>
  User ubuntu
  IdentityFile "~/.ssh/FLINT'S KEY.pem"
  IdentitiesOnly yes
  ServerAliveInterval 30
  ServerAliveCountMax 10
  TCPKeepAlive yes
  StrictHostKeyChecking accept-new
```

### Usage Guidelines
1. **Remote Execution**: Use `bin/anvil run "<command>"` or SSH targeting `ubuntu@anvil` (or `ssh anvil`) to run full test suites (`pytest`), slow physics benchmarks (`pytest -m "slow"`), large JAX SPH simulation grids, parameter sweeps, and integration smoke tests (`python src/smoke.py`).
2. **Conda Environment & Binaries**: On `anvil`, execute commands within the `cq` conda environment using `conda run -n cq --no-capture-output <command>` (prefer relative executable names like `python`, `pytest`, `ruff` over absolute paths).
3. **Preceding Run Cancellation**: Before initiating a new remote execution or benchmark on `anvil`, ensure any active or stale background runs of the same command are cancelled or terminated to avoid cloud resource contention and duplicate processing.

---

## Core Architecture & Code Invariants

### 1. Test Isolation & Regression Unit Testing
* Unit tests MUST be completely isolated from implementation code. Core framework tests go in [src/tests/](file:///Users/daparker/gh/hardware/src/tests/) and project-specific tests go in [src/projects/tests/](file:///Users/daparker/gh/hardware/src/projects/tests/).
* **Slow Tests**: 3D CAD boolean checks, PyBullet physics simulations, and JAX SPH fluid dynamics tests are highly resource-intensive and must be decorated with `@pytest.mark.slow` (or have `slow` in their test markers) so they do not block fast pre-commit checks:
  ```bash
  pytest -m "slow"
  ```
* **Regression Unit Testing Mandate**: Whenever a regression is identified, investigated, or bisected to a prior change, you MUST introduce dedicated regression unit tests (or add active regression assertions to existing test suites) that explicitly guard against the identified regression before concluding the task.

### 2. Geometry Providers & Discoverability
* Custom geometry projects must be packages nested within [src/projects/](file:///Users/daparker/gh/hardware/src/projects/).
* The provider class must inherit from `Provider` and be decorated with `@discover_provider` (imported from [src/provider/utils.py](file:///Users/daparker/gh/hardware/src/provider/utils.py)). Always export the provider at the package level (`__init__.py`) and import it in [src/projects/\_\_init\_\_.py](file:///Users/daparker/gh/hardware/src/projects/__init__.py).
* **Project Manifest Integration**: All custom geometry parts, components, clips, or support structures that participate in assemblies or are needed for manufacturing MUST be explicitly registered in the project's `manifest.yaml` to ensure correct build-chain discovery and inclusion in build artifacts.
* Builder methods should return shape/build geometries (e.g., `BuildPart`), while diagram/view actions should populate a `Room` object via `room.add(...)` or `room.add_label(...)`.

### 3. Configuration & Data Model Integrity
* Always use `@cached_property` for `default_config` and any sub-tools (Builders, Configurators) in your provider class to guarantee correct orchestration timing and minimize expensive CAD allocations.
* **Geometry Parametrization**: Define base geometry parameters in the project's `measurements.yaml` and read them dynamically via config settings. Compute derived geometry coordinates, dimensions, and branch comparison thresholds dynamically relative to these settings rather than hardcoding numeric literals.
* **Data Model Integrity & Validation**: Settings and configuration schemas must use Pydantic models (subclassing `BaseModel`) defined under [src/projects_config/](file:///Users/daparker/gh/hardware/src/projects_config/). Prefer strongly typed data models over runtime dynamic attribute parsing (`hasattr` / `getattr`). Prefer Pydantic validation over manual checks in code; if dynamic validation is necessary, raise a descriptive `ValueError`.
* **Method Parameterization**: Pass parameters and configuration models explicitly into methods and functions rather than having them read instance attributes or parent provider properties internally.
* **Configuration Persistence**: For configuration actions, persist saved settings to the Pydantic environment file (`.env`) in addition to updating source data files (`measurements.yaml`).
* **No Fallback Constants**: Do NOT place fallback constants directly in the codebase when parsing configs or settings (e.g., ternary fallbacks or `getattr` defaults like `0.004` or `0.90`). All configuration fields must be strongly typed and resolved dynamically. Fallbacks of `0`, `0.0`, or `None` are acceptable to represent unconfigured properties.

### 4. Strict Code Cleanliness & Hygiene
* **No Dead Code**: Unused code (dangling clauses, functions, or parameters that do nothing) and settings that do not affect anything must be removed from the repository.
* **No Backward Compatibility Shims**: Do NOT introduce, retain, or propose backward compatibility shims, aliases, legacy wrappers, deprecated fallbacks, or obsolete re-exports. Update callers, imports, and tests directly to canonical current names and purge obsolete identifiers completely.
* **Parameter & Signature Hygiene**: When modifying, refactoring, or simplifying functions, subroutines, or methods, any parameters that become unused MUST be immediately pruned from both the function signature and all caller invocations with each change.
* **Error Handling Guardrails**: Use explicit bounds checking and validation rather than generic `try/except` blocks. Do NOT use `try/except` structures in core computation or logic paths except to guard I/O operations (filesystem, network, database). Never silently ignore errors with `try/except/pass` blocks; exceptions must be logged, raised descriptively, or allowed to propagate.

### 5. Documentation & Lint Style
* Code documentation MUST be PEP-257 compliant and comprehensive. Write docstrings for all custom classes, methods, functions, and properties.
* **String Enums for Keys**: Prefer defining structured string enums (subclassing `str` and `Enum`) over passing raw string literals directly for dictionary keys, joint/link labels, or configuration modes.
* **Named Constant Formatting**: Constant values in production code must be assigned to module-level or class-level `ALL_CAPS` named constant variables rather than being embedded as inline magic literals.
* **Idiomatic Iteration & Pattern Matching**: Prefer looping over sequences directly or using `enumerate(...)` rather than indexing by integer range bounds. Prefer Python `match / case` pattern matching syntax when comparing against multiple variants or enum branches.
* **Import Placement**: Imports should be placed at the top of the file, unless doing so would cause circular dependencies.
* **Markdown Preview Asset Location**: All markdown preview galleries, rendered frame previews, inspection figures, and simulation snapshots intended for visual evaluation MUST be placed inside the workspace under `recordings/previews/` using relative image paths.

---

## Workflow & Issue Tracking Principles

### 1. Work Tracking & Task Management
* **Task List (`TODO.md`)**: Maintain and track planned tasks, active implementation steps, outstanding engineering checklist items, and completed work in `TODO.md` in the workspace root. Keep checklist items updated (`[ ]` -> `[x]`) as subtasks progress.

### 2. Pending Code Review Inspection
* Whenever beginning a new task, turn, or feature implementation, you MUST inspect the `feedback/` directory—including the primary aggregated report (`feedback/CR.md`), granular commit review files (`feedback/CR_<commit>.md`), or query the review database (`build/code_review.sqlite`, `python src/dashboard.py list-reviews --open`) for pending code review feedback, active review comments, or requested revisions. Any unaddressed feedback (particularly `MUST_FIX` blockers) must be prioritized and resolved before progressing to new development tasks.

### 3. Bug Tracker & Historical Context Inspection
* Whenever working on tasks, investigating issues, or modifying existing subsystems, you MUST inspect the bug tracking records (`feedback/BUGS.md`, `feedback/BUG_<id>.md`, `build/bugs.sqlite`, `python src/dashboard.py list-bugs --open`) for past context, historical failure modes, reproduction steps, and resolved invariants. Leveraging past context prevents re-introducing known regressions. All bug report attachments (`attachments/`, `build/attachments/`, `feedback/attachments/`) are tracked in **GitHub LFS** and considered **non-confidential** and public to the repository; never attach sensitive credentials, secret tokens, private keys, or proprietary secrets.

### 4. Single-Bug Focus & Atomic Issue Remediation
* To prevent context pollution and attention degradation during extended problem-solving sessions, you MUST investigate, diagnose, and resolve only ONE bug or defect at a time:
  1. **Registry & Context**: Query the bug tracker or register the new defect with reproduction steps and classification.
  2. **Isolated Reproduction**: Construct an isolated reproduction script or minimal failing unit test asserting the flawed invariant *before* editing production code.
  3. **Targeted Fix**: Implement the minimal necessary change strictly scoped to the defect.
  4. **Dedicated Regression Test**: Codify the reproduction into an active unit test asserting the correct invariant.
  5. **Verification**: Run pre-commit checks (`compileall`, `ruff`, and `pytest`) to verify 100% pass rate.
  6. **Resolution & Commit**: Mark the bug resolved in `src/dashboard.py` and commit the fix atomically before picking up the next task.

### 5. User-Managed Code Review & Autonomous PR Prohibition
* The assistant is strictly PROHIBITED from autonomously creating pull requests (`gh pr create`) or merging pull requests (`gh pr merge`). All pull request creation, peer code reviews, and PR merges MUST be performed manually by the user.

---

## Modular Subsystem & Domain Architecture Guides

To minimize global context overhead and prevent unnecessary token burn, domain- and subsystem-specific architectural mandates are maintained in dedicated reference documents under `docs/`:

1. [SPH Fluid Dynamics & Numerical Stability](file:///Users/daparker/gh/hardware/docs/sph_fluid_dynamics.md)
   - Analytical vs concave boundary representations and cylinder cavity invariants.
   - JAX-JIT compilation, semantic coordinate transforms, and fluid recycling.
   - Numerical velocity damping and physical contact non-floating verification.

2. [Physics & URDF Simulation Guidelines](file:///Users/daparker/gh/hardware/docs/physics_urdf_simulation.md)
   - URDF metadata specification and kinematic joint definitions.
   - Mandated direct CAD boundary derivation via `URDFBoundary.from_shape` with zero duplicate numeric literals.
   - Dynamic physics parameter configuration and PyBullet bug reproduction mandate.

3. [Declarative Wiring & PCB Engine](file:///Users/daparker/gh/hardware/docs/declarative_wiring_pcb.md)
   - Declarative PCB toolchain, manifest pipeline, and headless KiCad CAM generation.
   - Subassembly footprint scoping and canonical component reference designators (`R1`, `C1`, `D1`, `Q1`, `Y1`, `J1`, `U1`, `TP1`).
   - PCB routing invariants, flex planar keepouts, DRC exemptions, and schematic router detour rules.
   - Component selection and bare-metal Rust (`no_std`, Embassy) firmware co-design criteria.

4. [VCS Workstation, Code Review & Quake HUD Templates](file:///Users/daparker/gh/hardware/docs/vcs_code_review.md)
   - Jinja2 code generation, dedicated template directory structures, and error guardrails.
   - Review session feedback persistence and atomic SQLite backing store.
   - Structured bug tracking, Git LFS attachments, and VCS CLI subcommand parity.
