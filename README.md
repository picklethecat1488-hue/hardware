# Hardware Engineering & CAD/PCB/Simulation Workstation

Declarative 3D CAD (`build123d`), multi-layer KiCad PCB design & CAM compilation, coupled PyBullet + JAX SPH/LBM fluid physics simulation, and interactive zero-globals engineering workstations (**Scope** & **Forge**).

---

## Featured Demo: Interactive Hardware Tools Walkthrough

<div align="center">
  <a href="https://www.youtube.com/watch?v=Q7QWYVTvzCw">
    <img src="https://img.youtube.com/vi/Q7QWYVTvzCw/maxresdefault.jpg" alt="Watch the Hardware Tools Demo on YouTube" width="840" />
  </a>
  <p>
    <a href="https://www.youtube.com/watch?v=Q7QWYVTvzCw"><strong>▶ Watch the Hardware Tools Demo on YouTube</strong></a>
  </p>
</div>

The walkthrough showcases the end-to-end local hardware engineering loop:
- **Scope Workstation (`tools/scope.py`)**: Real-time 2× Retina Three.js + custom GLSL inspection across **3D CAD** assemblies, **2D Multi-Layer PCB** GPU SDF copper/pad/via/silkscreen rendering with magnetic `mm`/`mil` ruler & one-click KiCad launch, **Exploded & Wiring Diagrams**, and undecimated **SPH/LBM Fluid Simulation** playback with 2D/3D viewport markups and instant **Target Bug** filing.
- **Forge Workstation (`tools/forge.py`)**: Unified Quake-styled **Smartlog DAG & Diff Viewer**, inline **Code Review**, and **Bug Tracker** backed by dual-layer SQLite + detached-worktree Markdown synchronization and Git LFS attachments.

---

## Quick Start

```bash
mamba env create -f environment.yml && conda activate cq

python tools/scope.py          # Launch interactive CAD / PCB / Simulation / Diagram workstation
python tools/forge.py          # Launch VCS Diff / Smartlog / Code Review / Bug Tracker workstation
./tools/verify.py              # Run full pre-commit verification (Python, Ruff, JS lint, Node & Pytest)
```

For full CLI flags, target syntax, build commands, and test runners, see **[CLI Tools, Build & Workstation Workflows](docs/cli_and_workflows.md)**.

---

## Projects

| Project | Description |
| :--- | :--- |
| **[Carrier Board 2.0](projects/carrier_board.md)** | 6-layer rigid-flex sensor fusion, ML gesture, and BLE carrier board (NXP MCX N947) with declarative routing, DRC, and turnkey CAM outputs. |
| **[Cat Water Fountain](projects/cat_fountain.md)** | 3D-printable automatic pet water fountain with snap-fit enclosures, brushless impeller pump, and coupled PyBullet + JAX fluid simulation. |
| **[Exhaust Manifolds](projects/exhaust_manifolds.md)** | Parametric multi-branch exhaust manifolds connecting midpipe sections to exhaust tips with automated geometry optimization. |
| **[Valve Actuator Limiter](projects/valve_actuator_limiter.md)** | Mechanical travel limiter restricting the sweep of an exhaust valve actuator arm. |

---

## Documentation Index

- **[CLI Tools, Build & Workstation Workflows](docs/cli_and_workflows.md)** — Environment setup, target specifiers, `build.py`, `config.py`, `list.py`, `scope.py`, `forge.py`, and `./tools/verify.py`.
- **[Declarative Wiring & PCB Engine](docs/declarative_wiring_pcb.md)** — `build123d` component footprints, declarative netlists & trace routing, schematic sheets, DRC, and headless `kicad-cli` CAM generation.
- **[JavaScript Style, Zero-Globals & CAD Viewport Architecture](docs/javascript_style_architecture.md)** — Modular `js/` ES architecture, strict `runtime_context.js` global isolation, GPU SDF PCB shaders, and parallel `node --test` suites.
- **[Physics & URDF Simulation Guidelines](docs/physics_urdf_simulation.md)** — Kinematic joints, `URDFMetadata` / `URDFBoundary` CAD-derived collision primitives, and PyBullet simulation hooks.
- **[SPH Fluid Dynamics & Numerical Stability](docs/sph_fluid_dynamics.md)** — JAX fluid simulation kernels, analytical cavity containment, fluid recycling, and flow telemetry metrics.
- **[VCS Workstation, Code Review & Quake HUD Templates](docs/vcs_code_review.md)** — `tools/forge.py` architecture, Smartlog DAG, dual-layer SQLite/Markdown sync, and Git LFS bug attachments.
- **[Remote Cloud Runner (`anvil` / Vast.ai)](docs/remote_cloud_runner.md)** — Ephemeral GPU provisioning, remote test/simulation execution, and Close-of-Business auto-release.
- **[Consignment Sourcing & Shipping Guide](docs/consignment_sourcing_and_shipping_guide.md)** & **[Component Downselection Report](docs/downselection_report.md)** — Turnkey PCBA procurement, component trade studies, and BOM consignment procedures.
- **[Contributing Guide](CONTRIBUTING.md)** — Creating new geometry providers, manifests, VS Code debugging profiles, and release tagging.
