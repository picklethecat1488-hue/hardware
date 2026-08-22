"""Pytest configuration hooks and global fixtures."""

import os

# Force JAX to run exclusively in CPU mode during unit tests to avoid MPS (Apple Silicon GPU)
# compilation deadlocks, resource constraints, and multi-process GPU conflicts.
os.environ["JAX_PLATFORMS"] = "cpu"
os.environ["JAX_PLATFORM_NAME"] = "cpu"


def pytest_configure(config):
    """Configure pytest settings dynamically."""
    # Double-guard: Disable parallel execution (xdist) for slow resource-intensive tests to prevent deadlocks
    markexpr = getattr(config.option, "markexpr", "")
    if "slow" in markexpr:
        if hasattr(config.option, "numprocesses"):
            config.option.numprocesses = 0
