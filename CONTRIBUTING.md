# Contributing

## Source Paths

 - **src/build.py** - Orchestrates the generation and export of 3D-printable geometry.
 - **src/config.py** - Automated utility for part placement and geometry optimization.
 - **src/view.py** - Interactive CAD visualization tool for inspection and debugging.
 - **src/code_review.py** - Interactive Quake-themed code review tool and Markdown report generator.
 - **src/bug_report.py** - Interactive bug reporting terminal, web workstation, and Markdown tracker.
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
from projects_config import ExhaustManifoldsConfig  # Or a custom Pydantic model


@discover_provider
class BracketProvider(Provider):
    @cached_property
    def default_config(self):
        return ExhaustManifoldsConfig(measurements_path=str(Path(__file__).parent / "measurements.yaml"))

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

- **Derived Geometry Properties**:
  - `urdf_height` (`float`): Derived height of the shape in meters (calculated from the shape's Z-axis bounding box dimensions).
  - `urdf_thickness` (`float`): Derived minimum thickness of the shape in meters (calculated from the minimum bounding box dimension).
  - These properties are dynamically attached to the build123d `Shape` class, making them queryable directly on any shape or geometry object (e.g., `shape.urdf_height`).

- **Boundary & Fluid Interaction**:
  - `urdf_boundary_friction` (`float`): Coulomb friction coefficient for fluid-boundary interactions.
  - `urdf_boundaries` (`list[BoundaryConfig]`): A list of boundary configurations representing the analytical boundaries of the link. Instead of manually constructing these via `Room.make_boundary_config`, you can now use the `URDFBoundary` helper within a `URDFMetadata` block. `URDFBoundary` automatically extracts geometry dimensions and registers the resulting `BoundaryConfig` with the active metadata.
    ```python
    from provider import URDFMetadata, URDFBoundary, LinkType, ShapeType, BoundaryType, URDFCollisionType

    with URDFMetadata(
        label=target,
        material=self.settings.material,
        density=self.settings.density,
        boundary_friction=self.settings.boundary_friction,
        collision_type=URDFCollisionType.ANALYTICAL,
    ) as meta:
        URDFBoundary(
            part=meta.geometry,
            link_type=LinkType.BASE,
            shape=ShapeType.CYLINDER,
            type=BoundaryType.CAVITY,
        )
    ```
  - Each `BoundaryConfig` includes fields such as `shape`, `type`, `radius`, `height`, `thickness`, `xyz`, `rpy`, etc.
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

## PCB Design & KiCad Toolchain

The repository incorporates an end-to-end PCB design, simulation, and manufacturing pipeline:

### 1. Declarative Pipeline Flow
```
pcb_materials.yaml imports -> manifest.yaml -> .kicad_pcb / .kicad_sch targets -> kicad_cli -> board and schematic files
```
- **Materials Library**: Physical and electrical properties (dielectric constants, loss tangents, copper thickness, solder mask) are declared in `src/projects/pcb_materials.yaml` and imported into project manifests.
- **Manifest Integration**: PCB targets are registered in the project's `manifest.yaml` under `pcb:`.
- **Native KiCad Generation**: Board geometry and schematics are generated directly into canonical `.kicad_pcb` and `.kicad_sch` formats via clean Jinja templates (`src/provider/templates/kicad_pcb.j2`).
- **Headless CAM Compilation**: Manufacturing files (RS-274X Gerbers, Excellon NC drills, Gerber job files) are compiled strictly by `kicad-cli` rather than hand-rolled custom formatters.

### 2. KiCad Dependency & Multi-Platform Support
- **Local Installation**: Install KiCad (v7+ or v8+) locally via Homebrew on macOS (`brew install --cask kicad`), apt on Linux (`sudo apt-get install -y kicad`), or the Windows installer from [kicad.org](https://www.kicad.org/).
- **Discovery & Binary Override**: `KiCadCLI` automatically discovers standard installation paths across macOS, Linux, and Windows, and respects PATH and the `KICAD_CLI_BIN` environment variable override. Remote execution can be dispatched via `bin/anvil run`.

### 3. Viewing & Inspecting Board Files
- **In VS Code (KiCode)**: Install the recommended [KiCode](https://marketplace.visualstudio.com/items?itemName=SajadGhorbani.KiCode) (`sajadghorbani.kicode`) extension (powered by KiCanvas). Opening any `.kicad_pcb` or `.kicad_sch` file opens an interactive webview tab with layer toggling, zoom/pan, net highlighting, and component inspection directly in VS Code.
- **Interactive Viewer CLI (`view.py`)**:
  ```bash
  # View PCB target (opens KiCode tab in VS Code and renders 3D substrate in ocp_vscode):
  python src/view.py test_board:pcb

  # View a direct board or schematic file:
  python src/view.py build/board/test_board/test_board.kicad_pcb
  ```
- **In-Browser Gerber Viewers**: Drag the `build/board/<project>/` folder into open-source [tracespace.io/view](https://tracespace.io/view/) or online fab viewers (JLCPCB, PCBWay).
- **Vector Schematics**: Open `build/schematics/<project>/<project>_schematic.svg` in any browser or SVG editor.

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

## Interactive Code Review

Before submitting or approving pull requests, you can audit commits and staged changes using the interactive Quake-styled code review tool:

```bash
# Review uncommitted working tree changes (staged and unstaged)
python src/code_review.py

# Review specific commits or revision ranges
python src/code_review.py HEAD~1 HEAD
python src/code_review.py 542007d

# Launch on custom port or output path
python src/code_review.py --port 8765 --output build/CR.md

# Directly export Markdown report from existing review state without launching the server
python src/code_review.py --export-only
```

### Review Features & Workflow
- **Retro Console UI**: 3-column layout displaying the revision stream, changed files list, and side-by-side or unified syntax-highlighted diffs.
- **Line Selection & Inline Feedback**: Click or shift-click diff line numbers to select line ranges and submit structured review findings tagged as `[MUST FIX]`, `[PROPOSAL]`, or `[NIT]`.
- **Integrated Quake CLI**: Bottom terminal console supporting commands such as `goto <path> [line]`, `must_fix <msg>`, `proposal <msg>`, `nit <msg>`, `reviewed`, `approve`, and `reject`.
- **Automated Termination & Markdown Export**: Submitting a final verdict (`approve` / `lgtm` or `reject` / `changes`) automatically compiles and exports the full review audit log to `build/CR.md` and gracefully shuts down the local server, returning control to your terminal.
- **VS Code Integration**: By default, opens inside VS Code via Simple Browser (`--browser vscode`) with task bindings in `.vscode/tasks.json`.

## Interactive Bug Tracker & Issue Management

You can log, triage, track, and resolve bugs using the interactive Quake-styled bug tracking workstation:

```bash
# Launch interactive bug reporting web workstation
python src/bug_report.py

# List active / open bugs directly in the terminal
python src/bug_report.py --list
python src/bug_report.py --list --open

# Quickly register an issue from the CLI
python src/bug_report.py --add "Antenna on Q1" --severity HIGH --category PCB --component carrier_board

# Resolve a bug with notes
python src/bug_report.py --resolve BUG-014 --notes "Added bug filtering and status toggles"

# Launch on custom port or output path
python src/bug_report.py --port 8766 --output build/BUGS.md

# Directly export Markdown report from existing state without launching the server
python src/bug_report.py --export-only
```

### Bug Tracker Features & Workflow
- **Retro Quake Workstation UI**: Styled with the GLQuake console aesthetic, featuring CRT scanlines, beveled stone plaque panels, and interactive Quake 3D embossed controls.
- **Bug Status Filtering**: Filter issues by status (`OPEN`, `ALL`, `RESOLVED`), with resolved bugs hidden by default so developers focus immediately on active blockers.
- **Clipboard & File Attachments**: Drag and drop or paste (⌘V / Ctrl+V) screenshots, images, logs, PDFs, and code references directly into issue reports with live previews.
- **Automated Markdown Synchronization**: Changes made in the workstation or CLI automatically persist to `build/bugs_state.json` and sync seamlessly to GitHub-flavored Markdown in `build/BUGS.md`.
- **Graceful Termination**: Clicking "Save and Exit" saves the active bug, syncs `build/BUGS.md`, and gracefully shuts down the server, releasing terminal control.

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

Releases are automated via GitHub Actions and are triggered by pushing a version tag. Release notes are automatically compiled by **release-drafter** using merged pull request details.

1. Ensure your changes are committed and tests pass locally.
2. Create and push a new tag, or create a release via the GitHub CLI.

### Option A: Using Git Tags
Create and push the version tag directly. The workflow will automatically compile the release notes and draft/publish the release.

```bash
# For main:
git tag v0.0.0
git push origin v0.0.0

# For quick experimental releases (using a timestamp):
git tag v0.0.$(date +%s)
git push origin v0.0.$(date +%s)
```

### Option B: Using GitHub CLI (`gh`)
Create a release using `gh`. Note that you do not need the `--generate-notes` flag, as the CI release workflow will use **release-drafter** to populate the release body.

```bash
# For main (prerelease):
gh release create v0.0.0 -p

# For quick experimental releases:
gh release create v0.0.$(date +%s) -p

# For V4:
gh release create v4.0.1
```

To verify the release process, check the "Actions" tab on your GitHub repository after pushing a tag. You can view the progress, logs, and download the generated artifacts from there.
