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
1. **Execution**: Always activate the `cq` conda environment (as specified in [environment.yml](file:///Users/daparker/gh/hardware/environment.yml)) and run commands from the repository root.
2. **Outcome Verification**: Confirm that all checks (format, lint, compile, and pytest) pass with exit code `0`.
3. **Resolution**: If any component fails (such as syntax error, ruff failure, or failing test), you must address the failure and re-run the check before concluding your work.
4. **Integration Smoke Tests**: The integration smoke tests (`python src/smoke.py`) are highly resource-intensive and should be run on the continuous integration (CI) server. Avoid running them locally during normal development iterations unless you are verifying changes to the daemon, visualizer backend, or SPH physics engine.

---

## Software Architecture & Code Guidelines

### 1. Test Isolation & Marking
* Unit tests MUST be completely isolated from implementation code. Do NOT mix unit tests inside implementation files.
* Core framework tests go in [src/tests/](file:///Users/daparker/gh/hardware/src/tests/) and project-specific tests go in [src/projects/tests/](file:///Users/daparker/gh/hardware/src/projects/tests/).
* **Slow Tests**: 3D CAD boolean checks, PyBullet physics simulations, and JAX SPH fluid dynamics tests are highly resource-intensive. They must be decorated with `@pytest.mark.slow` (or have `slow` in their test markers) so they do not block the fast pre-commit check. Run them manually or in nightly validation with:
  ```bash
  pytest -m "slow"
  ```

### 2. Geometry Providers & Discoverability
* Custom geometry projects must be packages nested within [src/projects/](file:///Users/daparker/gh/hardware/src/projects/).
* The provider class must inherit from `Provider` and be decorated with `@discover_provider` (imported from [src/provider/utils.py](file:///Users/daparker/gh/hardware/src/provider/utils.py)).
* Always export the provider at the package level (`__init__.py`) and import it in [src/projects/\_\_init\_\_.py](file:///Users/daparker/gh/hardware/src/projects/__init__.py).
* Builder methods should return shape/build geometries (e.g., `BuildPart`), while diagram/view actions should populate a `Room` object via `room.add(...)` or `room.add_label(...)`.

### 3. Configuration & Lazy Initialization
* Always use `@cached_property` for `default_config` and any sub-tools (Builders, Configurators) in your provider class. This guarantees correct orchestration timing, prevents staling configs, and minimizes expensive CAD allocations.
* **Geometry Parametrization**: Always define base geometry parameters in the project's `measurements.yaml` and read them dynamically via config settings. Compute derived geometry coordinates and dimensions dynamically relative to these settings (e.g., using clearances, wall thicknesses, and offsets) instead of hardcoding absolute values. This prevents geometry regressions (e.g. intersections, misaligned steps, or floating shells) when base dimensions are scaled or overridden.
* Settings and configuration schemas must use Pydantic models (subclassing `BaseModel`) defined under [src/projects_config/](file:///Users/daparker/gh/hardware/src/projects_config/).
* Config overrides can be injected dynamically via environment variables patterned as `<PROJECT>__<SETTING>` (e.g., `EXHAUST_MANIFOLDS__WALL_THICKNESS`).
* **Data Model Integrity**: Prefer using strongly typed data models with well-defined properties and methods over runtime dynamic attribute parsing (e.g., avoiding loose `hasattr` or `getattr` checks on untyped objects where static type annotations should instead guarantee structure).
* **Error Handling & Exception Guardrails**: Use explicit bounds checking and validation rather than generic `try/except` blocks. Do NOT use `try/except` structures in core computation or logic paths except to guard I/O operations (such as filesystem access, networking, or database calls).
* **Parameter Validation**: Prefer Pydantic parameter validation over manual validation checks in code. If dynamic runtime validation is necessary (e.g., in math or physics functions), raise a descriptive `ValueError` to indicate invalid parameters rather than silently failing or falling back.
* **Method Parameterization**: Prefer passing parameters and configuration models explicitly into methods and functions rather than having them read instance attributes or parent provider properties internally. This keeps computation blocks pure, modular, and easy to unit test.

### 4. Physical Simulation & URDF Metadata
* For components participating in physics simulations (e.g., PyBullet, JAX fluids), attach URDF and simulation attributes to shape geometries.
* Use `URDFMetadata` blocks to wrap geometries, providing `label`, `material`, `density`, `collision_type` (`URDFCollisionType`), etc.
* Available fields include:
  - `urdf_label` (`str`): Unique label in URDF.
  - `urdf_material` (`str`): Material name (e.g., `"petg"`, `"acrylic"`).
  - `urdf_density` (`float`): Density in $\text{kg/m}^3$.
  - `urdf_collision_type` (`URDFCollisionType`): Convex, concave, compound, analytical, or none.
  - Kinematic joint constraints (`urdf_joint_type`, `urdf_joint_axis`, limits) and motor properties (`urdf_motor_type`, target, force).
* **Physics Parameters Definition**: All physical properties and simulation parameters—including magnetic coupling attraction forces, joint constraints, kinematics, and physical barriers—MUST be defined in the URDF metadata or settings schema rather than being hardcoded in python source code.
* **Dynamic Physics via URDF & Joints**: The physics and simulation code (e.g., in [fluid.py](file:///Users/daparker/gh/hardware/src/provider/fluid.py) and [bullet.py](file:///Users/daparker/gh/hardware/src/provider/bullet.py)) MUST compute physics dynamically using values read from the URDF metadata and PyBullet joint information, rather than hardcoding physics constants. Extend the URDF metadata schema as needed to support new physical properties.

### 5. SPH Fluid Simulation & Numerical Stability
* **Analytical Boundaries**: Prefer analytical boundaries (`URDFCollisionType.ANALYTICAL`) over concave meshes (`URDFCollisionType.CONCAVE`) for JAX SPH fluid simulation. This prevents boundary particle tunneling and accelerates collision resolution.
* **Cylinder Boundaries**: For cylinder cavity boundary configurations, treat height as infinite along the local Z axis where possible to avoid particle escape at high pressures.
* **Fluid Recycling**: Ensure `fluid.recycle_fluid = True` is used in steady-state flow loops, with boundary coordinates matching physical limits.
* **JAX-JIT Compilation**: Prefer using `jax.jit` and pure functions during physics computations in JAX to leverage static optimization, compilation speedups, and hardware acceleration.
* **Numeric Damping**: For long-running simulation validations, enforce stabilization velocity damping (e.g., `0.95`) to prevent numerical velocity buildup.

### 6. Declarative Wiring & Routing Engine
* Declare footprint, physical dimensions, pinouts, and net connections in the project's `wiring.yaml` file.
* Keep orthogonal routing layout automated using pathfinding algorithms. Wire path crossover bumps must be computed automatically to avoid visual intersections.

### 7. Documentation & Lint Style
* Code documentation MUST be PEP-257 compliant and comprehensive. Write docstrings for all custom classes, methods, functions, and properties.
* Docstring correctness is checked automatically by ruff linting rules (group `D` configured in [pyproject.toml](file:///Users/daparker/gh/hardware/pyproject.toml)).
* **String Enums for Keys**: Prefer defining structured string enums (subclassing `str` and `Enum`) over passing raw string literals directly for dictionary keys, joint/link labels, or configuration modes. This prevents typos and improves code readability/refactoring.
