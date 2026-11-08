"""Configuration and automated routing action for carrier_board."""

import math
from pathlib import Path
from typing import Any, Optional
from model.wiring import Wiring
from provider.pcb.router import PCBAutoRouter


def config_route(provider: Any, target: str, subassembly: Optional[str]) -> None:
    """Execute automated PCB routing across all carrier board nets, persist to YAML and .env, and report metrics."""
    wiring = provider.wiring
    if wiring is None:
        raise FileNotFoundError(f"Wiring specification not found for {provider.name}")

    cfg = provider.get_pcb_config_without_routes()
    if cfg is None:
        raise ValueError("PCB configuration not found for carrier_board")

    project_dir = provider.wiring_path.parent
    routing_file = project_dir / "routing.yaml"
    auto_traces, auto_vias = [], []

    if subassembly == "carrier_board" or not routing_file.exists():
        router = PCBAutoRouter(cfg, wiring)
        auto_traces, auto_vias = router.route_all_nets()
        # 1. Save carrier board routing to per-project YAML file
        router.save_routing_yaml(routing_file, auto_traces, auto_vias)
    elif routing_file.exists():
        auto_traces, auto_vias = PCBAutoRouter.load_routing_yaml(routing_file)

    # 2. Persist path to root application .env so routes can be manually inspected or overridden
    if routing_file.is_relative_to(Path.cwd()):
        rel_path = routing_file.relative_to(Path.cwd())
    else:
        rel_path = routing_file

    env_entry = f"APP_CARRIER_BOARD__ROUTING_PATH={rel_path}\n"
    root_env = Path(".env")
    if root_env.exists():
        existing_lines = [
            line
            for line in root_env.read_text().splitlines(keepends=True)
            if not line.startswith("APP_CARRIER_BOARD__ROUTING_PATH=")
        ]
        existing_lines.append(env_entry)
        root_env.write_text("".join(existing_lines))

    # Calculate total routing length
    total_len_mm = sum(math.hypot(tr.end_mm[0] - tr.start_mm[0], tr.end_mm[1] - tr.start_mm[1]) for tr in auto_traces)

    if hasattr(provider, "logger") and provider.logger:
        provider.logger.print(
            f"Auto-routed carrier: {len(auto_traces)} trace segments ({total_len_mm:.2f} mm total) and {len(auto_vias)} vias.",
            symbol="⚡ ",
        )
        provider.logger.print(f"Persisted routing to {routing_file} and .env", symbol="💾 ")
    else:
        print(
            f"[carrier_board:route] Carrier routed {len(auto_traces)} traces ({total_len_mm:.2f} mm) and {len(auto_vias)} vias."
        )
        print(f"[carrier_board:route] Saved to {routing_file} and .env")


if __name__ == "__main__":
    from projects.carrier_board.provider import CarrierBoardProvider

    provider_instance = CarrierBoardProvider()
    config_route(provider_instance, "carrier_board:route", "carrier_board")
