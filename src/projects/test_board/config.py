"""Configuration and automated routing action for test_board."""

from typing import Any, Optional
from model.wiring import Wiring
from provider.pcb.router import PCBAutoRouter


def config_route(provider: Any, target: str, subassembly: Optional[str]) -> None:
    """Execute automated PCB routing across all test board nets and report metrics."""
    if not provider.wiring_path.exists():
        raise FileNotFoundError(f"Wiring specification not found at {provider.wiring_path}")

    wiring = Wiring(str(provider.wiring_path))
    cfg = provider.pcb_manifest or provider.pcb_config
    if cfg is None:
        raise ValueError("PCB configuration not found for test_board")

    manual_nets = {"CAP_TX0", "CAP_RX0", "CAP_TX1", "CAP_RX1", "CAP_TX2", "CAP_RX2", "CAP_RX3", "CAP_SHIELD"}
    router = PCBAutoRouter(cfg, wiring)
    auto_traces, auto_vias = router.route_all_nets(exclude_nets=manual_nets)

    # Calculate total routing length
    total_len_mm = sum(
        ((tr.end_mm[0] - tr.start_mm[0]) ** 2 + (tr.end_mm[1] - tr.start_mm[1]) ** 2) ** 0.5 for tr in auto_traces
    )

    if hasattr(provider, "logger") and provider.logger:
        provider.logger.print(
            f"Auto-routed {len(auto_traces)} trace segments ({total_len_mm:.2f} mm total) and {len(auto_vias)} vias across nets.",
            symbol="⚡ ",
        )
    else:
        print(f"[test_board:route] Routed {len(auto_traces)} traces ({total_len_mm:.2f} mm) and {len(auto_vias)} vias.")
