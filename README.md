# Hardware Projects

This repository contains CAD models and designs for various hardware projects:

- [Cat Water Fountain](src/projects/cat_fountain.md) - A 3D-printable automatic pet cat water fountain with an impeller, delivery tube, and spout.
- [Exhaust Manifolds](src/projects/exhaust_manifolds.md) - Custom exhaust manifolds to connect the midpipe section of the kit to exhaust tips.
- [Valve Actuator Limiter](src/projects/valve_actuator_limiter.md) - A mechanical stop to restrict the sweep of the exhaust valve actuator arm.

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
python src/build.py

# Build all parts from the exhaust_manifolds project
python src/build.py 'exhaust_manifolds/*'

# Build only diagrams for all manifolds
python src/build.py --parts=false 'exhaust_manifolds/*'
```

### Geometry Configuration

If project measurements or parameters have changed, run the configuration utility to optimize part placement and geometry:
```bash
# Configure and optimize all projects
python src/config.py

# Configure only the driver manifold
python src/config.py exhaust_manifolds/driver

# Run only text logo placement optimization
python src/config.py -m text
```

### Listing Targets and Outputs

Use the list utility to list available targets or predict the exact files that the build process will export:

```bash
# List all valid targets across all actions and modes
python src/list.py targets

# List all files the build will export without actually building them
python src/list.py outputs

# List build outputs for specific targets
python src/list.py outputs 'exhaust_manifolds/*'
```

### Geometry Visualization
Use the viewer to inspect geometry in VS Code using the `ocp_vscode` extension. For PCB targets, `view.py` also opens the native board file in VS Code using the interactive [KiCode](https://marketplace.visualstudio.com/items?itemName=SajadGhorbani.KiCode) extension.

```bash
# List all available targets and their supported visual actions:
python src/view.py --list

# View the driver manifold part
python src/view.py exhaust_manifolds/driver

# View the global wire path for all manifold assemblies
python src/view.py exhaust_manifolds/wire

# View all printable parts for all manifolds 
python src/view.py 'exhaust_manifolds/*:part/print'

# View PCB target (opens interactive KiCode tab in VS Code and shows 3D substrate in ocp_vscode):
python src/view.py test_board:pcb
python src/view.py test_board/carrier_pcb

# View any compiled KiCad PCB or schematic file directly in VS Code:
python src/view.py build/board/test_board/test_board.kicad_pcb
```

### Simulating Rooms and Visualizing in Rerun

For targets that support simulation (e.g., the cat water fountain room), you can run a PyBullet physics simulation and visualize it in real-time using Rerun. Rerun runs headless under DIRECT physics client mode and spawns the visualization automatically.

```bash
# Run the simulation and spawn the Rerun visualizer:
python src/view.py cat_fountain/product:view/simulate

# Run the simulation for a specific number of steps:
python src/view.py cat_fountain/product:view/simulate -s 500

# Skip compiling parts and URDFs prior to starting the simulation:
python src/view.py cat_fountain/product:view/simulate --no-build

# Save the simulation recording to a (.rrd) file to upload to rerun.io:
python src/view.py cat_fountain/product:view/simulate --save-rrd output.rrd
```

### Wiring Diagrams & PCB Manufacturing Pipeline

This project includes a declarative wiring and PCB engine driven by native KiCad headless compilation:

*   **Pipeline Architecture**:
    `pcb_materials.yaml imports -> manifest.yaml -> .kicad_pcb / .kicad_sch targets -> kicad_cli -> board and schematic files`
*   **KiCad Dependency (`kicad-cli`)**:
    The build toolchain uses `kicad-cli` (v7+ or v8+) to generate industry-standard CAM manufacturing files (RS-274X Gerbers, Excellon drills, IPC-2581/gbrjob). It automatically detects local KiCad installations (`brew install --cask kicad` on macOS or `apt-get install kicad` on Linux) and seamlessly falls back to remote cloud execution on `anvil` when not installed locally.
*   **Viewing PCB & Schematic Files**:
    *   **In VS Code**: Install the recommended [KiCode](https://marketplace.visualstudio.com/items?itemName=SajadGhorbani.KiCode) (`sajadghorbani.kicode`) extension (powered by KiCanvas) to inspect `.kicad_pcb` and `.kicad_sch` with interactive zoom, pan, layer toggling, net highlighting, and component inspection directly in VS Code editor tabs. Alternatively, use the **KiCad PCB Viewer** (`kicad-pcb-viewer`) or **Gerber Viewer** extension for `.gbr` layers.
    *   **In Browser**: Inspect layer stacks instantly by dragging the `build/board/<project>/` folder into [tracespace.io/view](https://tracespace.io/view/) or online fab viewers (JLCPCB / PCBWay).
    *   **SVG Schematics**: Vector schematics (`build/schematics/<project>/<project>_schematic.svg`) can be opened directly in any browser or SVG viewer.

To build PCB and wiring outputs:
```bash
# Build PCB board, schematics, CAM files, and BOM/CPL:
python src/build.py test_board:pcb

# Build wiring diagrams:
python src/build.py cat_fountain/wiring
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
