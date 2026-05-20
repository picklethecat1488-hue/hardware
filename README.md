# Exhaust Manifolds

I got an [IE exhaust kit](http://ecstuning.com/b-integrated-engineering-parts/ie-b9-sq5-cat-back-exhaust-system/ieexcz1~int/?__cf_chl_tk=3.sM98lc3zO6.TljKxYxHSWbfedp2mBXP4KXyj35eUw-1776977950-1.0.1.1-Kr.Mao_o47HH8.Kwx2htw8uEozn_W59rgKzPN0KS9hY) for my car and after looking around, decided the best way to add some [exhaust tips](https://parts.audibethesda.com/p/Audi__SQ5/SQ5-Sport-Exhaust--Black/109131021/ZAW071897EDSP.html) to the kit and make it look nice was by creating some custom exhaust manifolds to connect the midpipe section of the kit to the pipes I got.

I initially prototyped the manifolds shapes mesh generation in Jupyter Lab using mainly cadquery and numpy, but have since totally redesigned my code to have it's own build and configuration processes, as well as many design and functional tests suites.

The manifolds themselves include a 3" clamp bed in the middle, as well as lap jointing to ensure they are align with each other correctly. The outer diameter is 2.5" with a 3mm wall thickness. The production process is 316L stainless steel using [SLM](https://www.pcbway.com/rapid-prototyping/3D-Printing/3D-Printing-SLM.html).

## Releases

I'm not anticipating any more releases of the manifolds tubing after V4 completes production, but there is a potential to design some kind of blockoff plate or dummy exhaust valve for a dash light I'm getting in a future release:

- **V3** This completed production with the supplier after about 3 weeks. There were a couple issues, but the main issue was that half these parts are unusuable due to a geometry error I introduced attempting to place them flat on the print bed. Oops!!
- **V4** These are currenty being scheduled for production. They are pretty much a total redesign of V3, and include a bunch of fixed issues.

## Files

There are two manifolds, driver and passenger. The manifolds are further separated into left and right sides, and must be sealed together with a high temperature adhesive or gasket sealer to prevent leaks:

![Diagram](diagram.svg)

*Exploded assembly diagram.*

- **build.py** \- contains the project source.
- **exhaust\_manifolds.ipynb** \- contains examples of using the `Builder` class.
- **exhaust\_manifolds\_v{x}\_driver\_left.stl** \- the left side of the driver manifold.  
- **exhaust\_manifolds\_v{x}\_driver\_right.stl** \- the right side of the driver manifold.  
- **exhaust\_manifolds\_v{x}\_passenger\_left.stl** \- the left side of the passenger manifold.  
- **exhaust\_manifolds\_v{x}\_passenger\_right.stl** \- the right side of the passenger manifold.
- **build/\*\*** \- contains output from the last build.
- **tests/\*\*** \- contains test files.

## Getting Started

This project uses [conda](https://conda-forge.org/download/) for dependency management. You can easily setup the build environment using these commands:
```
mamba env create -f environment.yml
conda activate cq
```

## Building and Running

This will run unit tests, then build all project files:
```
pytest
python build.py
```

If the profile of the exhaust tubes has changed, you may need to run this command to get the correct output prior to running `build.py`:
```
python config.py
```

Prior to updating `build.py`, these commands should be run to ensure proper formatting:
```
ruff format build.py
ruff check build.py
```

There is a notebook showing usage examples named `exhaust_manifolds.ipynb`. I use the lab GUI to modify the notebook. Prior to committing, you should run nbstripout prior to pushing any changes to the notebook to make sure the notebook is free of artifacts.

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
