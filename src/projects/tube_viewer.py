"""Viewer for manifold tube geometry."""

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, Literal, cast
from build123d import *  # type: ignore
from model.app_config import AppConfig
from projects_config import TubeConfig
from .tube_builder import TubeBuilder


class TubeViewer:
    """Viewer for tube geometry."""

    def __init__(
        self,
        builder: TubeBuilder,
        config: AppConfig,
        tube_config: TubeConfig,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """Initialize the viewer with a builder and config."""
        self.builder = builder
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

    def create_part_position_point(self, name: str, offset: float, right: bool = False):
        """Build a part position point marker at the given offset."""
        tube = self.builder.create_part(name, right=right, tube_only=True)
        path = self.builder.create_wire(name)
        radius = min(self.tube_config.clamp_diameters) / 2
        pos = path.position_at(offset)
        # Orientation is normal (up) if midpoint_up is closer to solid center than path position.
        normal = (tube.center() - (pos + Vector(0, 0, 1))).length < (tube.center() - pos).length
        center = pos + (Vector(0, 0, radius) if normal else Vector(0, 0, -radius))
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
        return to_show

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

    def view_part_positions(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Return visualization data for part positions."""
        room_data = self.show_positions_room()
        return [(obj, self._get_rgba(color, alpha)) for obj, color, alpha in room_data.values()]

    def view_overlay(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Return visualization data for the overlay view."""
        room_data = self.show_overlay_room()
        return [(obj, self._get_rgba(color, alpha)) for obj, color, alpha in room_data.values()]

    def view_tube_profile(self) -> list[tuple[Any, tuple[float, float, float, float]]]:
        """Return visualization data for the profile sketches."""
        room_data = self.show_profiles_room()
        return [(obj, self._get_rgba(color, alpha)) for obj, color, alpha in room_data.values()]
