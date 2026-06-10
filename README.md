## Getting Started

This project uses [conda](https://conda-forge.org/download/) for dependency management. You can easily setup the build environment using these commands:
```
mamba env create -f environment.yml
conda activate cq
```

Detailed development information can be found in [CONTRIBUTING](CONTRIBUTING.md)


## Building and Running

The build command will build project files. This (and all commands below) support wildcards for target resolution. Note that all commands should be run from the repository root:
```bash
python src/build.py

# Build all parts from the exhaust_manifolds project
python src/build.py 'exhaust_manifolds/*'

# Build the exhaust_manifolds project diagram
python src/build.py -pno 'exhaust_manifolds/*'
```

### Configuration

If project measurements or parameters have changed, run the configuration utility to optimize part placement and geometry:
```bash
# Configure and optimize all projects
python src/config.py

# Configure only the driver manifold
python src/config.py exhaust_manifolds/driver

# Run only text logo placement optimization
python src/config.py -m text
```

### Visualization
Use the viewer to inspect geometry in VS Code using the `ocp_vscode` extension.

```bash
# List all available targets and their supported actions:
python src/view.py --list

# View the driver manifold part
python src/view.py exhaust_manifolds/driver

# View the global wire path for all manifold assemblies
python src/view.py exhaust_manifolds/wire

# View all printable parts for all manifolds 
python src/view.py 'exhaust_manifolds/*/part/*'
```