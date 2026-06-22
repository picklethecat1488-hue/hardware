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
Use the viewer to inspect geometry in VS Code using the `ocp_vscode` extension.

```bash
# List all available targets and their supported visual actions:
python src/view.py --list

# View the driver manifold part
python src/view.py exhaust_manifolds/driver

# View the global wire path for all manifold assemblies
python src/view.py exhaust_manifolds/wire

# View all printable parts for all manifolds 
python src/view.py 'exhaust_manifolds/*:part/print'
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

```