"""Configuration tuning actions for the cat fountain."""

from pathlib import Path
from typing import Any, Optional
from provider import Room, Simulate, Mode


def config_tune(provider: Any, target: str, subassembly: Optional[str]) -> None:
    """Configure and tune SPH parameters algorithmically by running simulation sweeps."""
    import pybullet as p
    import numpy as np
    import tempfile
    import shutil

    # Ensure that the URDF and meshes are built and up-to-date
    from provider import ProviderManager
    from build import Builder

    manager = ProviderManager(provider.app_config, logger=provider.logger)
    builder = Builder(manager, provider.logger)
    builder._load_manifest("build")
    builder.generate_parts(
        out_dir="build",
        names=[
            "cat_fountain/bowl",
            "cat_fountain/impeller",
            "cat_fountain/bottom_cover",
            "cat_fountain/lid",
            "cat_fountain/led_cover",
            "cat_fountain/drive_hub",
            "cat_fountain/pump_cover",
            "cat_fountain/motor_clip",
        ],
    )
    builder.generate_urdfs(out_dir="build", names=["cat_fountain/product"])
    builder._save_manifest("build")

    # Build the product room to parse boundaries
    room = Room()
    provider.build_product(room, mode=Mode.SIMULATE)
    room.translate_joints()

    # Find the URDF path
    build_dir = Path("build")
    urdf_path = build_dir / "urdf/cat_fountain/product.urdf"
    if not urdf_path.exists():
        provider.logger.print("Warning: URDF file not found in build directory.", symbol="⚠️")
        return

    boundaries = {}
    for _, (geom, _) in room.items():
        u_geom = geom
        label = getattr(u_geom, "urdf_label", None)
        if label:
            geom_boundaries = getattr(u_geom, "urdf_boundaries", None)
            if geom_boundaries:
                boundaries[label] = geom_boundaries

    # Create temporary directory and copy project assets for PyBullet path resolution
    temp_dir = tempfile.mkdtemp()
    try:
        proj_name = "cat_fountain"
        proj_dir = Path(temp_dir) / proj_name
        proj_dir.mkdir(parents=True, exist_ok=True)

        build_proj_dir = Path("build/obj") / proj_name
        if not build_proj_dir.exists():
            build_proj_dir = Path("build") / proj_name

        if build_proj_dir.exists():
            for item in build_proj_dir.glob("*"):
                if item.is_file():
                    shutil.copy(item, proj_dir / item.name)

        urdf_temp_path = Path(temp_dir) / "product.urdf"
        shutil.copy(urdf_path, urdf_temp_path)

        # SPH ranges to optimize over
        stiffness_range = (500.0, 1500.0)
        damping_range = (0.5, 3.0)

        # Set random seed for deterministic reproducibility
        np.random.seed(42)
        best_stiffness = None
        best_damping = None
        best_stable = False
        best_flow_score = -1
        best_max_speed = 999.0

        def evaluate_candidate(k_b, d_b) -> tuple[float, int]:
            # Connect to PyBullet DIRECT
            physics_client = p.connect(p.DIRECT)
            try:
                p.setGravity(0, 0, -9.81, physicsClientId=physics_client)
                body_id = p.loadURDF(str(urdf_temp_path), useFixedBase=True, physicsClientId=physics_client)
                if body_id < 0:
                    return 99.0, 0

                # Set candidate in-memory
                provider.settings.stiffness_boundary = k_b
                provider.settings.damping_boundary = d_b

                hooks = provider.get_simulate_hooks_impl("product:view/simulate")
                setup_fn = hooks[Simulate.SETUP]
                step_fn = hooks[Simulate.STEP]

                setup_fn(body_id, physics_client, "product:view/simulate", boundaries, None)

                max_speed_observed = 0.0
                total_flow_accum = 0
                num_steps = 150

                for step_idx in range(num_steps):
                    step_fn(body_id, physics_client, step_idx, "product:view/simulate")
                    p.stepSimulation(physicsClientId=physics_client)

                    # Monitor instability and flow
                    if provider.water_sim is not None:
                        vel_np = np.array(provider.water_sim.vel_jax)
                        if len(vel_np) > 0:
                            max_speed = float(np.max(np.linalg.norm(vel_np, axis=1)))
                            max_speed_observed = max(max_speed_observed, max_speed)
                            if max_speed > 50.0:  # Prevent JAX overflow/NaN
                                break

                        # Count particles in the tube
                        pos_np = np.array(provider.water_sim.pos_jax)
                        tube_center_x = 0.0
                        tube_center_y = 0.028
                        dist_sq = (pos_np[:, 0] - tube_center_x) ** 2 + (pos_np[:, 1] - tube_center_y) ** 2
                        in_tube = (dist_sq < 0.008**2) & (pos_np[:, 2] >= 0.041)
                        total_flow_accum += int(np.sum(in_tube))

                return max_speed_observed, total_flow_accum

            finally:
                p.disconnect(physics_client)

        def is_better_candidate(stable: bool, max_speed: float, flow: int) -> bool:
            if best_stiffness is None:
                return True
            # Preference 1: Stable is strictly better than unstable
            if stable and not best_stable:
                return True
            if not stable and best_stable:
                return False
            # Preference 2: Compare within same stability status
            if stable:
                # If flow is significantly higher (>2.5%), prefer it
                flow_diff_ratio = (flow - best_flow_score) / max(1, best_flow_score)
                if flow_diff_ratio > 0.025:
                    return True
                elif flow_diff_ratio >= -0.025:
                    # Flow is within 2.5%, select the one with better stability (lower max speed)
                    return max_speed < best_max_speed
                return False
            else:
                # If both are unstable, select the one with lower max speed
                return max_speed < best_max_speed

        # 1. Phase 1: Seed Discovery via Monte Carlo Random Sampling
        num_seeds = 5
        provider.logger.print(
            f"SPH Optimization Phase 1: running {num_seeds} Monte Carlo random seed trials...",
            symbol="🎲",
        )

        for seed_idx in range(num_seeds):
            # Sample uniformly in range
            k_b = float(np.random.uniform(stiffness_range[0], stiffness_range[1]))
            d_b = float(np.random.uniform(damping_range[0], damping_range[1]))

            max_speed, flow = evaluate_candidate(k_b, d_b)
            stable = max_speed <= 10.0
            status_str = "STABLE" if stable else "UNSTABLE"

            provider.logger.print(
                f"  Seed {seed_idx + 1} stiffness={k_b:.1f}, damping={d_b:.2f} | Status={status_str} | Max Speed={max_speed:.2f} m/s | Flow={flow}",
                symbol="📊",
            )

            if is_better_candidate(stable, max_speed, flow):
                best_stable = stable
                best_flow_score = flow
                best_max_speed = max_speed
                best_stiffness = k_b
                best_damping = d_b

        # Fallback if no stable seeds found
        if best_stiffness is None or best_damping is None or not best_stable:
            provider.logger.print(
                "Warning: No stable seeds found during Phase 1. Seeding with default parameters.", symbol="⚠️"
            )
            best_stiffness = 1000.0
            best_damping = 1.5
            max_speed, flow = evaluate_candidate(best_stiffness, best_damping)
            best_stable = max_speed <= 10.0
            best_flow_score = flow
            best_max_speed = max_speed

        # 2. Phase 2: Local Search / Annealing (Gaussian random walk around the best seed)
        num_local_iters = 12
        scale_stiffness = 200.0
        scale_damping = 0.5

        provider.logger.print(
            f"SPH Optimization Phase 2: starting localized Monte Carlo hill climbing from seed stiffness={best_stiffness:.1f}, damping={best_damping:.2f} (Flow={best_flow_score}, Max Speed={best_max_speed:.2f} m/s)...",
            symbol="🔍",
        )

        for iter_idx in range(num_local_iters):
            # Cooling factor reduces search radius over time
            cooling = 1.0 - (iter_idx / num_local_iters)

            # Sample candidate from Gaussian centered around best found
            k_b = float(np.random.normal(best_stiffness, scale_stiffness * cooling))
            d_b = float(np.random.normal(best_damping, scale_damping * cooling))

            # Clamp candidate to search boundaries
            k_b = max(stiffness_range[0], min(stiffness_range[1], k_b))
            d_b = max(damping_range[0], min(damping_range[1], d_b))

            max_speed, flow = evaluate_candidate(k_b, d_b)
            stable = max_speed <= 10.0
            status_str = "STABLE" if stable else "UNSTABLE"

            if is_better_candidate(stable, max_speed, flow):
                provider.logger.print(
                    f"  Iter {iter_idx + 1}/{num_local_iters}: Found improved local maximum! stiffness={k_b:.1f}, damping={d_b:.2f} | Status={status_str} | Max Speed={max_speed:.2f} m/s | Flow={flow}",
                    symbol="🚀",
                )
                best_stable = stable
                best_flow_score = flow
                best_max_speed = max_speed
                best_stiffness = k_b
                best_damping = d_b
            else:
                provider.logger.print(
                    f"  Iter {iter_idx + 1}/{num_local_iters}: stiffness={k_b:.1f}, damping={d_b:.2f} | Status={status_str} | Max Speed={max_speed:.2f} m/s | Flow={flow}",
                    symbol="📊",
                )

        if best_damping is not None and best_stiffness is not None and best_stable:
            provider.logger.print(
                f"Optimal SPH parameters determined: stiffness_boundary = {best_stiffness:.1f}, damping_boundary = {best_damping:.2f} (Status = STABLE, Flow = {best_flow_score}, Peak Speed = {best_max_speed:.2f} m/s)",
                symbol="🏆",
            )
            # Set the optimal values back to settings for environment persistence
            provider.settings.stiffness_boundary = best_stiffness
            provider.settings.damping_boundary = best_damping
        else:
            raise ValueError(
                f"SPH parameter optimization failed: no stable configuration found. "
                f"Best peak speed was {best_max_speed:.2f} m/s (limit is 10.0 m/s)."
            )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
