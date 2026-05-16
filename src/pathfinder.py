"""Search for valid attractor points to balance manifold paths."""

import argparse
import json
import subprocess
from build import AppConfig, Builder, Logger
from config import Configurator
from pathlib import Path
import random


class Pathfinder:
    """Tries building a part with a random attractor point."""

    def __init__(self, logger=None):
        """Initialize the pathfinder."""
        self.logger = logger or Logger(text="Pathfinding...")
        self.config = AppConfig(_env_file=None)  # type: ignore
        self.builder = Builder(logger=logger, config=self.config)
        self.configurator = Configurator(logger=logger, builder=self.builder, config=self.config)
        self._bbox = None

    def clear_builder_cache(self):
        """Clear cached builder geometry that depends on attractors."""
        self.builder.create_wire.cache_clear()
        self.builder.build_tube.cache_clear()
        self.builder.build_clamp_bed.cache_clear()
        self.builder.create_logo_text_shape.cache_clear()
        self.builder.build_text.cache_clear()
        self.builder.build_clean_tool.cache_clear()
        self.builder.build_part.cache_clear()
        self.builder.build_prepared_part.cache_clear()

    def get_bounding_box(self):
        """Cache the static bounding box used for random point generation."""
        if self._bbox is None:
            self._bbox = self.builder.build_bound_box().val().BoundingBox()  # type: ignore
        return self._bbox

    def invoke_pytest(self):
        """Run pytest for validation and raise on failure."""
        self.logger.print("Invoking pytest...", symbol="🧪 ")
        result = subprocess.run(["pytest", "-qq", "-n", "auto", "-x", "--maxfail=1", "tests/"])
        exit_code = result.returncode
        if exit_code != 0:
            raise RuntimeError(f"Test suite failed with pytest exit code {exit_code}.")

    def get_point(self):
        """Generate a random point inside the bounding box."""
        bbox = self.get_bounding_box()
        x = round(random.uniform(bbox.xmin, bbox.xmax), 2)
        y = round(random.uniform(bbox.ymin, bbox.ymax), 2)
        z = round(random.uniform(bbox.zmin, bbox.zmax), 2)
        return (x, y, z)

    def try_points(self, name, points, out_dir):
        """Test a candidate attractor and log success if valid."""
        self.config.attractors[name] = points
        self.clear_builder_cache()
        try:
            self.logger.print(f"Trying {points} on {name}...", symbol="📍")
            self.configurator.configure_all(names=[name])
            self.builder.generate_parts(out_dir=str(out_dir), names=[name])
            self.invoke_pytest()
            return True
        except Exception as e:
            self.logger.print(f"Path failed: {str(e)}", symbol="❌")
            return False


def get_args():
    """Get parsed arguments for the program.

    :return _type_: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Pathfinder Experiment.")
    parser.add_argument("-o", "--outdir", default="out", help="Target directory for outputs")
    parser.add_argument("-n", "--num_iterations", default=1, type=int, help="Number of iterations")
    parser.add_argument("-p", "--num_points", default=2, type=int, help="Number of points")
    parser.add_argument(
        "-s",
        "--name",
        default="driver",
        help="The name to evaluate",
    )
    args = parser.parse_args()
    return args


def main(logger, args):
    """Initialize the build environment and perform build actions.

    :param _type_ args: The program arguments.
    """
    # Create the output directory
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = out_dir / "pathfinder_output.txt"

    pathfinder = Pathfinder()
    with open(log_file_path, "a", encoding="utf-8") as file:
        for _ in range(args.num_iterations):
            points = [pathfinder.get_point() for _ in range(args.num_points)]

            # Run our path evaluation and log the attractor if it works.
            if pathfinder.try_points(args.name, points, out_dir):
                json_line = json.dumps(pathfinder.config.model_dump(exclude_unset=True, by_alias=True))
                file.write(f"{json_line}\n")
                logger.print(f"Found path! Wrote to {str(log_file_path)}", symbol="✅")
    logger.done()


if __name__ == "__main__":
    """Program entry point.
    """
    logger = Logger(text="Pathfinding...")
    args = get_args()
    main(logger, args)
