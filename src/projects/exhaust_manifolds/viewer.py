"""Viewer for manifold tube geometry."""

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, Literal, cast
from build123d import *  # type: ignore
from model.app_config import AppConfig
from projects_config import ExhaustManifoldsConfig
from .builder import ExhaustManifoldsBuilder
from provider import Room, ColorType
from .configurator import ExhaustManifoldsConfigurator


class ExhaustManifoldsViewer:
    """Viewer for exhaust manifold geometry."""

    def __init__(
        self,
        builder: ExhaustManifoldsBuilder,
        configurator: ExhaustManifoldsConfigurator,
        config: AppConfig,
        exhaust_manifolds_config: ExhaustManifoldsConfig,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """Initialize the viewer with a builder and config."""
        self.builder = builder
        self.configurator = configurator
        self.config = config
        self.exhaust_manifolds_config = exhaust_manifolds_config
        self.executor = executor or ThreadPoolExecutor()
        self.names = self.exhaust_manifolds_config.names

    @property
    def bound_box(self) -> Part:
        """Return the axis-aligned build bounding box."""
        x_len = max(self.exhaust_manifolds_config.x_bounds) - min(self.exhaust_manifolds_config.x_bounds)
        y_len = max(self.exhaust_manifolds_config.y_bounds) - min(self.exhaust_manifolds_config.y_bounds)
        z_len = max(self.exhaust_manifolds_config.z_bounds) - min(self.exhaust_manifolds_config.z_bounds)
        center = (
            min(self.exhaust_manifolds_config.x_bounds) + x_len / 2,
            min(self.exhaust_manifolds_config.y_bounds) + y_len / 2,
            min(self.exhaust_manifolds_config.z_bounds) + z_len / 2,
        )
        with BuildPart() as bounds:
            Box(x_len, y_len, z_len)
            bounds.part = cast(Part, bounds.part).move(Location(center))
        return cast(Part, bounds.part)

    def create_part_position_point(self, name: str, offset: float, right: bool = False):
        """Build a part position point marker at the given offset."""
        tube = self.builder.create_part(name, right=right, tube_only=True).part
        path = self.builder.create_wire(name)
        center = self.configurator.get_part_position(tube, path, offset)
        return Pos(center) * Sphere(radius=10)  # Sphere is a Part, not a BuildPart

    def create_solid_center_point(self, name: str, right: bool = False):
        """Build a solid center point marker for the part."""
        tube = self.builder.create_part(name, right=right, tube_only=True).part
        return Pos(tube.center()) * Cone(
            bottom_radius=10, top_radius=0, height=10, align=(Align.CENTER, Align.CENTER, Align.MIN)
        )

    def view_part_positions(self, room: Room) -> None:
        """Return visualization data for part positions."""
        for name in self.names:
            for right in [False, True]:
                side = "right" if right else "left"
                color = (
                    (ColorType.RED if right else ColorType.GREEN)
                    if name == "driver"
                    else (ColorType.BLUE if right else ColorType.ORANGE)
                )
                room.add(
                    f"{name}_{side}",
                    self.builder.create_part(name, right=right, tube_only=False),
                    color=color,
                    alpha=0.5,
                )

                for i in range(10):
                    room.add(
                        f"{name}_{side}_pos_{i}",
                        self.create_part_position_point(name, i / 10, right=right),
                        color=color,
                    )
                room.add(
                    f"{name}_{side}_center", self.create_solid_center_point(name, right=right), color=ColorType.BLUE
                )
        room.add("bounds", self.bound_box, color=ColorType.GREY, alpha=0.2)

    def view_overlay(self, room: Room) -> None:
        """Return visualization data for the overlay view."""
        for name in self.names:
            color = ColorType.CYAN if name == "driver" else ColorType.YELLOW
            room.add(f"{name}_full_tube", self.builder.create_manifold(name), color=color, alpha=0.2)
            for right in [False, True]:
                side = "right" if right else "left"
                color = (
                    (ColorType.RED if right else ColorType.GREEN)
                    if name == "driver"
                    else (ColorType.BLUE if right else ColorType.ORANGE)
                )
                room.add(
                    f"{name}_{side}",
                    self.builder.create_part(name, right=right, tube_only=False),
                    color=color,
                )
        room.add("bounds", self.bound_box, color=ColorType.GREY, alpha=0.2)

    def view_wire(self, room: Room) -> None:
        """Return visualization data for path wires."""
        for name in self.names:
            room.add(f"{name}_wire", self.builder.create_wire(name), color=ColorType.MAGENTA)

    def view_sketch(self, room: Room) -> None:
        """Return visualization data for the profile sketches."""
        room.add("lap_joint_sketch", self.builder.create_profile_sketch(180, lap_joint=True), color=ColorType.MAGENTA)
        room.add("full_sketch", self.builder.create_profile_sketch(360), color=ColorType.MAGENTA)
