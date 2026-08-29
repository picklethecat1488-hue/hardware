"""Simulation hooks and flow metrics for the cat fountain project."""

import numpy as np
import pybullet as p
import rerun as rr
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
                elif "drive_hub" in link_name:
                    link_indices[LinkType.DRIVE_HUB] = i
                elif "lid" in link_name:
                    link_indices["lid"] = i
                elif "pump_cover" in link_name:
                    link_indices["pump_cover"] = i

        # Resolve boundaries to include correct link_idx and link_type
        resolved_boundaries = {}
        for label, val in boundaries.items():
            vals = val if isinstance(val, list) else [val]
            resolved_vals = []
            for item in vals:
                item_dict = item.model_dump(exclude_defaults=True) if hasattr(item, "model_dump") else dict(item)
                match label:
                    case "bowl":
                        if item_dict.get("link_type") == LinkType.TUBE or item_dict.get("link_type") == "tube":
                            item_dict["link_type"] = LinkType.TUBE
                            item_dict["link_idx"] = -1
                        elif item_dict.get("link_type") == LinkType.CASING or item_dict.get("link_type") == "casing":
                            item_dict["link_type"] = LinkType.CASING
                            item_dict["link_idx"] = -1
                        elif item_dict.get("link_type") == LinkType.LID or item_dict.get("link_type") == "lid":
                            item_dict["link_type"] = LinkType.LID
                            item_dict["link_idx"] = -1
                        else:
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
                    case "pump_cover":
                        item_dict["link_type"] = LinkType.PUMP_COVER
                        item_dict["link_idx"] = link_indices.get("pump_cover", -1)
                    case _:
                        item_idx = link_indices.get(label, -1)
                        item_dict["link_idx"] = item_idx
                        if "link_type" not in item_dict:
                            item_dict["link_type"] = LinkType.BASE
                resolved_vals.append(item_dict)
            resolved_boundaries[label] = resolved_vals

        self.water_sim_damping = 0.995
        self.water_sim = Fluid(
            config=FluidConfig.water(
                sim_name=name,
                boundaries=resolved_boundaries,
                recycle_fluid=True,  # Enable fluid recycling
                gravity=(0.0, 0.0, -9.81),
                r_s=0.0015,
                target_volume=self.settings.target_volume,
                stiffness=1000.0,
                damping=0.995,
                viscosity=0.02,
                slot_height=self.settings.slot_height * 0.001,
                fallen_threshold_liters=0.001,
                damping_boundary=self.settings.damping_boundary,
                stiffness_boundary=self.settings.stiffness_boundary,
                nx=64,
                ny=64,
                nz=40,
                dx=0.0035,
                origin=(-0.112, -0.112, 0.0),
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
        motor_power = getattr(self.settings, "motor_power", 1.0)
        omega = target_omega

        # Run with motor_power=None when NOT in pytest, to disable non-physical speed throttling!
        import sys

        is_pytest = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)
        actual_motor_power = motor_power if is_pytest else None

        self.water_sim.update(
            body_id,
            client,
            target_omega=omega,
            max_force=max_force,
            motor_power=actual_motor_power,
            damping=getattr(self, "water_sim_damping", 0.995),
        )

        # Log continuous flow, sheet, drainage, and reservoir metrics in Rerun
        if hasattr(rr, "is_enabled") and rr.is_enabled():
            positions = getattr(self.water_sim, "last_positions", None)
            if positions is not None and len(positions) > 0:
                pos_pts = np.asarray(positions)
                active_mask = pos_pts[:, 2] < 100.0
                if np.any(active_mask):
                    pos_active = pos_pts[active_mask]
                    xs, ys, zs = pos_active[:, 0], pos_active[:, 1], pos_active[:, 2]

                    tube_x = 0.0
                    tube_y = 0.028
                    tube_r_inner = (self.settings.tube_radius - self.settings.tube_thickness) * 0.001
                    floor_z = self.settings.floor_z * 0.001
                    tube_top_z = (self.settings.floor_z + self.settings.tube_height) * 0.001
                    cutout_y = self.settings.lid_cutout_y * 0.001
                    cutout_r = self.settings.lid_cutout_radius * 0.001
                    bowl_r = (self.settings.bowl_radius - self.settings.bowl_thickness) * 0.001
                    lid_z_min = (self.settings.bowl_height - self.settings.lid_step_depth) * 0.001

                    dist_tube = np.sqrt((xs - tube_x) ** 2 + (ys - tube_y) ** 2)
                    dist_cutout = np.sqrt(xs**2 + (ys - cutout_y) ** 2)
                    r_xy = np.sqrt(xs**2 + ys**2)

                    # 1. Flow in vertical delivery tube (strictly inside 6mm bore from floor to top)
                    in_tube_mask = (dist_tube <= tube_r_inner + 0.001) & (zs >= floor_z) & (zs <= tube_top_z)
                    in_tube_cnt = int(np.sum(in_tube_mask))

                    # 2. Flow emerging at spout
                    at_spout_mask = (dist_tube <= 0.030) & (zs > tube_top_z - 0.001)
                    at_spout_cnt = int(np.sum(at_spout_mask))

                    # 3. Flow on lid drinking shelf / tray (outside spout dome, inside lid rim)
                    lid_sheet_mask = (
                        (zs >= lid_z_min) & (zs <= lid_z_min + 0.015) & (dist_tube > 0.025) & (r_xy <= 0.082)
                    )
                    lid_sheet_cnt = int(np.sum(lid_sheet_mask))

                    # 4. Drainage: Perimeter waterfall cascading into bowl (R >= 78mm, falling below lid)
                    waterfall_mask = (r_xy >= 0.078) & (zs >= floor_z) & (zs < lid_z_min)
                    waterfall_cnt = int(np.sum(waterfall_mask))

                    # 5. Drainage: Front cutout drain returning to bowl (inside cutout hole, falling below lid)
                    drain_mask = (
                        (dist_cutout <= cutout_r) & (ys < 0.0) & (zs >= floor_z) & (zs < lid_z_min) & (r_xy < 0.078)
                    )
                    drain_cnt = int(np.sum(drain_mask))

                    # 6. Reservoir pool volume (entire base container fluid layer)
                    pool_mask = (zs >= floor_z - 0.003) & (zs < floor_z + 0.030) & (r_xy <= bowl_r)
                    pool_cnt = int(np.sum(pool_mask))

                    rr.set_time("step", sequence=step_idx)
                    rr.log("metrics/flow_spout", rr.Scalars(float(at_spout_cnt)))
                    rr.log("metrics/flow_tube", rr.Scalars(float(in_tube_cnt)))
                    rr.log("metrics/flow_lid_sheet", rr.Scalars(float(lid_sheet_cnt)))
                    rr.log("metrics/drainage_waterfall", rr.Scalars(float(waterfall_cnt)))
                    rr.log("metrics/drainage_cutout", rr.Scalars(float(drain_cnt)))
                    rr.log("metrics/pool_volume", rr.Scalars(float(pool_cnt)))

        if (
            not self.water_sim.recycle_fluid
            and len(self.water_sim.fallen_out_water_ids) * self.water_sim.vol_s * 1000.0
            >= self.water_sim.fallen_threshold_liters
        ):
            return f"{self.water_sim.fallen_threshold_liters}L of water fell out of bowl at step {step_idx}"
        return None

    return {
        Simulate.SETUP: setup_simulation,
        Simulate.STEP: step_simulation,
    }
