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

### Geometry Visualization
Use the viewer to inspect geometry in VS Code using the `ocp_vscode` extension.

```bash
# List all available targets and their supported actions:
python src/view.py --list

# View the driver manifold part
python src/view.py exhaust_manifolds/driver

# View the global wire path for all manifold assemblies
python src/view.py exhaust_manifolds/wire

# View all printable parts for all manifolds 
python src/view.py 'exhaust_manifolds/*:part/print'
```