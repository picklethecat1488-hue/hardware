"""Flying probes physics simulation and electrical validation hooks for carrier_board.

Replicates a physical high-precision multi-axis flying probe tester in PyBullet.
Loads declarative assembly test steps from provider models, populates obstacles declared in PCB schema,
and delegates simulation execution to provider.simulation.flying_probe.
"""

from typing import Any, Callable, Dict

from provider import Simulate
from provider.simulation.flying_probe import (
    create_flying_probe_hooks,
)


def get_simulate_hooks_impl(self: Any, sim_name: str) -> Dict[Simulate, Callable[..., Any]]:
    """Return flying probe simulation and electrical verification hooks for carrier_board.

    Args:
        self: CarrierBoardProvider instance.
        sim_name: Target name passed to simulator (e.g. carrier_board or flex_tail).

    Returns:
        Dictionary mapping Simulate.SETUP and Simulate.STEP to execution callbacks.
    """
    return create_flying_probe_hooks(self, sim_name)
