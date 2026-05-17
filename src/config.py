"""Run manifold configuration steps before building."""

from build import AppConfig, Builder, Logger
from functools import lru_cache
import argparse
import cadquery as cq
from typing import cast, Any
import numpy as np
import json


class Configurator:
    """Runs configuration steps on the app config."""

    def __init__(self, builder=None, config=None, logger=None):
        """Initialize the configurator."""
        self.config = config or AppConfig(**{"_env_file": None})
        self.logger = logger or Logger(text="Configuring...", enabled=False)
        self.builder = builder or Builder(config=config, logger=logger)
        self._tube_cache = {}
        self._path_cache = {}

    @lru_cache
    def get_part_position(self, tube, path, off):
        """Get a suitable attachment position on the tube."""
        radius = min(self.builder.config.clamp_diameters) / 2
        self._tube_cache[id(tube)] = tube
        self._path_cache[id(path)] = path
        return self.get_part_position_cached(id(tube), id(path), off, radius)

    @lru_cache
    def get_part_position_cached(self, tube_id, path_id, off, radius):
        """Get a cached attachment position on the tube."""
        tube = self._tube_cache[tube_id]
        path = self._path_cache[path_id]
        pos = path.val().positionAt(off)
        midpoint_up = pos + cq.Vector(0, 0, radius)
        midpoint_down = pos - cq.Vector(0, 0, radius)
        solid_center = tube.val().Center()
        dist_up = midpoint_up.sub(solid_center).Length
        dist_down = midpoint_down.sub(solid_center).Length
        return midpoint_up if dist_up < dist_down else midpoint_down

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

    def parts_not_touching(self, c_shape, o_shape, c_box, o_box, tol=0.1):
        """Return True if the candidate does not intersect the other object."""
        # Bail early checks here before doing expensive boolean thing.
        if not self.shapes_overlap(c_box, o_box):
            return True
        elif c_shape.distance(o_shape) > tol:
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
        for angle in angles:
            candidate = candidate_factory(float(angle))
            c_shape = candidate.val()
            c_box = c_shape.BoundingBox()
            if self.parts_not_touching(c_shape, o_shape, c_box, o_box):
                candidate_center = c_shape.Center()
                distance = (candidate_center - center).Length
                if distance < best_distance:
                    best_distance = distance
                    best_angle = float(angle)
        return best_angle

    def find_best_angle(self, candidate_factory, other_obj, center, coarse_step=None, fine_window=None, fine_step=1):
        """Find the best offset with a coarse sweep followed by a fine search."""
        if coarse_step:
            coarse_angles = np.arange(0, 360, coarse_step)
            best_angle = self.scan_angles(coarse_angles, candidate_factory, other_obj, center)
            if best_angle is None:
                return None
            fine_angles = self.angle_window(best_angle, fine_window, fine_step)
            return self.scan_angles(fine_angles, candidate_factory, other_obj, center)
        else:
            fine_angles = np.arange(0, 360, fine_step)
            return self.scan_angles(fine_angles, candidate_factory, other_obj, center)

    def config_clamp(self, name):
        """Tune clamp positions for a part."""
        tube = self.builder.build_part(name, tube_only=True)
        other_tube = self.builder.build_part(name, right=True, tube_only=True)
        path = self.builder.create_wire(name)

        for idx in range(1, len(self.config.clamp_positions[name]) - 1):
            clamp_offset, _ = self.config.clamp_positions[name][idx]  # type: ignore
            center = self.get_part_position(tube, path, clamp_offset)

            def build_clamp(angle):
                return self.builder.build_clamp_bed(name, idx, offset_deg=angle, joint_space=0)

            offset_deg = self.find_best_angle(
                build_clamp,
                other_tube,
                center,
                fine_step=1,
            )

            # Update the clamp offset
            if not offset_deg is None:
                self.config.clamp_positions[name][idx] = (cast(float, clamp_offset), float(offset_deg))
                self.logger.print(f"angle offset for {name} clamp {idx} updated to {offset_deg}°", symbol="📐")

    def config_text_logo(self, name):
        """Tune logo text placement for a part."""
        tube = self.builder.build_part(name, right=True, tube_only=True)
        other_tube = self.builder.build_part(name, tube_only=True)
        path = self.builder.create_wire(name)
        text_offset, _ = self.config.logo_text_positions[name]
        center = self.get_part_position(tube, path, text_offset)

        def build_text(angle):
            return self.builder.build_text(name, right=True, offset_deg=angle, font_path="Sans")

        offset_deg = self.find_best_angle(
            build_text,
            other_tube,
            center,
            coarse_step=30,
            fine_window=15,
            fine_step=1,
        )

        # Update the text offset
        if not offset_deg is None:
            self.config.logo_text_positions[name] = (cast(float, text_offset), float(offset_deg))
            self.logger.print(f"angle offset for {name} text logo updated to {offset_deg}°", symbol="📐")

    def configure_clamps(self, names=None):
        """Configure clamps for all specified parts."""
        if names is None:
            names = self.config.names
        for name in names:
            self.config_clamp(name)

    def configure_text_logos(self, names=None):
        """Configure logo text for all specified parts."""
        if names is None:
            names = self.config.names
        for name in names:
            self.config_text_logo(name)

    def configure_all(self, names=None):
        """Perform all configuration steps."""
        if names is None:
            names = self.config.names
        self.configure_clamps(names)
        self.configure_text_logos(names)


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
    config = AppConfig(**{"_env_file": None})
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
                    # Fix json.decoder.JSONDecodeError
                    value_str = json.dumps(value)
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
