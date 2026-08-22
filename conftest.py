"""Pytest configuration hooks and global fixtures."""

import os

# Force JAX to run exclusively in CPU mode during unit tests to avoid MPS (Apple Silicon GPU)
# compilation deadlocks, resource constraints, and multi-process GPU conflicts.
os.environ["JAX_PLATFORMS"] = "cpu"
os.environ["JAX_PLATFORM_NAME"] = "cpu"


def pytest_cmdline_main(config):
    """Check options before test session runs."""
    # Disable parallel execution (xdist) for slow resource-intensive tests to prevent deadlocks
    markexpr = getattr(config.option, "markexpr", "")
    if "slow" in markexpr:
        if hasattr(config.option, "numprocesses"):
            config.option.numprocesses = 0


def pytest_xdist_auto_num_workers(config):
    """Dynamically determine the number of xdist workers."""
    markexpr = getattr(config.option, "markexpr", "")
    if "slow" in markexpr:
        # Force 0 workers (sequential execution) for slow tests to prevent GPU/UDS deadlocks
        return 0
    # Let xdist decide automatically for other tests
    return None
