"""Viewer for manifold tube geometry."""

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, Literal, cast
from build123d import *  # type: ignore
from model.app_config import AppConfig
from projects_config import TubeConfig
from .builder import TubeBuilder
from .configurator import TubeConfigurator


class TubeViewer:
    """Viewer for tube geometry."""

    def __init__(
        self,
        builder: TubeBuilder,
        configurator: TubeConfigurator,
        config: AppConfig,
        tube_config: TubeConfig,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """Initialize the viewer with a builder and config."""
        self.builder = builder
        self.configurator = configurator
        self.config = config
        self.tube_config = tube_config
        self.executor = executor or ThreadPoolExecutor()
        self.names = self.tube_config.names

    def _get_rgba(self, color_name: str, alpha: float) -> tuple[float, float, float, float]:
        """Convert a color name to an RGBA tuple."""
        color_map = {
            "red": (1.0, 0.0, 0.0),
            "green": (0.0, 1.0, 0.0),
            "blue": (0.0, 0.0, 1.0),
            "orange": (1.0, 0.65, 0.0),
            "cyan": (0.0, 1.0, 1.0),
            "yellow": (1.0, 1.0, 0.0),
            "magenta": (1.0, 0.0, 1.0),
            "grey": (0.5, 0.5, 0.5),
        }
        rgb = color_map.get(color_name, (1.0, 1.0, 1.0))
        return (*rgb, alpha)

    @property
    def bound_box(self) -> Part:
        """Return the axis-aligned build bounding box."""
        x_len = max(self.tube_config.x_bounds) - min(self.tube_config.x_bounds)
        y_len = max(self.tube_config.y_bounds) - min(self.tube_config.y_bounds)
        z_len = max(self.tube_config.z_bounds) - min(self.tube_config.z_bounds)
        center = (
            min(self.tube_config.x_bounds) + x_len / 2,
            min(self.tube_config.y_bounds) + y_len / 2,
            min(self.tube_config.z_bounds) + z_len / 2,
        )
        with BuildPart() as bounds:
            Box(x_len, y_len, z_len)
            cast(Part, bounds.part).move(Location(center))
        return cast(Part, bounds.part)

    def create_part_position_point(self, name: str, offset: float, right: bool = False):
        """Build a part position point marker at the given offset."""
        tube = self.builder.create_part(name, right=right, tube_only=True)
        path = self.builder.create_wire(name)
        center = self.configurator.get_part_position(tube, path, offset)
        return Pos(center) * Sphere(radius=10)

    def create_solid_center_point(self, name: str, right: bool = False):
        """Build a solid center point marker for the part."""
        tube = self.builder.create_part(name, right=right, tube_only=True)
        return Pos(tube.center()) * Cone(
            bottom_radius=10, top_radius=0, height=10, align=(Align.CENTER, Align.CENTER, Align.MIN)
        )

    def show_positions_room(self):
        """Build geometry for the positions room."""
        to_show = {}
        for name in self.names:
            for right in [False, True]:
                side = "right" if right else "left"
                color = ("red" if right else "green") if name == "driver" else ("blue" if right else "orange")
                to_show[f"{name}_{side}"] = (self.builder.create_part(name, right=right, tube_only=False), color, 0.5)

                for i in range(10):
                    to_show[f"{name}_{side}_pos_{i}"] = (
                        self.create_part_position_point(name, i / 10, right=right),
                        color,
                        1.0,
                    )
                to_show[f"{name}_{side}_center"] = (self.create_solid_center_point(name, right=right), "blue", 1.0)
        to_show["bounds"] = (self.bound_box, "grey", 0.2)
        return to_show

    def show_overlay_room(self):
        """Build geometry for the overlay room."""
        to_show = {}
        for name in self.names:
            color = "cyan" if name == "driver" else "yellow"
            to_show[f"{name}_full_tube"] = (self.builder.create_tube(name), color, 0.2)
            for right in [False, True]:
                side = "right" if right else "left"
                color = ("red" if right else "green") if name == "driver" else ("blue" if right else "orange")
                to_show[f"{name}_{side}"] = (self.builder.create_part(name, right=right, tube_only=False), color, 1.0)
        to_show["bounds"] = (self.bound_box, "grey", 0.2)
        return to_show

    def show_profiles_room(self):
        """Build geometry for the profiles room."""
        return {
            "lap_joint_sketch": (self.builder.create_profile_sketch(180, lap_joint=True), "magenta", 1.0),
            "full_sketch": (self.builder.create_profile_sketch(360), "magenta", 1.0),
        }

    def view_part_positions(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Return visualization data for part positions."""
        room_data = self.show_positions_room()
        return [(obj, self._get_rgba(color, alpha)) for obj, color, alpha in room_data.values()]

    def view_overlay(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Return visualization data for the overlay view."""
        room_data = self.show_overlay_room()
        return [(obj, self._get_rgba(color, alpha)) for obj, color, alpha in room_data.values()]

    def view_wire(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Return visualization data for path wires."""
        return [(self.builder.create_wire(name), self._get_rgba("magenta", 1.0)) for name in self.names]

    def view_sketch(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Return visualization data for the profile sketches."""
        room_data = self.show_profiles_room()
        return [(obj, self._get_rgba(color, alpha)) for obj, color, alpha in room_data.values()]
