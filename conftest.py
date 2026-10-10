"""Pytest configuration hooks and global fixtures."""

import os

# Force JAX to run exclusively in CPU mode during unit tests to avoid MPS (Apple Silicon GPU)
# compilation deadlocks, resource constraints, and multi-process GPU conflicts.
os.environ["JAX_PLATFORMS"] = "cpu"
os.environ["JAX_PLATFORM_NAME"] = "cpu"

from provider.utils import initialize_jax_environment

initialize_jax_environment()


def is_slow_marker_selected(markexpr: str) -> bool:
    """Return True if the pytest marker expression explicitly selects 'slow' tests.

    Properly handles negations such as 'not slow' or '(not slow)' without mistakenly
    treating substring 'slow' in 'not slow' as selecting slow tests.
    """
    if not markexpr:
        return False
    import re

    if not re.search(r"\bslow\b", markexpr):
        return False

    try:
        from _pytest.mark.expression import Expression

        expr = Expression.compile(markexpr)
        # If an item matching all markers (including 'slow') fails the expression,
        # then 'slow' is negated (e.g. 'not slow') and slow tests cannot run.
        return bool(expr.evaluate(lambda name: True))
    except Exception:
        tokens = re.split(r"[\s()]+", markexpr.strip())
        for i, tok in enumerate(tokens):
            if tok == "slow":
                if i > 0 and tokens[i - 1] == "not":
                    continue
                return True
        return False


def pytest_cmdline_main(config):
    """Check options before test session runs."""
    # Disable parallel execution (xdist) for slow resource-intensive tests to prevent deadlocks
    markexpr = getattr(config.option, "markexpr", "")
    if is_slow_marker_selected(markexpr):
        if hasattr(config.option, "numprocesses"):
            config.option.numprocesses = 0


def pytest_xdist_auto_num_workers(config):
    """Dynamically determine the number of xdist workers."""
    markexpr = getattr(config.option, "markexpr", "")
    if is_slow_marker_selected(markexpr):
        # Force 0 workers (sequential execution) for slow tests to prevent GPU/UDS deadlocks
        return 0
    # Let xdist decide automatically for other tests
    return None
