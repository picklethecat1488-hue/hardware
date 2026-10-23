"""Flying probes physics simulation and electrical validation hooks for carrier_board.

Replicates a physical high-precision multi-axis flying probe tester in PyBullet.
Loads test steps from pcb_test_steps.yaml, populates obstacles declared in PCB schema,
and delegates simulation execution to provider.simulation.flying_probe.
"""

from pathlib import Path
from typing import Any, Callable, Dict

from provider import Simulate
from provider.simulation.flying_probe import (
    TestStepSpec,
    create_flying_probe_hooks,
    load_test_steps_from_yaml,
    render_markdown_test_report,
)


def get_simulate_hooks_impl(self: Any, sim_name: str) -> Dict[Simulate, Callable[..., Any]]:
    """Return flying probe simulation and electrical verification hooks for carrier_board.

    Args:
        self: CarrierBoardProvider instance.
        sim_name: Target name passed to simulator (e.g. carrier_board or flex_tail).

    Returns:
        Dictionary mapping Simulate.SETUP and Simulate.STEP to execution callbacks.
    """
    steps_path = Path(__file__).parent / "pcb_test_steps.yaml"
    return create_flying_probe_hooks(self, sim_name, test_steps_path=steps_path)
