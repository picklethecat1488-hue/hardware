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
Create a new directory under `src/projects/` (e.g., `src/projects/bracket/`).

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
  color: [0.7, 0.7, 0.7, 1.0]
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
from build123d import *
from pathlib import Path
from provider import Provider, Action, Mode, discover_provider
from projects_config import TubeConfig # Or a custom Pydantic model

@discover_provider
class BracketProvider(Provider):
    @property
    def default_config(self):
        # Define where to find measurements
        return TubeConfig(
            measurements_path=str(Path(__file__).parent / "measurements.yaml")
        )

    @property
    def part(self):
        return {name: self.build_part for name in self.targets.supporting(Action.PART)}

    def build_part(self, target: str, subassembly: str, mode: Mode) -> Part:
        with BuildPart() as p:
            Box(10, 20, 5)
            if subassembly == "right":
                mirror(about=Plane.YZ)
        return p.part
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
from .tube import TubeProvider
from .bracket import BracketProvider
```

## Core Concepts

### TargetList
When you call `provider.targets`, it returns a `TargetList` helper. You can chain filters like:
`provider.targets.supporting(Action.PART).for_subassemblies(["left"])`

### Orchestration
The `ProviderOrchestrator` handles the execution of tasks. It manages:
1.  **Validation**: Ensuring requested modes and subassemblies exist in the manifest.
2.  **Parallelization**: Running CAD generation tasks across a thread pool.
3.  **Mapping**: Routing `Action.PART` to the `part` registry and `Action.VIEW` to the `view` registry.

### Configuration Lifecycle
1.  **Discovery**: `ProviderManager` finds all decorated providers.
2.  **Config Sync**: `ProviderManager.load_configs()` takes environment variables (e.g., `TUBE__WALL_THICKNESS`) and applies them to the provider's `settings`.
3.  **Execution**: `provider.run(target_list)` triggers the orchestrator.

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

## Creating a Release

Releases are automated via GitHub Actions and are triggered by pushing a version tag.

1. Ensure your changes are committed and tests pass locally.
2. Create a new release using the `v*` format. Use `v0.0.0` for main:
   ```bash
   gh release create v0.0.0 --generate-notes -p
   ```
   Use `v4.0.x` for V4:
   ```bash
   gh release create v4.0.1 --generate-notes
   ```

To verify the release process, check the "Actions" tab on your GitHub repository after pushing a tag. You can view the progress, logs, and download the generated artifacts from there.