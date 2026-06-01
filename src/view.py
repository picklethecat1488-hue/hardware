"""View manifold geometry using ocp_vscode."""

import argparse
from build123d import *  # type: ignore
from build import Builder
from config import Configurator
from model import AppConfig
from provider import ProviderManager
from shell import Logger
from ocp_vscode import show, set_port, Collapse, Camera  # type: ignore


class Viewer:
    """Builds and displays geometry rooms for visualization."""

    def __init__(self, builder: Builder, configurator: Configurator, logger: Logger):
        """Initialize the viewer."""
        self.builder = builder
        self.configurator = configurator
        self.logger = logger
        self.names = builder.config.tube.names

    def get_summary(self, names: list[str]) -> str:
        """Return a truncated summary string of the names being shown."""
        if len(names) > 8:
            return f"{', '.join(names[:8])} ... ({len(names)} items)"
        return ", ".join(names)

    def build_part_position_point(self, name, offset, right=False):
        """Build a part position point marker at the given offset."""
        tube = self.builder.build_part(name, right=right, tube_only=True)
        path = self.builder.create_wire(name)
        center = self.configurator.get_part_position(tube, path, offset)
        return Pos(center) * Sphere(radius=10)

    def build_solid_center_point(self, name, right=False):
        """Build a solid center point marker for the part."""
        tube = self.builder.build_part(name, right=right, tube_only=True)
        center = tube.center()
        return Pos(center) * Cone(
            bottom_radius=10, top_radius=0, height=10, align=(Align.CENTER, Align.CENTER, Align.MIN)
        )

    def show_wires_room(self):
        """Build geometry for the wires room."""
        return {f"{name}_wire": (self.builder.create_wire(name), "magenta", 1.0) for name in self.names}

    def show_profiles_room(self):
        """Build geometry for the profiles room."""
        return {
            "quadrant_90deg_315center": (self.builder.create_profile(315, 90, joint_space=0.3), "magenta", 1.0),
            "quadrant_90deg_45center": (self.builder.create_profile(45, 90, joint_space=0.3), "magenta", 1.0),
            "sector_30deg_180center": (self.builder.create_profile(180, 30, joint_space=0.3), "magenta", 1.0),
            "sector_30deg_210center": (self.builder.create_profile(210, 30, joint_space=0.3), "magenta", 1.0),
            "lap_joint_sketch": (self.builder.create_profile_sketch(180, lap_joint=True), "magenta", 1.0),
            "full_sketch": (self.builder.create_profile_sketch(360), "magenta", 1.0),
        }

    def show_positions_room(self):
        """Build geometry for the positions room."""
        to_show = {}
        for name in self.names:
            for right in [False, True]:
                side = "right" if right else "left"
                color = ("red" if right else "green") if name == "driver" else ("blue" if right else "orange")
                to_show[f"{name}_{side}"] = (self.builder.build_part(name, right=right), color, 0.5)

                for i in range(10):
                    to_show[f"{name}_{side}_pos_{i}"] = (
                        self.build_part_position_point(name, i / 10, right=right),
                        color,
                        1.0,
                    )
                to_show[f"{name}_{side}_center"] = (self.build_solid_center_point(name, right=right), "blue", 1.0)
        return to_show

    def show_parts_room(self):
        """Build geometry for the parts room."""
        to_show = {}
        for name in self.names:
            for right in [False, True]:
                side = "right" if right else "left"
                color = ("red" if right else "green") if name == "driver" else ("blue" if right else "orange")
                to_show[f"{name}_{side}"] = (self.builder.build_part(name, right=right), color, 1.0)
        return to_show

    def show_overlay_room(self):
        """Build geometry for the overlay room."""
        to_show = {}
        for name in self.names:
            color = "cyan" if name == "driver" else "yellow"
            to_show[f"{name}_full_tube"] = (self.builder.build_tube(name), color, 0.2)
            for right in [False, True]:
                side = "right" if right else "left"
                color = ("red" if right else "green") if name == "driver" else ("blue" if right else "orange")
                to_show[f"{name}_{side}"] = (self.builder.build_part(name, right=right), color, 1.0)
        return to_show

    def show_view(self, scene: str, name: str | None = None, show_bounds: bool = False):
        """Build and show the requested geometry in ocp_vscode."""
        self.names = [name] if name else self.builder.config.tube.names

        to_show = {}
        if show_bounds:
            to_show["bounds"] = (self.builder.config.bound_box, "grey", 0.2)

        rooms = {
            "wires": self.show_wires_room,
            "profiles": self.show_profiles_room,
            "positions": self.show_positions_room,
            "parts": self.show_parts_room,
            "overlay": self.show_overlay_room,
        }

        if scene in rooms:
            to_show.update(rooms[scene]())

        if to_show:
            names = list(to_show.keys())
            summary = self.get_summary(names)
            self.logger.print(f"Showing {summary}", symbol="👁️ ")

            values = [v[0] for v in to_show.values()]
            colors = [v[1] for v in to_show.values()]
            alphas = [v[2] for v in to_show.values()]

            show(
                *values,
                names=names,
                colors=colors,
                alphas=alphas,
                collapse=Collapse.LEAVES,
                reset_camera=Camera.RESET,
            )
        else:
            raise ValueError("No scenes to show") from None


def get_args():
    """Get parsed arguments for the viewer."""
    parser = argparse.ArgumentParser(description="View Utility.")
    parser.add_argument(
        "scene",
        choices=["parts", "wires", "profiles", "positions", "overlay"],
        help="The specific scene/room to visualize.",
    )
    parser.add_argument(
        "-n",
        "--name",
        choices=["driver", "passenger"],
        default=None,
        help="Filter by part name.",
    )
    parser.add_argument("-b", "--bounds", action="store_true", help="Show bounding box")

    args = parser.parse_args()

    if args.scene == "profiles":
        if args.name is not None:
            parser.error("Argument -n/--name is not allowed with the 'profiles' scene.")
        if args.bounds:
            parser.error("Argument -b/--bounds is not allowed with the 'profiles' scene.")

    return args


def main():
    """Build and show the requested geometry in ocp_vscode."""
    args = get_args()
    logger = Logger(text="Visualizing...")
    config = AppConfig()
    manager = ProviderManager(config)
    builder = Builder(config, logger)
    configurator = Configurator(builder, config, logger)
    viewer = Viewer(builder, configurator, logger)
    viewer.show_view(args.scene, name=args.name, show_bounds=args.bounds)
    logger.done()


if __name__ == "__main__":
    main()
