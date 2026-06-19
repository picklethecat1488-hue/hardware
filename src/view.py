"""View manifold geometry using ocp_vscode."""

import argparse
import importlib
import fnmatch
import os
import sys
import shutil
import tempfile
import time
import pybullet as p
from model import AppConfig
from pathlib import Path
from typing import Sequence, Optional, List, Any, cast, Iterable
from build123d import *  # type: ignore
from target_parser import TargetParser
from provider import ProviderManager, Section, TargetList, Room, Simulate, Mode
from provider.types import URDFShape
from pydantic import validate_call
from shell import Logger
from ocp_vscode import set_port, Collapse, Camera, show as ocp_show  # type: ignore
from build import Builder
from list import Lister


def show(*args, **kwargs):
    """Bypass ocp_vscode visualization during smoke tests."""
    if os.environ.get("SMOKE_TEST") == "1":
        return
    return ocp_show(*args, **kwargs)


class Viewer:
    """Builds and displays geometry rooms for visualization."""

    VISUAL_ACTIONS = [Section.VIEW, Section.PART, Section.DIAGRAM]

    def __init__(self, manager: ProviderManager, logger: Logger):
        """Initialize the viewer."""
        self.manager = manager
        self.logger = logger
        self.target_parser = TargetParser(manager.router)

    def get_summary(self, names: Sequence[str]) -> str:
        """Return a truncated summary string of the names being shown."""
        if len(names) > 8:
            return f"{', '.join(names[:8])} ... ({len(names)} items)"
        return ", ".join(names)

    def _get_view_items(self, targets: TargetList) -> List[tuple[Any, str, tuple[float, float, float], float]]:
        """Collect items from a VIEW room."""
        items = []
        results = self.manager.router.run(targets)
        for room_name, room in results:
            for item_name, (geom, rgba) in room.items():
                items.append((geom, f"{room_name}_{item_name}", rgba[:3], rgba[3]))
        return items

    def _get_part_items(self, targets: Any) -> List[tuple[Any, str, tuple[float, float, float], float]]:
        """Collect geometry from a PART build."""
        items = []
        results = self.manager.router.run(targets)

        # Determine subassemblies used from the TargetList to correctly label items
        subs = targets.subassemblies if targets.subassemblies else [None]

        for name, geom in results:
            res_list = geom if isinstance(geom, list) else [geom]
            for i, item in enumerate(res_list):
                sub = subs[i] if i < len(subs) else None
                display_name = f"{name}_{sub}" if sub else name
                rgba = self.manager.router.get_color(name, sub)
                items.append((item, display_name, rgba[:3], rgba[3]))
        return items

    def _get_diagram_items(
        self, targets: TargetList
    ) -> List[tuple[Any, str, Optional[tuple[float, float, float]], float]]:
        """Collect a compound from a DIAGRAM build."""
        items = []
        results = self.manager.router.run(targets)
        for p_name, room in results:
            items.append((room.compound, f"{p_name}_diagram", None, 1.0))
        return items

    @validate_call(config={"arbitrary_types_allowed": True})
    def show_view(self, input_targets: Sequence[str], build_dir: str = "build", no_build: bool = False, sim_steps=1000):
        """Build and show the requested geometry in ocp_vscode."""
        display_items = []
        is_simulate = False
        provider = None
        sim_target = None

        for target in input_targets:
            for action in self.VISUAL_ACTIONS:
                try:
                    targets = self.target_parser.resolve(target, action)
                    if not targets:
                        continue
                    if Mode.SIMULATE in getattr(targets, "modes", []):
                        is_simulate = True
                        provider = targets.provider
                        sim_target = list(targets)[0] if targets else target.split(":")[0]
                    if action == Section.VIEW:
                        display_items.extend(self._get_view_items(targets))
                        break
                    elif action == Section.PART:
                        display_items.extend(self._get_part_items(targets))
                        break
                    elif action == Section.DIAGRAM:
                        display_items.extend(self._get_diagram_items(targets))
                        break
                except ValueError:
                    continue

        if not display_items:
            raise ValueError("No geometry generated for the specified targets.")

        room = Room(config=self.manager.config)
        for obj, name, color, alpha in display_items:
            # Assembly names cannot contain slashes as they are path delimiters
            base_name = name.replace("/", "_")
            safe_name = base_name
            counter = 1
            while safe_name in room:
                safe_name = f"{base_name}_{counter}"
                counter += 1
            room.add(safe_name, obj, color=color, alpha=alpha)

        if is_simulate and provider:
            proj_name = "default"
            for target in input_targets:
                if "/" in target:
                    proj_name = target.split("/", 1)[0]
                    break

            if not no_build:
                # Compile OBJs and URDFs prior to simulating to ensure they are up to date
                base_targets = [t.split(":")[0].split("/")[0] for t in input_targets]
                builder = Builder(self.manager, self.logger)
                builder.generate_parts(build_dir, names=base_targets)
                builder.generate_urdfs(build_dir, names=base_targets)

            self.show_simulation(
                room, provider, proj_name, sim_target=sim_target or "default", build_dir=build_dir, steps=sim_steps
            )
        else:
            summary = self.get_summary(list(room.keys()))
            self.logger.print(f"Showing {summary}", symbol="👁️ ")
            show(room.compound, names=["View"], collapse=Collapse.ALL, reset_camera=Camera.RESET)

    def show_simulation(
        self,
        room: Room,
        provider: Any,
        proj_name: str,
        sim_target: str,
        steps,
        build_dir: str = "build",
    ) -> None:
        """Run a PyBullet physics simulation for the room geometries."""
        self.logger.print("Running Simulation...", symbol="🤖")

        if not room:
            raise ValueError("Cannot simulate an empty Room.")

        temp_dir = tempfile.mkdtemp()
        try:
            proj_dir = os.path.join(temp_dir, proj_name)
            os.makedirs(proj_dir, exist_ok=True)

            build_proj_dir = os.path.join(build_dir, proj_name)

            # Map to determine names of room geometries
            room.translate_joints()

            for geom, _ in room.values():
                u_geom = cast(URDFShape, geom)
                label = getattr(u_geom, "urdf_label", None)
                if label:
                    real_obj_path = os.path.join(build_proj_dir, f"{label}.obj")
                    temp_obj_path = os.path.join(proj_dir, f"{label}.obj")
                    if os.path.exists(real_obj_path):
                        shutil.copy(real_obj_path, temp_obj_path)
                    else:
                        raise FileNotFoundError(f"Required OBJ file not found for simulation: {real_obj_path}")

            # Determine URDF filename using Lister
            lister = Lister(self.manager, self.logger)
            urdf_rel_path = lister.get_urdf_output(sim_target)
            real_urdf_path = os.path.join(build_dir, urdf_rel_path)
            temp_urdf_filename = os.path.basename(urdf_rel_path)
            urdf_path = os.path.join(temp_dir, temp_urdf_filename)

            if os.path.exists(real_urdf_path):
                shutil.copy(real_urdf_path, urdf_path)
            else:
                raise FileNotFoundError(f"Required URDF file not found for simulation: {real_urdf_path}")

            gui_mode = p.DIRECT if os.environ.get("SMOKE_TEST") == "1" else p.GUI
            physics_client = p.connect(gui_mode)
            try:
                p.setGravity(*room.gravity, physicsClientId=physics_client)

                body_id = p.loadURDF(urdf_path, physicsClientId=physics_client)
                if body_id < 0:
                    raise RuntimeError("PyBullet failed to load the URDF.")

                num_joints = p.getNumJoints(body_id, physicsClientId=physics_client)
                joint_name_to_index = {}
                for i in range(num_joints):
                    info = p.getJointInfo(body_id, i, physicsClientId=physics_client)
                    joint_name = info[1].decode("utf-8")
                    joint_name_to_index[joint_name] = i

                for geom, _ in room.values():
                    u_geom = cast(URDFShape, geom)
                    label = getattr(u_geom, "urdf_label", None)
                    parent_label = getattr(u_geom, "urdf_parent", None)
                    if label and parent_label:
                        joint_name = f"{parent_label}_to_{label}"
                        if joint_name in joint_name_to_index:
                            idx = joint_name_to_index[joint_name]
                            motor_type = getattr(u_geom, "urdf_motor_type", None)
                            if motor_type:
                                target = getattr(u_geom, "urdf_motor_target", 0.0)
                                force = getattr(u_geom, "urdf_motor_force", 10.0)
                                if motor_type == "velocity":
                                    p.setJointMotorControl2(
                                        bodyUniqueId=body_id,
                                        jointIndex=idx,
                                        controlMode=p.VELOCITY_CONTROL,
                                        targetVelocity=target,
                                        force=force,
                                        physicsClientId=physics_client,
                                    )
                                elif motor_type == "torque":
                                    p.setJointMotorControl2(
                                        bodyUniqueId=body_id,
                                        jointIndex=idx,
                                        controlMode=p.TORQUE_CONTROL,
                                        force=target,
                                        physicsClientId=physics_client,
                                    )
                            else:
                                p.setJointMotorControl2(
                                    bodyUniqueId=body_id,
                                    jointIndex=idx,
                                    controlMode=p.VELOCITY_CONTROL,
                                    force=0,
                                    physicsClientId=physics_client,
                                )

                # Setup Hooks
                setup_hook = provider.simulate.get(Simulate.SETUP, None)
                if setup_hook:
                    setup_hook(body_id, physics_client)

                loop_start = time.perf_counter()
                for step_idx in range(steps):
                    # Step Hooks
                    step_hook = provider.simulate.get(Simulate.STEP, None)
                    sleep_t = float("inf")
                    if step_hook:
                        res = step_hook(body_id, physics_client, step_idx)
                        sleep_t = min(sleep_t if isinstance(res, (int, float)) else 1, float(res))

                    p.stepSimulation(physicsClientId=physics_client)

                    if sleep_t == float("inf"):
                        # Simulation early termination conditions met.
                        break
                    elif sleep_t > 0:
                        # Lock simulation speed to the speed of the fastest provider, or 0
                        elapsed = time.perf_counter() - loop_start
                        remaining_t = sleep_t - elapsed
                        if gui_mode == p.GUI and remaining_t > 0:
                            time.sleep(remaining_t)
                    loop_start = time.perf_counter()

                # Teardown Hooks
                teardown_hook = provider.simulate.get(Simulate.TEARDOWN, None)
                if teardown_hook:
                    teardown_hook(body_id, physics_client)
            finally:
                p.disconnect(physicsClientId=physics_client)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def get_args():
    """Get parsed arguments for the viewer."""
    parser = argparse.ArgumentParser(description="View Utility.")
    parser.add_argument(
        "targets", nargs="*", help="The targets to visualize (e.g. tube/driver, tube/wire, tube/driver_left)."
    )
    parser.add_argument("-l", "--list", action="store_true", help="List available visual targets")
    parser.add_argument("--no-build", action="store_true", help="Skip compiling parts and URDFs prior to simulating")
    parser.add_argument(
        "--build-dir", default="build", help="Directory where compiled parts and URDFs are stored (default: 'build')"
    )
    parser.add_argument(
        "-s",
        "--sim-steps",
        default=10000,
        required=False,
        help="Maximum number of steps to take before stopping the simulation.",
    )
    args = parser.parse_args()

    if not args.list and not args.targets:
        parser.error("the following arguments are required: target (or use --list)")

    return args


def main():
    """Build and show the requested geometry in ocp_vscode."""
    args = get_args()

    # Allow overriding the OCP Viewer port for testing environments
    ocp_port = os.environ.get("OCP_PORT")
    if ocp_port:
        set_port(int(ocp_port))

    logger = Logger(text="Visualizing...")

    config = AppConfig()
    manager = ProviderManager(config, logger=logger)
    viewer = Viewer(manager, logger)
    try:
        if args.list:
            logger.text = "Listing targets..."
            Lister(manager, logger).list_targets(Viewer.VISUAL_ACTIONS)
        else:
            viewer.show_view(
                cast(Sequence[str], args.targets),
                build_dir=args.build_dir,
                no_build=args.no_build,
                sim_steps=args.sim_steps,
            )
    finally:
        logger.done()


if __name__ == "__main__":
    main()
