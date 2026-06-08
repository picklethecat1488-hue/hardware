"""Configurator for manifold tube geometry."""

from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Literal, cast
from build123d import *  # type: ignore
from pydantic import validate_call
from model.utils import method_cache
from model.app_config import AppConfig
from projects_config import ExhaustManifoldsConfig
from shell import Logger
from .builder import ExhaustManifoldsBuilder


class ExhaustManifoldsConfigurator:
    """Configurator for exhaust manifold geometry."""

    def __init__(
        self,
        builder: ExhaustManifoldsBuilder,
        config: AppConfig,
        exhaust_manifolds_config: ExhaustManifoldsConfig,
        executor: Optional[ThreadPoolExecutor] = None,
        logger: Optional[Logger] = None,
    ):
        """Initialize the configurator with a builder and config."""
        self.builder = builder
        self.config = config
        self.exhaust_manifolds_config = exhaust_manifolds_config
        self._tube_cache = {}
        self._path_cache = {}
        self.executor = executor or ThreadPoolExecutor()
        self.logger = logger or Logger(enabled=False)

    @validate_call(config={"arbitrary_types_allowed": True})
    def get_part_position(self, tube: Part | Solid, path: Wire, off: float):
        """Get a suitable attachment position on the tube."""
        radius = min(self.exhaust_manifolds_config.clamp_diameters) / 2
        self._tube_cache[id(tube)] = tube
        self._path_cache[id(path)] = path
        return self.get_part_position_cached(id(tube), id(path), off, radius)

    @method_cache()
    @validate_call(config={"arbitrary_types_allowed": True})
    def get_orientation_normal(self, tube_id, path_id):
        """Return True if we should use midpoint_up, False if we should use midpoint_down."""
        tube: Part | Solid = self._tube_cache[tube_id]
        path: Wire = self._path_cache[path_id]
        pos = path.position_at(0.5)
        midpoint_up = pos + Vector(0, 0, 1)
        solid_center = tube.center()
        # Orientation is normal if midpoint_up is closer to solid center than path position.
        return (solid_center - midpoint_up).length < (solid_center - pos).length

    @method_cache()
    @validate_call(config={"arbitrary_types_allowed": True})
    def get_part_position_cached(self, tube_id, path_id, off, radius):
        """Get a cached attachment position on the tube."""
        path: Wire = self._path_cache[path_id]
        pos = path.position_at(off)
        midpoint_up = pos + Vector(0, 0, radius)
        midpoint_down = pos + Vector(0, 0, -radius)
        orientation_normal = self.get_orientation_normal(tube_id, path_id)
        return midpoint_up if orientation_normal else midpoint_down

    @validate_call(config={"arbitrary_types_allowed": True})
    def shapes_overlap(self, lhs_box: BoundBox, rhs_box: BoundBox):
        """Return True when two CAD objects' bounding boxes overlap."""
        return not (
            lhs_box.max.X < rhs_box.min.X
            or lhs_box.min.X > rhs_box.max.X
            or lhs_box.max.Y < rhs_box.min.Y
            or lhs_box.min.Y > rhs_box.max.Y
            or lhs_box.max.Z < rhs_box.min.Z
            or lhs_box.min.Z > rhs_box.max.Z
        )

    @validate_call(config={"arbitrary_types_allowed": True})
    def parts_not_touching(self, c_shape: Part | Solid, o_shape: Part | Solid, c_box: BoundBox, o_box: BoundBox):
        """Return True if the candidate does not intersect the other object."""
        # Bail early checks here before doing expensive boolean thing.
        if not self.shapes_overlap(c_box, o_box):
            return True
        else:
            return len(cast(Part | Solid, (c_shape & o_shape)).solids()) == 0

    @validate_call(config={"arbitrary_types_allowed": True})
    def angle_window(self, center, radius, step):
        """Return a wrapped angular window around a center angle."""
        start = int(center - radius)
        end = int(center + radius)
        return [(angle % 360) for angle in range(start, end + 1, step)]

    @validate_call(config={"arbitrary_types_allowed": True})
    def scan_angles(self, angles, candidate_factory, other_obj: Part | Solid, center: Vector):
        """Scan angle candidates and return the best angle based on distance."""
        best_angle = None
        best_distance = float("inf")
        o_box = other_obj.bounding_box()

        def check_angle(angle):
            candidate_builder = candidate_factory(float(angle))
            candidate_part = candidate_builder.part
            c_box = candidate_part.bounding_box()
            if self.parts_not_touching(candidate_part, other_obj, c_box, o_box):
                candidate_center = candidate_part.center()
                distance = (candidate_center - center).length
                return angle, distance
            return None, None

        # Parallelize the angle scanning to utilize multiple CPU cores for CAD calculations.
        results = self.executor.map(check_angle, angles)
        for angle, distance in results:
            if angle is not None and distance is not None:
                if distance < best_distance:
                    best_distance = distance
                    best_angle = float(angle)
        return best_angle

    @validate_call(config={"arbitrary_types_allowed": True})
    def find_best_angle(self, candidate_factory, other_obj, center, coarse_window=10, fine_window=30, fine_step=1):
        """Find the best offset using a windowed search strategy."""
        coarse_angles = list(range(0, 360, coarse_window))
        best_coarse = self.scan_angles(coarse_angles, candidate_factory, other_obj, center)
        if best_coarse is not None:
            radius = fine_window / 2
            fine_angles = self.angle_window(best_coarse, radius, fine_step)
            return self.scan_angles(fine_angles, candidate_factory, other_obj, center)
        return None

    @validate_call(config={"arbitrary_types_allowed": True})
    def config_clamp(self, name: Literal["driver", "passenger"]):
        """Tune clamp positions for a part."""
        tube = self.builder.create_part(name, tube_only=True).part
        other_tube = self.builder.create_part(name, right=True, tube_only=True).part
        path = self.builder.create_wire(name)

        for idx in range(1, len(self.exhaust_manifolds_config.clamp_positions[name]) - 1):
            pos_info = self.exhaust_manifolds_config.clamp_positions[name][idx]
            if pos_info is not None:
                clamp_offset, _ = pos_info
                center = self.get_part_position(tube, path, clamp_offset)
                offset_deg = self.find_best_angle(
                    lambda angle: self.builder.create_clamp_bed(name, idx, offset_deg=angle),
                    other_tube,
                    center,
                )

                # Update the clamp offset
                if offset_deg is None:
                    raise ValueError(f"failed to configure {name} clamp") from None
                self.exhaust_manifolds_config.clamp_positions[name][idx] = (
                    cast(float, clamp_offset),
                    float(offset_deg),
                )
                self.logger.print(f"angle offset for {name} clamp {idx} updated to {offset_deg}°", symbol="📐")

    @validate_call(config={"arbitrary_types_allowed": True})
    def config_text_logo(self, name: Literal["driver", "passenger"]):
        """Tune logo text placement for a part."""
        tube = self.builder.create_part(name, right=True, tube_only=True).part
        other_tube = self.builder.create_part(name, tube_only=True).part
        path = self.builder.create_wire(name)
        text_offset, _ = self.exhaust_manifolds_config.logo_text_positions[name]
        center = self.get_part_position(tube, path, text_offset)
        offset_deg = self.find_best_angle(
            lambda angle: self.builder.create_text(name, "FHB", right=True, offset_deg=angle),
            other_tube,
            center,
        )

        # Update the text offset
        if offset_deg is None:
            raise ValueError(f"failed to configure {name} text logo") from None
        self.exhaust_manifolds_config.logo_text_positions[name] = (cast(float, text_offset), float(offset_deg))
        self.logger.print(f"angle offset for {name} text logo updated to {offset_deg}°", symbol="📐")

    def config_mount(self, target: str, subassembly: Optional[str]) -> None:
        """Configure mounting hardware positions."""
        name = cast(Literal["driver", "passenger"], target)
        self.config_clamp(name)

    def config_text(self, target: str, subassembly: Optional[str]) -> None:
        """Configure text logo positions."""
        name = cast(Literal["driver", "passenger"], target)
        self.config_text_logo(name)
