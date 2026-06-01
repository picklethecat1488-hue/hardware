## Getting Started

This project uses [conda](https://conda-forge.org/download/) for dependency management. You can easily setup the build environment using these commands:
```
mamba env create -f environment.yml
conda activate cq
```

Detailed development information can be found in [CONTRIBUTING](CONTRIBUTING.md)


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

If you want to view parts or profiles, use `view.py`. For example:
```
python view.py parts
```

