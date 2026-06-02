## Getting Started

This project uses [conda](https://conda-forge.org/download/) for dependency management. You can easily setup the build environment using these commands:
```
mamba env create -f environment.yml
conda activate cq
```

Detailed development information can be found in [CONTRIBUTING](CONTRIBUTING.md)


## Building and Running

This will run unit tests, then build all project files. Note that all commands should be run from the repository root:
```
pytest
python build.py
```

If the profile of the exhaust tubes has changed, you may need to run this command to get the correct output prior to running `build.py`:
```
python config.py
```

If you want to view parts or profiles, use `view.py`. For example:
```
python view.py parts
```

There is a notebook showing usage examples named `exhaust_manifolds.ipynb`. I use the lab GUI to modify the notebook. Prior to committing, you should run nbstripout prior to pushing any changes to the notebook to make sure the notebook is free of artifacts.
