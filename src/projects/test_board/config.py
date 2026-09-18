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
    cfg = provider.pcb_manifest or provider.pcb_config
    if cfg is None:
        raise ValueError("PCB configuration not found for test_board")

    router = PCBAutoRouter(cfg, wiring)
    auto_traces, auto_vias = router.route_all_nets()

    # 1. Save routing to per-project YAML file
    project_dir = provider.wiring_path.parent
    routing_file = project_dir / "routing.yaml"
    router.save_routing_yaml(routing_file, auto_traces, auto_vias)

    # 2. Persist path to per-project .env and root .env so routes can be manually inspected or overridden
    try:
        rel_path = routing_file.relative_to(Path.cwd())
    except ValueError:
        rel_path = routing_file

    env_entry = f"APP_TEST_BOARD__ROUTING_PATH={rel_path}\n"
    project_env = project_dir / ".env"
    project_env.write_text(f"# Test board persisted routing\n{env_entry}")

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

    if hasattr(provider, "logger") and provider.logger:
        provider.logger.print(
            f"Auto-routed {len(auto_traces)} trace segments ({total_len_mm:.2f} mm total) and {len(auto_vias)} vias across nets.",
            symbol="⚡ ",
        )
        provider.logger.print(f"Persisted routing to {routing_file} and .env", symbol="💾 ")
    else:
        print(f"[test_board:route] Routed {len(auto_traces)} traces ({total_len_mm:.2f} mm) and {len(auto_vias)} vias.")
        print(f"[test_board:route] Saved to {routing_file} and .env")
