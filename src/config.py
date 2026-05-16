"""Run any pre-build configuration steps."""

from build import AppConfig, Builder, Logger
from functools import lru_cache
import argparse
import cadquery as cq
import json


class Configurator:
    """Runs configuration steps on the app config."""

    def __init__(self, builder=None, config=None, logger=None):
        """Initialize the configurator.

        :param _type_ builder: The Builder to use, defaults to None
        :param _type_ config: The Configurator to use, defaults to None
        :param _type_ logger: The Logger to use, defaults to None
        """
        self.config = config or AppConfig()
        self.logger = logger or Logger(text="Configuring...", enabled=False)
        self.builder = builder or Builder(config=config, logger=logger)
        self._tube_cache = {}
        self._path_cache = {}

    def get_part_position(self, tube, path, off):
        """Get the part position of the tube at offset.

        If a part is attached to this offset, it should be attached
        as close to the part position as possible.

        :param _type_ part: The tube to test
        :param _type_ path: The wire path used to create the tube
        :param _type_ off: The path offset to use
        :return _type_: The part midpoint of the tube.
        """
        radius = min(self.builder.config.clamp_diameters) / 2
        self._tube_cache[id(tube)] = tube
        self._path_cache[id(path)] = path
        return self.get_part_position_cached(id(tube), id(path), off, radius)

    @lru_cache
    def get_part_position_cached(self, tube_id, path_id, off, radius):
        """Get the part position of the tube at offset.

        If a part is attached to this offset, it should be attached
        as close to the part position as possible.

        :param _type_ part: The tube to test
        :param _type_ path: The wire path used to create the tube
        :param _type_ off: The path offset to use
        :return _type_: The part midpoint of the tube.
        """
        tube = self._tube_cache[tube_id]
        path = self._path_cache[path_id]
        pos = path.val().positionAt(off)
        midpoint_up = pos + cq.Vector(0, 0, radius)
        midpoint_down = pos - cq.Vector(0, 0, radius)
        solid_center = tube.val().Center()
        dist_up = midpoint_up.sub(solid_center).Length
        dist_down = midpoint_down.sub(solid_center).Length
        return midpoint_up if dist_up < dist_down else midpoint_down

    def boxes_overlap(self, lhs, rhs):
        """Return True when two CAD objects' bounding boxes overlap."""
        lhs_box = lhs.val().BoundingBox()
        rhs_box = rhs.val().BoundingBox()
        return not (
            lhs_box.xmax < rhs_box.xmin
            or lhs_box.xmin > rhs_box.xmax
            or lhs_box.ymax < rhs_box.ymin
            or lhs_box.ymin > rhs_box.ymax
            or lhs_box.zmax < rhs_box.zmin
            or lhs_box.zmin > rhs_box.zmax
        )

    def is_geometry_clear(self, candidate, other):
        """Return True if the candidate does not intersect the other object."""
        if not self.boxes_overlap(candidate, other):
            return True
        return candidate.intersect(other).val().Volume() == 0

    def config_clamp(self, name):
        """Configure clamps.

        We need to sweep angle offsets for this part to minimize the center of mass distances between clamp
        and bare part, on both the left and right side. We combine both
        distances into an average value to index on which offset is most optimal.

        :param _type_ name: The name of the part to configure.
        """
        tube = self.builder.build_part(name, tube_only=True)
        other_tube = self.builder.build_part(name, right=True, tube_only=True)
        path = self.builder.create_wire(name)

        for idx in range(1, len(self.config.clamp_positions[name]) - 1):
            min_distance = float("inf")
            offset_deg = None
            clamp_offset, _ = self.config.clamp_positions[name][idx]  # type: ignore
            center = self.get_part_position(tube, path, clamp_offset)

            for cur_offset_deg in range(360):
                # Compute Center of Mass distance for each part side
                clamp = self.builder.build_clamp_bed(name, idx, offset_deg=float(cur_offset_deg))
                clamp_center = clamp.val().Center()  # type: ignore
                distance = (clamp_center - center).Length

                # Update the distance tracker
                if (distance < min_distance) and self.is_geometry_clear(clamp, other_tube):
                    min_distance = distance
                    offset_deg = cur_offset_deg

            # Update the clamp offset
            if not offset_deg is None:
                self.config.clamp_positions[name][idx] = (clamp_offset, float(offset_deg))  # type: ignore
                self.logger.print(f"angle offset for {name} clamp {idx} updated to {offset_deg}°", symbol="📐")

    def config_text_logo(self, name):
        """Configure text logo.

        :param _type_ name: The name of the part to configure.
        """
        tube = self.builder.build_part(name, right=True, tube_only=True)
        other_tube = self.builder.build_part(name, tube_only=True)
        path = self.builder.create_wire(name)
        text_offset, _ = self.config.logo_text_positions[name]
        center = self.get_part_position(tube, path, text_offset)
        min_distance = float("inf")
        offset_deg = None

        for cur_offset_deg in range(0, 360, 1):
            # Compute Center of Mass distance for each part side
            text = self.builder.build_text(name, right=True, offset_deg=float(cur_offset_deg))
            text_center = text.val().Center()  # type: ignore
            distance = (text_center - center).Length

            # Update the distance tracker
            if (distance < min_distance) and self.is_geometry_clear(text, other_tube):
                min_distance = distance
                offset_deg = cur_offset_deg

        # Update the text offset
        if not offset_deg is None:
            self.config.logo_text_positions[name] = (text_offset, float(offset_deg))  # type: ignore
            self.logger.print(f"angle offset for {name} text logo updated to {offset_deg}°", symbol="📐")

    def configure_clamps(self, names=None):
        """Perform clamp configuration.

        :param _type_ name: The name of the part.
        """
        if names is None:
            names = self.config.names
        for name in names:
            self.config_clamp(name)

    def configure_text_logos(self, names=None):
        """Perform text logo configuration.

        :param _type_ name: The name of the part.
        """
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
    config = AppConfig(_env_file=None)  # type: ignore
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
