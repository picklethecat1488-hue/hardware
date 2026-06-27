"""Simulation hooks for the cat fountain project."""

import pybullet as p
from provider.bullet import _is_real_physics_client
from typing import Any, Callable, cast
from provider import Bullet, LinkType, Fluid, Simulate, URDFShape
from model import FluidConfig, BoundaryConfig


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
                if "tube" in link_name:
                    link_indices[LinkType.TUBE] = i
                    link_indices[LinkType.OUTLET] = i
                elif "impeller" in link_name:
                    link_indices[LinkType.IMPELLER] = i
                elif "lid" in link_name:
                    link_indices["lid"] = i

        # Resolve boundaries to include correct link_idx and link_type
        resolved_boundaries = {}
        for label, val in boundaries.items():
            vals = val if isinstance(val, list) else [val]
            resolved_vals = []
            for item in vals:
                item_dict = item.model_dump(exclude_defaults=True) if hasattr(item, "model_dump") else dict(item)
                match label:
                    case "bowl":
                        item_dict["link_type"] = LinkType.BASE
                        item_dict["link_idx"] = -1
                    case "tube":
                        item_dict["link_type"] = LinkType.TUBE
                        item_dict["link_idx"] = link_indices.get(LinkType.TUBE, -1)
                    case "impeller":
                        item_dict["link_type"] = LinkType.IMPELLER
                        item_dict["link_idx"] = link_indices.get(LinkType.IMPELLER, -1)
                    case "lid":
                        item_dict["link_type"] = LinkType.LID
                        item_dict["link_idx"] = link_indices.get("lid", -1)
                    case _:
                        item_dict["link_idx"] = link_indices.get(label, -1)
                        if "link_type" not in item_dict:
                            item_dict["link_type"] = LinkType.BASE
                resolved_vals.append(item_dict)
            resolved_boundaries[label] = resolved_vals

        self.water_sim = Fluid(
            config=FluidConfig.water(
                sim_name=name,
                boundaries=resolved_boundaries,
                recycle_fluid=False,
                gravity=(0.0, 0.0, -9.81),
                r_s=0.0015,
                target_volume=0.00020,
                slot_height=self.settings.slot_height * 0.001,
                fallen_threshold_liters=0.001,
                high_damping_value=0.998,
                damping_boundary=25.0,
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

        # Update physical joint speed in PyBullet
        if not hasattr(self, "_impeller_joint_idx"):
            self._impeller_joint_idx = -1
            if _is_real_physics_client(client):
                for i in range(p.getNumJoints(body_id, physicsClientId=client)):
                    info = p.getJointInfo(body_id, i, physicsClientId=client)
                    if "impeller" in info[12].decode("utf-8"):
                        self._impeller_joint_idx = i
                        break

        if self._impeller_joint_idx != -1 and _is_real_physics_client(client):
            p.setJointMotorControl2(
                bodyUniqueId=body_id,
                jointIndex=self._impeller_joint_idx,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=omega,
                force=max_force,
                physicsClientId=client,
            )

        self.water_sim.update(
            body_id,
            client,
            target_omega=omega,
            max_force=max_force,
        )
        if (
            len(self.water_sim.fallen_out_water_ids) * self.water_sim.vol_s * 1000.0
            >= self.water_sim.fallen_threshold_liters
        ):
            return f"{self.water_sim.fallen_threshold_liters}L of water fell out of bowl at step {step_idx}"
        return None

    return {
        Simulate.SETUP: setup_simulation,
        Simulate.STEP: step_simulation,
    }
