"""Valve actuator limiter geometry provider."""

import math
from functools import cached_property
from build123d import *  # type: ignore
import cadquery as cq
import numpy as np
from model import method_cache, DiagramOptions
from pathlib import Path
from provider import Provider, Action, Mode as ProviderMode, discover_provider
from projects_config.valve_actuator_limiter_config import ValveActuatorLimiterConfig
from typing import Any, cast, Callable, Sequence


@discover_provider
class ValveActuatorLimiterProvider(Provider):
    """Provider for valve actuator limiter geometry."""

    @cached_property
    def default_config(self) -> ValveActuatorLimiterConfig:
        """Return the default configuration for the limiter project."""
        return ValveActuatorLimiterConfig(
            measurements_path=str(Path(__file__).parent / "measurements.yaml"),
            diagram_options=DiagramOptions(line_weight=0.5, projection_dir=(0, 0, -1)),
        )

    @property
    def settings(self) -> ValveActuatorLimiterConfig:
        """Return the typed configuration settings."""
        return cast(ValveActuatorLimiterConfig, super().settings)

    @cached_property
    def hull_center(self) -> Vector:
        """Calculate the geometric center of the plate's base hull."""
        with BuildSketch() as s:
            with Locations(self.settings.bolt_holes):
                Circle(radius=self.settings.bolt_radius + self.settings.wall_thickness)
            make_hull()
        return s.sketch.center()

    @property
    def part(self) -> dict[str, Callable[..., Part]]:
        """A mapping of part names to their build handler methods."""
        return {"limiter": self.build_limiter, "plate": self.build_plate, "limiter_plate": self.build_limiter_plate}

    @property
    def diagram(self) -> dict[str, Callable[..., Any]]:
        """A mapping of diagram names to their build handler methods."""
        return {name: self.build_diagram for name in self.targets.supporting(Action.DIAGRAM)}

    @method_cache
    def build_limiter(
        self, target: str, subassembly: str = "90deg", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Create a 3D sector (limiter) solid using only 3D primitives."""
        r = self.settings.pocket_radius
        h = self.settings.pocket_depth
        start_angle = 180 if subassembly == "0deg" else 90 if subassembly == "90deg" else 270
        cutter_size = r * 3

        with BuildPart() as limiter_gen:
            Cylinder(radius=r, height=h, align=(Align.CENTER, Align.CENTER, Align.MIN))

            # Use two rotated boxes as half-plane cutters to isolate the stop_angle sector
            with Locations(Rot(0, 0, start_angle - 90)):
                Box(cutter_size, cutter_size, h, align=(Align.MIN, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)
            with Locations(Rot(0, 0, start_angle + self.settings.stop_angle + 90)):
                Box(cutter_size, cutter_size, h, align=(Align.MIN, Align.CENTER, Align.CENTER), mode=Mode.SUBTRACT)

            # Blunt the sharp tip of the wedge
            angle = start_angle + self.settings.stop_angle / 2
            with Locations(Rot(0, 0, angle)):
                Box(2.0, 2.0, h, mode=Mode.SUBTRACT)

        return limiter_gen

    @method_cache
    def build_plate(
        self, target: str, subassembly: str = "90deg", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the geometry for a limiter plate."""
        with BuildPart() as p:
            # Generate the structural outer profile
            with BuildSketch():
                with Locations(self.settings.bolt_holes):
                    Circle(radius=self.settings.bolt_radius + self.settings.wall_thickness)
                make_hull()
            extrude(amount=self.settings.wall_thickness)

            with Locations((self.hull_center.X, self.hull_center.Y, 0)):
                Cylinder(
                    radius=self.settings.pocket_radius + self.settings.wall_thickness,
                    height=self.settings.pocket_depth,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.ADD,
                )

            # Cut back the plate between holes 2 and 3 to clear the obstruction
            # (Assumes holes are indices 1 and 2 in the bolt_holes list)
            holes = self.settings.bolt_holes
            if len(holes) >= 3:
                h2, h3 = holes[1], holes[2]
                edge_vec = h3 - h2
                midpoint = (h2 + h3) * 0.5
                # Compute a normal pointing outwards from the part center
                outward_normal = Vector(edge_vec.Y, -edge_vec.X).normalized()
                cylinder_offset = self.settings.pocket_radius + self.settings.wall_thickness
                half_dist = edge_vec.length / 2
                boss_radius = self.settings.bolt_radius + self.settings.wall_thickness
                scallop_radius = math.sqrt(half_dist**2 + cylinder_offset**2) - boss_radius

                # Place a large cylinder to create a concave scalloped cut along the edge
                with Locations(midpoint + outward_normal * cylinder_offset):
                    Cylinder(
                        radius=scallop_radius,
                        height=1000,
                        align=(Align.CENTER, Align.CENTER, Align.CENTER),
                        mode=Mode.SUBTRACT,
                    )

                # Add zip tie notches to the remaining two edges (Edge 0-1 and 2-0)
                for i, j in [(0, 1), (2, 0)]:
                    h_i, h_j = holes[i], holes[j]
                    v_edge = h_j - h_i
                    v_unit = v_edge.normalized()
                    v_out = Vector(v_edge.Y, -v_edge.X).normalized()
                    v_angle = math.degrees(math.atan2(v_edge.Y, v_edge.X))

                    for dist in [self.settings.zip_tie_hole_offset, v_edge.length - self.settings.zip_tie_hole_offset]:
                        # Ensure wall of 'wall_thickness' remains between the outer edge and the cut
                        cut_h = self.settings.zip_tie_cut_height
                        cut_pos = boss_radius - self.settings.wall_thickness - (cut_h / 2)
                        with Locations(h_i + v_unit * dist + v_out * cut_pos):
                            with Locations(Rot(0, 0, v_angle)):
                                Box(
                                    self.settings.zip_tie_cut_width,
                                    cut_h,
                                    100.0,
                                    mode=Mode.SUBTRACT,
                                )

            # Subtract the center pocket for the actuator drive mechanism
            with Locations((self.hull_center.X, self.hull_center.Y, 0)):
                Cylinder(
                    radius=self.settings.pocket_radius,
                    height=self.settings.wall_thickness + self.settings.pocket_depth + 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

            # Drill M6 bolt alignment holes through the entire part
            with Locations([(v.X, v.Y, 0) for v in self.settings.bolt_holes]):
                Cylinder(
                    radius=self.settings.bolt_radius,
                    height=self.settings.wall_thickness + self.settings.pocket_depth + 2.0,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
        return p

    @method_cache
    def build_limiter_plate(
        self, target: str, subassembly: str = "90deg", mode: ProviderMode = ProviderMode.DEFAULT
    ) -> BuildPart:
        """Build the geometry for a limiter plate."""
        with BuildPart() as p:
            plate = self.build_plate("_plate", subassembly=subassembly, mode=mode)
            add(plate)
            with Locations((self.hull_center.X, self.hull_center.Y, 0)):
                add(self.build_limiter("_limiter", subassembly=subassembly, mode=mode))
        return p

    @method_cache
    def build_diagram(self, targets: Sequence[str], mode: ProviderMode) -> BuildPart:
        """Build an assembly diagram for the limiter plates."""
        # Build only the limiter plate for diagram viewing
        plate = self.build_limiter_plate("limiter_plate")
        return plate
