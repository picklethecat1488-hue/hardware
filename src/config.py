"""Run manifold configuration steps before building."""

from model import AppConfig, method_cache
from build import Builder
from shell import Logger
import argparse
import cadquery as cq
from typing import cast, Any, Literal, Annotated, Optional
from pydantic import validate_call, Field
import numpy as np
import json
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor


class Configurator:
    """Runs configuration steps on the app config."""

    def __init__(self, builder=None, config=None, logger=None):
        """Initialize the configurator."""
        self.config = config or AppConfig()
        self.logger = logger or Logger(text="Configuring...", enabled=False)
        self.builder = builder or Builder(config=config, logger=logger)
        self._tube_cache = {}
        self._path_cache = {}
        self.executor = ThreadPoolExecutor()

    def get_part_position(self, tube, path, off):
        """Get a suitable attachment position on the tube."""
        radius = min(self.builder.config.clamp_diameters) / 2
        self._tube_cache[id(tube)] = tube
        self._path_cache[id(path)] = path
        return self.get_part_position_cached(id(tube), id(path), off, radius)

    @method_cache
    def get_orientation_normal(self, tube_id, path_id):
        """Get if we should use midpoint_up, otherwise use midpoint_down."""
        tube = self._tube_cache[tube_id]
        path = self._path_cache[path_id]
        p_tube = cast(Any, tube.val())
        p_shape = cast(Any, path.val())
        pos = p_shape.positionAt(0.5)
        midpoint_up = pos + cq.Vector(0, 0, 1)
        solid_center = p_tube.Center()
        # Orientation is normal if midpoint_up is closer to solid center than path position.
        return (solid_center - midpoint_up).Length < (solid_center - pos).Length

    @method_cache
    def get_part_position_cached(self, tube_id, path_id, off, radius):
        """Get a cached attachment position on the tube."""
        path = self._path_cache[path_id]
        p_shape = cast(Any, path.val())
        pos = p_shape.positionAt(off)
        midpoint_up = pos + cq.Vector(0, 0, radius)
        midpoint_down = pos + cq.Vector(0, 0, -radius)
        orientation_normal = self.get_orientation_normal(tube_id, path_id)
        return midpoint_up if orientation_normal else midpoint_down

    def shapes_overlap(self, lhs_box, rhs_box):
        """Return True when two CAD objects' bounding boxes overlap."""
        return not (
            lhs_box.xmax < rhs_box.xmin
            or lhs_box.xmin > rhs_box.xmax
            or lhs_box.ymax < rhs_box.ymin
            or lhs_box.ymin > rhs_box.ymax
            or lhs_box.zmax < rhs_box.zmin
            or lhs_box.zmin > rhs_box.zmax
        )

    def parts_not_touching(self, c_shape, o_shape, c_box, o_box):
        """Return True if the candidate does not intersect the other object."""
        # Bail early checks here before doing expensive boolean thing.
        if not self.shapes_overlap(c_box, o_box):
            return True
        else:
            return not c_shape.intersect(o_shape).Solids()

    def angle_window(self, center, radius, step):
        """Return a wrapped angular window around a center angle."""
        start = int(center - radius)
        end = int(center + radius)
        return [(angle % 360) for angle in range(start, end + 1, step)]

    def scan_angles(self, angles, candidate_factory, other_obj, center):
        """Scan angle candidates and return the best angle based on distance."""
        best_angle = None
        best_distance = float("inf")
        o_shape = other_obj.val()
        o_box = o_shape.BoundingBox()

        def check_angle(angle):
            candidate = candidate_factory(float(angle))
            c_shape = candidate.val()
            c_box = c_shape.BoundingBox()
            if self.parts_not_touching(c_shape, o_shape, c_box, o_box):
                candidate_center = c_shape.Center()
                distance = (candidate_center - center).Length
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
        tube = self.builder.build_part(name, tube_only=True)
        other_tube = self.builder.build_part(name, right=True, tube_only=True)
        path = self.builder.create_wire(name)

        for idx in range(1, len(self.config.clamp_positions[name]) - 1):
            pos_info = self.config.clamp_positions[name][idx]
            if not pos_info is None:
                clamp_offset, _ = pos_info
                center = self.get_part_position(tube, path, clamp_offset)
                offset_deg = self.find_best_angle(
                    lambda angle: self.builder.build_clamp_bed(name, idx, offset_deg=angle),
                    other_tube,
                    center,
                )

                # Update the clamp offset
                if offset_deg is None:
                    raise ValueError(f"failed to configure {name} clamp")
                self.config.clamp_positions[name][idx] = (cast(float, clamp_offset), float(offset_deg))
                self.logger.print(f"angle offset for {name} clamp {idx} updated to {offset_deg}°", symbol="📐")

    @validate_call(config={"arbitrary_types_allowed": True})
    def config_text_logo(self, name: Literal["driver", "passenger"]):
        """Tune logo text placement for a part."""
        tube = self.builder.build_part(name, right=True, tube_only=True)
        other_tube = self.builder.build_part(name, tube_only=True)
        path = self.builder.create_wire(name)
        text_offset, _ = self.config.logo_text_positions[name]
        center = self.get_part_position(tube, path, text_offset)
        offset_deg = self.find_best_angle(
            lambda angle: self.builder.build_text(name, "FHB", right=True, offset_deg=angle),
            other_tube,
            center,
        )

        # Update the text offset
        if offset_deg is None:
            raise ValueError(f"failed to configure {name} text logo")
        self.config.logo_text_positions[name] = (cast(float, text_offset), float(offset_deg))
        self.logger.print(f"angle offset for {name} text logo updated to {offset_deg}°", symbol="📐")

    @validate_call(config={"arbitrary_types_allowed": True})
    def configure_clamps(self, names: list[Literal["driver", "passenger"]] = ["driver", "passenger"]):
        """Configure clamps for all specified parts."""
        # Run configuration tasks for each part in parallel.
        futures = [self.executor.submit(self.config_clamp, name) for name in names]
        for future in futures:
            future.result()

    @validate_call(config={"arbitrary_types_allowed": True})
    def configure_text_logos(self, names: list[Literal["driver", "passenger"]] = ["driver", "passenger"]):
        """Configure logo text for all specified parts."""
        if names is None:
            names = self.config.names
        # Run configuration tasks for each part in parallel.
        futures = [self.executor.submit(self.config_text_logo, name) for name in names]
        for future in futures:
            future.result()

    @validate_call(config={"arbitrary_types_allowed": True})
    def configure_all(self, names: list[Literal["driver", "passenger"]] = ["driver", "passenger"]):
        """Perform all configuration steps."""
        # Execute clamp and logo configuration in parallel to maximize throughput.
        f1 = self.executor.submit(self.configure_clamps, names)
        f2 = self.executor.submit(self.configure_text_logos, names)
        f1.result()
        f2.result()


def get_args():
    """Get parsed arguments for the program.

    :return _type_: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Configuration Utility.")
    parser.add_argument("-e", "--env", required=False, default=".env", help="Output environment to file.")
    parser.add_argument("-n", "--name", required=False, default=None, help="The part to configure.")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-c", "--clamps", required=False, action="store_true", help="Configure part clamps.")
    group.add_argument("-t", "--logo_text", required=False, action="store_true", help="Configure logo text.")
    args = parser.parse_args()
    return args


def main(logger, args):
    """Initialize the build environment and perform build actions.

    :param _type_ args: The program arguments.
    """
    gen_args = {}
    if not args.name is None:
        gen_args["names"] = [args.name]
    config = AppConfig()

    builder = Builder(config, logger)
    configurator = Configurator(builder, config, logger)

    # Perform requested configurations, output the model, and exit.
    if args.clamps:
        configurator.configure_clamps(**gen_args)
    elif args.logo_text:
        configurator.configure_text_logos(**gen_args)
    else:
        configurator.configure_all(**gen_args)

    # Output the changed items only and exit.
    changed_items = config.model_dump(by_alias=True)
    if len(changed_items) > 0:
        with open(args.env, "w") as file:
            for key, value in changed_items.items():
                if isinstance(value, (dict, list)):
                    # Use compact separators to ensure standard .env parsing
                    value_str = json.dumps(value, separators=(",", ":"))
                else:
                    value_str = str(value)
                file.write(f"{key}={value_str}\n")
            logger.print(f"Saved environment to {args.env}", symbol="⚙️ ")
    logger.done()


if __name__ == "__main__":
    """Program entry point.
    """
    logger = Logger(text="Configuring...")
    args = get_args()
    main(logger, args)
