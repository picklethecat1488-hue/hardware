"""Pytest configuration hooks and global fixtures."""

import os
from pathlib import Path

# Limit BLAS, OpenMP, and XLA threading per worker to avoid pthread limit exhaustion in containers
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("XLA_FLAGS", "--xla_cpu_multi_thread_eigen=false")

# Cap CPU core affinity to at most 8 on high-core Linux systems to prevent excessive
# Eigen/OpenBLAS thread pool allocations that exhaust container thread limits.
if hasattr(os, "sched_getaffinity") and hasattr(os, "sched_setaffinity"):
    try:
        current_affinity = sorted(os.sched_getaffinity(0))
        if len(current_affinity) > 8:
            os.sched_setaffinity(0, set(current_affinity[:8]))
    except OSError:
        pass

# Limit parallel xdist workers to at most 8 to prevent thread and process exhaustion on high-core systems
os.environ.setdefault("PYTEST_XDIST_AUTO_NUM_WORKERS", str(min(os.cpu_count() or 4, 8)))

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


import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_xdist_auto_num_workers(config):
    """Dynamically determine the number of xdist workers."""
    markexpr = getattr(config.option, "markexpr", "")
    if is_slow_marker_selected(markexpr):
        # Force 0 workers (sequential execution) for slow tests to prevent GPU/UDS deadlocks
        return 0
    # Cap auto workers to prevent thread and cgroup pid exhaustion on large cloud instances (e.g. 128-core hosts)
    cpu_count = os.cpu_count() or 4
    return min(cpu_count, 8)


@pytest.fixture(autouse=True)
def isolate_test_feedback(tmp_path_factory, monkeypatch) -> None:
    """Ensure all tests run with an isolated feedback directory, preventing workspace pollution."""
    if "FEEDBACK_DIR" not in os.environ:
        test_fb = tmp_path_factory.mktemp("test_feedback")
        (test_fb / "attachments").mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("FEEDBACK_DIR", str(test_fb))


@pytest.fixture
def test_feedback_dir(tmp_path: Path, monkeypatch) -> Path:
    """Provide a dedicated test feedback directory for tests that explicitly test feedback."""
    fb = tmp_path / "feedback"
    fb.mkdir(parents=True, exist_ok=True)
    (fb / "attachments").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FEEDBACK_DIR", str(fb))
    return fb
