"""Regression test for BUG-LUBRICATED-BRISTLE-678: Pytest parallelization and worker determination.

Verifies that:
1. Marker expressions deselecting slow tests (such as 'not slow') do not disable xdist workers.
2. Marker expressions selecting slow tests (such as 'slow') correctly force 0 workers (sequential execution).
3. The is_slow_marker_selected helper correctly parses marker expressions with negations and combinations.
"""

from unittest.mock import MagicMock

from conftest import is_slow_marker_selected, pytest_cmdline_main, pytest_xdist_auto_num_workers


def test_is_slow_marker_selected_negation() -> None:
    """Verify that 'not slow' and related expressions do not select slow tests."""
    assert not is_slow_marker_selected("not slow")
    assert not is_slow_marker_selected("(not slow)")
    assert not is_slow_marker_selected("not slow and not geometry")
    assert not is_slow_marker_selected("")
    assert not is_slow_marker_selected(None)


def test_is_slow_marker_selected_positive() -> None:
    """Verify that positive slow marker expressions select slow tests."""
    assert is_slow_marker_selected("slow")
    assert is_slow_marker_selected("slow and pcb")
    assert is_slow_marker_selected("slow or cad")


def test_xdist_workers_not_disabled_for_fast_tests() -> None:
    """Verify that fast test runs (e.g. markexpr='not slow') preserve xdist workers."""
    config = MagicMock()
    config.option.markexpr = "not slow"
    config.option.numprocesses = "auto"

    workers = pytest_xdist_auto_num_workers(config)
    assert workers is None, f"Expected None (letting xdist decide automatically), got {workers}"

    pytest_cmdline_main(config)
    assert config.option.numprocesses == "auto", "Fast test runs must not zero out numprocesses"


def test_xdist_workers_disabled_for_slow_tests() -> None:
    """Verify that slow test runs (e.g. markexpr='slow') force 0 workers for sequential execution."""
    config = MagicMock()
    config.option.markexpr = "slow"
    config.option.numprocesses = "auto"

    workers = pytest_xdist_auto_num_workers(config)
    assert workers == 0, f"Expected 0 workers for slow tests, got {workers}"

    pytest_cmdline_main(config)
    assert config.option.numprocesses == 0, "Slow test runs must set numprocesses to 0"
