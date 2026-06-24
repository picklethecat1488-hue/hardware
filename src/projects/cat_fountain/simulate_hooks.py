"""Simulation hooks for the cat fountain project."""

import pybullet as p
from provider.bullet import _is_real_physics_client
from typing import Any, Callable, cast
from provider import Bullet, LinkType, Fluid, Simulate, URDFShape
from model import FluidConfig, FluidMotorConfig


def get_simulate_hooks_impl(self: Any, sim_name: str) -> dict[Simulate, Callable[..., Any]]:
    """Return simulation hooks for the cat fountain."""
    self.water_sim = None

    def setup_simulation(body_id, client, name, boundaries, state_tracker=None):
        link_indices = {}
        if _is_real_physics_client(client):
            p.setGravity(0.0, 0.0, -9.81, physicsClientId=client)
            for i in range(p.getNumJoints(body_id, physicsClientId=client)):
                info = p.getJointInfo(body_id, i, physicsClientId=client)
                link_name = info[12].decode("utf-8")
                if "spout" in link_name:
                    link_indices[LinkType.OUTLET] = i
                elif "tube" in link_name:
                    link_indices[LinkType.TUBE] = i
                elif "impeller" in link_name:
                    link_indices[LinkType.IMPELLER] = i

        self.water_sim = Fluid(
            config=FluidConfig.water(
                sim_name=name,
                boundaries=boundaries,
                recycle_fluid=True,
                gravity=(0.0, 0.0, -9.81),
                r_s=0.0015,
                particle_radius=0.0015,
            ),
            provider=self,
            body_id=body_id,
            physics_client=client,
            state_tracker=state_tracker,
            link_indices=link_indices,
        )

        bullet_sim = Bullet(self.room, {}, "", "", 0, None, None)
        bullet_sim.reset_camera(client, view_from="top rear")

    def step_simulation(body_id, client, step_idx, name):
        assert self.water_sim is not None
        target_omega = 15.0
        max_force = 10.0
        vane_obj = cast(URDFShape, self.room["impeller"][0])
        target_omega = float(getattr(vane_obj, "urdf_motor_target", 15.0))
        max_force = float(getattr(vane_obj, "urdf_motor_force", 10.0))
        omega = target_omega if step_idx >= 40 else 0.0
        self.water_sim.update(
            body_id,
            client,
            motor_config=FluidMotorConfig(target_omega=omega, max_force=max_force),
        )
        if (
            len(self.water_sim.fallen_out_water_ids) * self.water_sim.vol_s * 1000.0
            >= self.water_sim.fallen_threshold_liters
        ):
            return f"{self.water_sim.fallen_threshold_liters}L of water fell out of bowl"
        return None

    return {
        Simulate.SETUP: setup_simulation,
        Simulate.STEP: step_simulation,
    }
