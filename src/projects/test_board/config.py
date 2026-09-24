"""Configuration and automated routing action for test_board."""

import math
from pathlib import Path
from typing import Any, Optional
from model.wiring import Wiring
from provider.pcb.router import PCBAutoRouter


def config_route(provider: Any, target: str, subassembly: Optional[str]) -> None:
    """Execute automated PCB routing across all test board nets, persist to YAML and .env, and report metrics."""
    if not provider.wiring_path.exists():
        raise FileNotFoundError(f"Wiring specification not found at {provider.wiring_path}")

    wiring = Wiring(str(provider.wiring_path))
    cfg = provider.get_pcb_config_without_routes()
    if cfg is None:
        raise ValueError("PCB configuration not found for test_board")

    project_dir = provider.wiring_path.parent
    routing_file = project_dir / "routing.yaml"
    auto_traces, auto_vias = [], []

    if subassembly in (None, "carrier_board"):
        router = PCBAutoRouter(cfg, wiring)
        auto_traces, auto_vias = router.route_all_nets()
        # 1. Save carrier board routing to per-project YAML file
        router.save_routing_yaml(routing_file, auto_traces, auto_vias)
    elif routing_file.exists():
        auto_traces, auto_vias = PCBAutoRouter.load_routing_yaml(routing_file)

    # 2. Route flexible sensing tail and save to routing_flex.yaml
    flex_part = provider.part.get("flex_tail")
    flex_traces = []
    flex_vias = []
    routing_flex_file = project_dir / "routing_flex.yaml"
    if flex_part and (subassembly == "flex_tail" or not routing_flex_file.exists()):
        from provider import Mode

        flex_res = flex_part("flex_tail", None, Mode.DEFAULT)
        flex_cfg = flex_res.to_pcb_config() if hasattr(flex_res, "to_pcb_config") else None
        if flex_cfg:
            flex_router = PCBAutoRouter(flex_cfg, wiring)
            flex_traces, flex_vias = flex_router.route_all_nets()
            flex_router.save_routing_yaml(routing_flex_file, flex_traces, flex_vias)
    elif routing_flex_file.exists():
        flex_traces, flex_vias = PCBAutoRouter.load_routing_yaml(routing_flex_file)

    # 3. Persist path to root application .env so routes can be manually inspected or overridden
    if routing_file.is_relative_to(Path.cwd()):
        rel_path = routing_file.relative_to(Path.cwd())
    else:
        rel_path = routing_file

    env_entry = f"APP_TEST_BOARD__ROUTING_PATH={rel_path}\n"
    root_env = Path(".env")
    if root_env.exists():
        existing_lines = [
            line
            for line in root_env.read_text().splitlines(keepends=True)
            if not line.startswith("APP_TEST_BOARD__ROUTING_PATH=")
        ]
        existing_lines.append(env_entry)
        root_env.write_text("".join(existing_lines))

    # Calculate total routing length
    total_len_mm = sum(math.hypot(tr.end_mm[0] - tr.start_mm[0], tr.end_mm[1] - tr.start_mm[1]) for tr in auto_traces)
    flex_len_mm = sum(math.hypot(tr.end_mm[0] - tr.start_mm[0], tr.end_mm[1] - tr.start_mm[1]) for tr in flex_traces)

    if hasattr(provider, "logger") and provider.logger:
        provider.logger.print(
            f"Auto-routed carrier: {len(auto_traces)} trace segments ({total_len_mm:.2f} mm total) and {len(auto_vias)} vias.",
            symbol="⚡ ",
        )
        if flex_traces:
            provider.logger.print(
                f"Auto-routed flex: {len(flex_traces)} trace segments ({flex_len_mm:.2f} mm total) and {len(flex_vias)} vias.",
                symbol="⚡ ",
            )
        provider.logger.print(f"Persisted routing to {routing_file} and .env", symbol="💾 ")
    else:
        print(
            f"[test_board:route] Carrier routed {len(auto_traces)} traces ({total_len_mm:.2f} mm) and {len(auto_vias)} vias."
        )
        if flex_traces:
            print(
                f"[test_board:route] Flex routed {len(flex_traces)} traces ({flex_len_mm:.2f} mm) and {len(flex_vias)} vias."
            )
        print(f"[test_board:route] Saved to {routing_file} and .env")


if __name__ == "__main__":
    from projects.test_board.provider import TestBoardProvider

    provider_instance = TestBoardProvider()
    config_route(provider_instance, "test_board:route", "carrier_board")
