# Contributing

## Source Paths

 - **src/build.py** - Orchestrates the generation and export of 3D-printable geometry.
 - **src/config.py** - Automated utility for part placement and geometry optimization.
 - **src/view.py** - Interactive CAD visualization tool for inspection and debugging.
 - **src/model/** - Core application data models and configuration schemas.
 - **src/provider/** - Framework for geometry generation and build orchestration.
 - **src/projects/** - Specific geometry provider implementations.
 - **src/projects_config/** - Configuration models specific to individual projects.

 ## Creating Projects

Projects are self-contained packages located in `src/projects/`. They define how specific geometry is built, configured, and visualized. To add a new project, follow these steps:

### 1. Create the Project Directory
Create a new directory under `src/projects/` (e.g., `src/projects/exhaust_manifolds/`).

### 2. Define the Manifest
Create a `manifest.yaml` file in your project folder. This file tells the orchestrator what parts are available and what actions (part, diagram, config, view) they support.

```yaml
# src/projects/bracket/manifest.yaml
main_plate:
  part:
    modes: [default]
    subassemblies: [left, right]
  config:
    modes: [default]
  color:
    left: grey
    right: [0.7, 0.7, 0.7, 1.0]
```

### 3. Create a Measurements File (Optional)
If your geometry depends on raw coordinates, store them in a `measurements.yaml` file.

```yaml
# src/projects/bracket/measurements.yaml
hole_center: [100, 50, 0]
support_point: [120, 60, 10]
```

### 4. Implement the Provider
The provider acts as the interface between your builder and the application's orchestrator. Decorate it with `@discover_provider` so the ProviderManager can find it. 

```python
# src/projects/bracket/provider.py
from functools import cached_property
from build123d import *
from pathlib import Path
from provider import Provider, Action, Mode, discover_provider, Room
from projects_config import ExhaustManifoldsConfig # Or a custom Pydantic model

@discover_provider
class BracketProvider(Provider):
    @cached_property
    def default_config(self):
        return ExhaustManifoldsConfig(
            measurements_path=str(Path(__file__).parent / "measurements.yaml")
        )

    @property
    def part(self):
        return {name: self.build_part for name in self.targets.supporting(Action.PART)}

    @property
    def diagram(self):
        return {name: self.build_diagram for name in self.targets.supporting(Action.DIAGRAM)}

    @property
    def view(self):
        return {name: self.build_view for name in self.targets.supporting(Action.VIEW)}

    def build_diagram(self, room: Room, targets: list[str], mode: Mode) -> None:
        # Diagrams populate a Room instead of returning geometry
        plate = self.build_part("main_plate", "left", mode)
        room.add("main_plate", plate)
        room.add_label("main_label", "Bracket Plate", (0, 0, 10))

    def build_part(self, target: str, subassembly: str, mode: Mode) -> BuildPart:
        with BuildPart() as p:
            Box(10, 20, 5)
            if subassembly == "right":
                mirror(about=Plane.YZ)
        return p

    def build_view(self, room: Room) -> None:
        # Views populate a Room similarly to diagrams
        room.add("plate", self.build_part("main_plate", "left", Mode.DEFAULT), color="blue")
```

### 5. Export the Provider
Ensure the provider is accessible at the package level so the discovery mechanism can import it.

```python
# src/projects/bracket/__init__.py
from .provider import BracketProvider
```

### 6. Register the Package
Finally, add the import to the top-level projects init file.

```python
# src/projects/__init__.py
from .exhaust_manifolds import ExhaustManifoldsProvider
from .bracket import BracketProvider
```

### 7. Registering Simulation Hooks (Optional)
If your project supports physical simulation (`Mode.SIMULATE`), you should register custom simulation callbacks to manage initialization, joint control, and fluid behavior:

```python
# src/projects/bracket/provider.py
def get_simulate_hooks_impl(self, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
    """Return simulation callbacks mapped to execution hooks."""
    from .simulate_hooks import get_simulate_hooks_impl as impl
    return impl(self, sim_name)
```

Create a `simulate_hooks.py` file within your project package to specify hooks for `Simulate.INIT`, `Simulate.PRE_STEP`, etc.:

```python
# src/projects/bracket/simulate_hooks.py
from provider import Simulate, Room, Bullet, Fluid

def get_simulate_hooks_impl(provider, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
    def on_init(bullet: Bullet, fluid: Fluid) -> None:
        bullet.set_motor_velocity("motor_joint", velocity=10.0)
        
    return {
        Simulate.INIT: on_init,
    }
```

## Core Concepts

### Lazy Initialization
Always use `@cached_property` for `default_config` and any sub-tools (Builders, Configurators). This ensures:
1.  **Reference Integrity**: The `ProviderManager` can swap the `default_config` for a bootstrapped version without your tools holding onto a stale instance.
2.  **Orchestration Timing**: Sub-tools are only created after the `orchestrator` and `app_config` are fully initialized.
3.  **Performance**: Expensive CAD resources are only allocated if the specific project is actually invoked.

### TargetList
When you call `provider.targets`, it returns a `TargetList` helper. You can chain filters like:
`provider.targets.supporting(Action.PART).for_subassemblies(["left"])`

### Orchestration
The `ProviderOrchestrator` handles the execution of tasks. It manages:
1.  **Validation**: Ensuring requested modes and subassemblies exist in the manifest.
2.  **Parallelization**: Running CAD generation tasks across a thread pool.
3.  **Mapping**: Routing `Action.PART` to handlers returning geometry (Builders or Parts), while `Action.DIAGRAM` and `Action.VIEW` route to handlers that populate a `Room` container using `add()` or `add_label()`.

### Configuration Lifecycle
1.  **Discovery**: `ProviderManager` finds all decorated providers.
2.  **Config Sync**: `ProviderManager.load_configs()` takes environment variables (e.g., `EXHAUST_MANIFOLDS__WALL_THICKNESS`) and applies them to the provider's `settings`.
3.  **Execution**: `provider.run(target_list)` triggers the orchestrator.

### Physical Simulation & URDF Export
For parts that participate in physics simulation, you must attach URDF/simulation metadata attributes to the shapes returned by the builders. These properties map to physics behaviors in the PyBullet simulator and JAX fluid engine:

- **Core Physical Attributes**:
  - `urdf_label` (`str`): Unique label for the link in the URDF representation.
  - `urdf_material` (`str`): Material name (e.g., `"petg"`, `"acrylic"`).
  - `urdf_density` (`float`): Density in $\text{kg/m}^3$ used to calculate link mass and inertia.

- **Kinematic & Joint Attributes**:
  - `urdf_parent` (`Optional[str]`): Parent link name in the kinematic tree (`None` for the base/root).
  - `urdf_joint_type` (`Optional[str]`): Joint type connecting to the parent. Allowed values: `"fixed"`, `"revolute"`, `"continuous"`, `"prismatic"`, `"planar"`, or `"spherical"`.
  - `urdf_joint_axis` (`Optional[str]`): Joint axis of motion (formatted as a space-separated string e.g., `"0 0 1"`, `"0 1 0"`, default is `"0 0 1"`).
  - `urdf_joint_lower` (`Optional[float]`): Lower limit for joint motion (in radians or meters, default is `-3.14159`).
  - `urdf_joint_upper` (`Optional[float]`): Upper limit for joint motion (in radians or meters, default is `3.14159`).

- **Motor & Actuation Attributes**:
  - `urdf_motor_type` (`Optional[str]`): Motor control type (e.g., `"velocity"`, `"torque"`).
  - `urdf_motor_target` (`Optional[float]`): Target motor velocity (in rad/s) or torque (in N·m) depending on `urdf_motor_type`.
  - `urdf_motor_force` (`Optional[float]`): Maximum force/torque applied by the motor (default is `10.0`).

- **Rigid-Body Collision Attributes**:
  - `urdf_collision_type` (`URDFCollisionType`): Collision model. Can be:
    - `URDFCollisionType.CONVEX` (`"convex"`): Uses a convex hull representation of the geometry for collision detection.
    - `URDFCollisionType.CONCAVE` (`"concave"`): Uses the full triangular mesh of the geometry.
    - `URDFCollisionType.COMPOUND` (`"compound"`): Uses compound collision shapes.
    - `URDFCollisionType.ANALYTICAL` (`"analytical"`): Uses idealized analytical shapes.
    - `URDFCollisionType.NONE` (`"none"`): Disables collision detection for the link.
  - `urdf_collision_primitives` (`list[dict]`): A list of analytical shapes used for rigid-body collision detection instead of complex meshes. Each dictionary must contain `type` (`URDFCollisionShapeType`) and parameters depending on the type:
    - For `URDFCollisionShapeType.BOX` (`"box"`): `size` (`list[float]`) representing the width, depth, and height.
    - For `URDFCollisionShapeType.CYLINDER` (`"cylinder"`): `radius` (`float`) and `length` (`float`).
    - For `URDFCollisionShapeType.SPHERE` (`"sphere"`): `radius` (`float`).
    - Optional offset keys: `xyz` (`list[float]`) and `rpy` (`list[float]`).

- **Boundary & Fluid Interaction**:
  - `urdf_boundary_friction` (`float`): Coulomb friction coefficient for fluid-boundary interactions.
  - `urdf_boundaries` (`list[BoundaryConfig]`): A list of boundary configurations representing the analytical boundaries of the link.
    This array should be built using the `Room.make_boundary_config` static helper method in `src/provider/room.py` whenever an analytical boundary needs to be defined. The helper function automatically extracts physical dimensions (radius, height, xyz translation, rpy orientation) from the CAD `BuildPart` or shape:
    ```python
    from provider import Room
    
    part.urdf_boundaries = [
        Room.make_boundary_config(
            shape_or_part,
            link_type=LinkType.BASE,
            shape=ShapeType.CYLINDER,
            type=BoundaryType.CAVITY,
            # Custom overrides if needed (e.g. adding extensions, thickness, slots, etc.)
            height=new_height_m,
            thickness=thickness_m,
        )
    ]
    ```
    Each boundary configuration in the array specifies:
    - `shape` (`str`): Geometry shape type (e.g., `"cylinder"`, `"tube"`, `"impeller"`, `"box"`, `"sphere"`, `"plane"`).
    - `type` (`str`): Boundary collision role (e.g., `"cavity"`, `"solid"`, `"solid_cavity"`).
    - `radius` (`float`): Radius in meters.
    - `height` (`float`): Height/length in meters.
    - `thickness` (`float`): Thickness in meters.
    - `xyz` (`list[float]`): Local offset relative to the link coordinate origin.
    - `rpy` (`list[float]`): Local orientation in roll-pitch-yaw.
    - `drain_hole_y` (`float`): Optional. Y coordinate of a drain hole in a cavity ceiling/floor.
    - `drain_hole_radius` (`float`): Optional. Radius of the drain hole.

## Simulation & Physics Best Practices

When designing parts or writing simulation hooks, adhere to these dynamic stability guidelines:

- **SPH Particle Containment**:
  - Always prefer analytical boundaries (`URDFCollisionType.ANALYTICAL`) over concave meshes (`URDFCollisionType.CONCAVE`) for JAX SPH boundaries. They provide significantly faster collision resolution and zero boundary leakage.
  - When defining a cylinder cavity boundary, treat the height as infinite along the local Z axis where possible to prevent particle tunneling under high pressure or tipping angles.
- **Fluid Recycling**:
  - Use `fluid.recycle_fluid = True` when simulating steady-state flows (such as fountains or recirculating pumps).
  - Make sure the recycling boundary coordinates match the physical limits of the container.
- **Numeric Damping**:
  - For long-running simulation validations, use a stabilization damping value (e.g. 0.95) to minimize numeric velocity buildup and unphysical particle ejection.
  - Keep simulation step tolerances loose enough to account for natural numeric sloshing while enforcing volume conservation constraints.
- **Test Markers**:
  - Heavy PyBullet and JAX fluid tests should be marked with `@pytest.mark.slow` so they are excluded from the fast CLI validation pass.

## Testing
Add validation tests in `src/projects/tests/`. Your tests should:
- Verify geometry volumes are non-zero.
- Ensure mirrored parts do not intersect unexpectedly.
- Validate that configuration updates correctly modify the `settings` model.

Run tests for your provider from the repo root using:
```bash
pytest src/projects/tests/test_your_project.py
```

After updating, these commands should be run to ensure proper formatting:
```
ruff format build.py
ruff check build.py
```

This will run unit tests, then build all project files, simulating a release:
```
pytest
python build.py
```

**Note:** All CI gates (tests, linting, and build checks) must pass successfully in the GitHub Actions workflow before a pull request can be merged.

## Debugging

The workspace includes a `.vscode/launch.json` file with pre-configured profiles to help debug scripts and tests.

### Debugging Scripts from the Terminal

If you need to debug a script while passing specific CLI arguments: 
1. Ensure debugpy is installed in your environment (`pip install debugpy`).
2. Start the script using the debugpy wrapper:

```bash
python -m debugpy --listen 5678 --wait-for-client src/build.py 'exhaust_manifolds/*'
```

3. In VS Code, go to the Run and Debug sidebar, select "Python: Attach via Port", and press F5. The script will pause at the start and wait for the debugger to connect. 

### Debugging Unit Tests 

There are two primary ways to debug tests: 

1. Run and Debug Sidebar: Open the test file you want to debug, select the "Python: Debug Unit Tests" configuration, and press F5. This will execute pytest on the currently active file.
2. Testing UI: Use the VS Code Testing panel (beaker icon). You can hover over any detected test and click the Debug Test icon to start a session with breakpoints enabled.

### Attaching to a Running Process

If a script is already executing and you want to inspect its state:

1. Select "Python: Attach using Process ID" from the debug configurations.
2. A list of active processes will appear; select the Python process running your script to attach the debugger immediately.

### Environment Variables

To debug with specific environment overrides, you can add an "env" block or an "envFile": "${workspaceFolder}/.env" entry to your configurations in launch.json.

## Creating a Release

Releases are automated via GitHub Actions and are triggered by pushing a version tag.

1. Ensure your changes are committed and tests pass locally.
2. Create a new release using the `v*` format. Use `v0.0.0` for main:
   ```bash
   gh release create v0.0.0 --generate-notes -p
   ```
   
   For quick experimental releases, you can use a timestamp to ensure a unique tag:
   ```bash
   gh release create v0.0.$(date +%s) --generate-notes -p
   ```
   
   Use `v4.0.x` for V4:
   ```bash
   gh release create v4.0.1 --generate-notes
   ```

To verify the release process, check the "Actions" tab on your GitHub repository after pushing a tag. You can view the progress, logs, and download the generated artifacts from there.
