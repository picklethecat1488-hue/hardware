# Hardware Projects

This repository contains CAD models and designs for various hardware projects:

- [Cat Water Fountain](projects/cat_fountain.md) - A 3D-printable automatic pet cat water fountain with an impeller, delivery tube, and spout.
- [Exhaust Manifolds](projects/exhaust_manifolds.md) - Custom exhaust manifolds to connect the midpipe section of the kit to exhaust tips.
- [Valve Actuator Limiter](projects/valve_actuator_limiter.md) - A mechanical stop to restrict the sweep of the exhaust valve actuator arm.

---

## Getting Started

This project uses [conda](https://conda-forge.org/download/) for dependency management. You can easily setup the build environment using these commands:
```
mamba env create -f environment.yml
conda activate cq
```

Detailed development information can be found in [CONTRIBUTING](CONTRIBUTING.md)


## Building and Running

All utilities use a standardized target specification format:
`[provider/target][_subassembly][:action[/mode]]`

*   **Target**: The project and part name (e.g., `tube/driver`). Wildcards like `tube/*` are supported.
*   **Subassembly**: Optional variant (e.g., `tube/driver_left`).
*   **Action/Mode**: Optional overrides (e.g., `tube/driver:part/print`).

All commands should be run from the repository root.

### Building Geometry

The build command generates geometry and diagrams:
```bash
python tools/build.py

# Build all parts from the exhaust_manifolds project
python tools/build.py 'exhaust_manifolds/*'

# Build only diagrams for all manifolds
python tools/build.py --parts=false 'exhaust_manifolds/*'
```

### Geometry Configuration

If project measurements or parameters have changed, run the configuration utility to optimize part placement and geometry:
```bash
# Configure and optimize all projects
python tools/config.py

# Configure only the driver manifold
python tools/config.py exhaust_manifolds/driver

# Run only text logo placement optimization
python tools/config.py -m text
```

### Listing Targets and Outputs

Use the list utility to list available targets or predict the exact files that the build process will export:

```bash
# List all valid targets across all actions and modes
python tools/list.py targets

# List all files the build will export without actually building them
python tools/list.py outputs

# List build outputs for specific targets
python tools/list.py outputs 'exhaust_manifolds/*'
```

### Geometry Visualization
Use the interactive CAD/PCB Scope Workstation (`tools/scope.py`) to inspect 3D geometry and multi-layer PCBs with Blender-style navigation (`MMB` orbit, `Shift+MMB` pan, scroll zoom, Numpad presets), face highlighting, 2D/3D diagram markups, and one-click **Target Bug** reporting into Forge.

```bash
# Launch interactive CAD/PCB Scope workstation with Target Chooser modal:
python tools/scope.py

# Inspect specific target in native Scope workstation:
python tools/scope.py exhaust_manifolds/driver

# View the global wire path for all manifold assemblies:
python tools/scope.py exhaust_manifolds/wire

# View all printable parts for all manifolds:
python tools/scope.py 'exhaust_manifolds/*:part/print'

# View PCB target with interactive multi-layer toggling and net highlighting:
python tools/scope.py carrier_board/carrier_board:pcb

# Run and inspect simulation targets:
python tools/scope.py cat_fountain/product:simulate
```

### Simulating Rooms and Visualizing in Scope

For targets that support simulation (e.g., the cat water fountain room), you can run a simulation and visualize it in real-time in Scope Workstation:

```bash
# Run the simulation and open in Scope:
python tools/scope.py cat_fountain/product:simulate
```

### Wiring Diagrams & PCB Manufacturing Pipeline

This project includes a declarative wiring and PCB engine driven by native KiCad headless compilation:

*   **Pipeline Architecture**:
    `pcb_materials.yaml imports -> manifest.yaml -> .kicad_pcb / .kicad_sch targets -> kicad_cli -> board and schematic files`
*   **KiCad Dependency (`kicad-cli`)**:
    The build toolchain uses `kicad-cli` (v7+ or v8+) to generate industry-standard CAM manufacturing files (RS-274X Gerbers, Excellon drills, IPC-2581/gbrjob). It automatically detects local KiCad installations (`brew install --cask kicad` on macOS, `apt-get install kicad` on Linux, or Windows installation) or custom paths via `KICAD_CLI_BIN`. Remote execution can be dispatched via `tools/anvil run`.
*   **Viewing PCB & Schematic Files**:
    *   **In CAD/PCB Scope Workstation**: Run `python tools/scope.py carrier_board/carrier_board:pcb` to inspect multi-layer copper ribbons, pads, vias, silkscreen, and substrate with interactive net highlighting, component inspection, and Blender navigation controls.
    *   **In Browser**: Inspect layer stacks instantly by dragging the `build/board/<project>/` folder into [tracespace.io/view](https://tracespace.io/view/) or online fab viewers (JLCPCB / PCBWay).
    *   **SVG Schematics**: Vector schematics (`build/schematics/<project>/<project>_schematic.svg`) can be opened directly in any browser or SVG viewer.

To build PCB and wiring outputs:
```bash
# Build PCB board, schematics, CAM files, and BOM/CPL:
python tools/build.py carrier_board:pcb

# Build wiring diagrams:
python tools/build.py cat_fountain/wiring
```
---

## Running Tests

This project uses `pytest` for testing.

To run the default test suite (skips slow tests for a fast local feedback loop):
```bash
pytest
```

To run only the slow geometry validation tests (which perform expensive 3D CAD boolean checks):
```bash
pytest -m "slow"
```

To run all tests (both fast and slow):
```bash
pytest -m "slow or not slow"
```
