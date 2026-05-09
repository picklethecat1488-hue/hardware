"""Contains the code to build exhaust manifolds."""

import argparse
import math
import numpy as np
import os
from pathlib import Path
import cadquery as cq
from functools import lru_cache
from IPython.core.getipython import get_ipython
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import zipfile


class AppConfig(BaseSettings):
    """Builder app configuration.

    :param _type_ BaseSettings: The base settings for the builder.
    """

    # Project name
    project_name: str = "exhaust_manifolds"

    # Build version
    ver: int = 4

    # The part x boundaries
    x_bounds: list[float] = [145, 950]

    # The part y boundaries
    y_bounds: list[float] = [-32, 390]

    # The part bounds
    z_bounds: list[float] = [145, 530]

    # Wall thickness ~1.4mm
    wall_thickness: float = 1.4

    # Inlet and outlet diameters, 2.5"
    outer_diameter: float = 63.5

    # Inner clamp diameter 3"
    clamp_diameter: float = 76.2

    # Inlet and outlet clamp length 2", inner clamp length 1"
    clamp_lengths: list[float] = [50.4, 25.4, 50.4]

    # The minimum space between each clanp bed
    clamp_space: float = 10

    # Applying a 0.5mm fillet/chamfer to all objects.
    edge_rounding: float = 0.5

    # The part names, driver and passenger
    names: list[str] = ["driver", "passenger"]

    model_config = SettingsConfigDict(env_file=".env")

    def get_measurements(self):
        """Get the raw measurements used for the project.

        :return _type_: The raw measurement points.
        """
        # Define the raw measurements taken here
        p = {
            # p[1] -> p[2] valve controller bottom plane
            1: np.array([443, 152, 521]),
            2: np.array([652, 205, 500]),
            # p[3] passenger exhaust input inlet start
            3: np.array([565, 356, 352]),
            # p[4] -> p[5] direction of passenger exhaust input
            4: np.array([555, 327, 0]),
            5: np.array([480, 343, 0]),
            # p[6] driver exhaust input inlet start
            6: np.array([347, 279, 382]),
            # p[7] -> p[8] direction of driver exhaust input
            7: np.array([410, 350, 0]),
            8: np.array([392, 300, 0]),
            # p[9] driver exhaust output inlet start
            9: np.array([200, 0, 520]),
            # p[10] passenger exhaust output inlet start
            10: np.array([895, 0, 525]),
        }
        return p

    def get_p_v(self):
        """Return the P and V dictionaries for the environment.

        The P and V dictionaries define inlet and outlet points and directions for each model.

        :return _type_: The P and V vectors
        """
        p = self.get_measurements()

        # Do some data correction here
        outlet_arrays = np.stack([p[9], p[10]])
        outlet_height = np.mean(outlet_arrays[:, 2])
        p[9][2] = p[10][2] = outlet_height

        vc_arrays = np.stack([p[1], p[2]])
        vc_depth, vc_height = np.mean(vc_arrays[:, 1]), np.mean(vc_arrays[:, 2])
        p[1][1] = p[2][1] = vc_depth
        p[1][2] = p[2][2] = vc_height

        for idx in [3, 6, 9, 10]:
            p[idx][2] = p[idx][2] - (self.outer_diameter / 2)

        def dir_vector(start, end):
            """Generate a 3D direction vector for the given points, e.g. p[4] and p[5]."""
            return (end - start) / np.linalg.norm(end - start)

        theta = np.radians(15)
        c, s = np.cos(theta), np.sin(theta)
        R_driver_inlet = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])

        P = {
            "driver_inlet": p[6],
            "driver_outlet": p[9],
            "passenger_inlet": p[3],
            "passenger_outlet": p[10],
        }

        V = {
            "driver_inlet": dir_vector(p[7], p[8]) @ R_driver_inlet,
            "driver_outlet": np.array([-1, 0, 0]),
            "passenger_inlet": dir_vector(p[5], p[4]),
            "passenger_outlet": np.array([1, 0, 0]),
        }

        return P, V

    def get_bounds(self):
        """Return the application bounds.

        The bounds are an Axis Aligned Boundary Box representing the valid space parts may occupy.

        :return _type_: The bounding box.
        """
        # Create the overall bounds.
        x_len = np.max(self.x_bounds) - np.min(self.x_bounds)
        y_len = np.max(self.y_bounds) - np.min(self.y_bounds)
        z_len = np.max(self.z_bounds) - np.min(self.z_bounds)
        center = (
            np.min(self.x_bounds) + x_len / 2,
            np.min(self.y_bounds) + y_len / 2,
            np.min(self.z_bounds) + z_len / 2,
        )
        bounds = cq.Workplane("XY").box(x_len, y_len, z_len).translate(center)

        # Subtract the valve controller bottom plane from the overall bounds.
        p = self.get_measurements()
        x_len = p[2][0] - p[1][0]
        y_len = np.max(self.y_bounds) - np.mean([p[2][1], p[1][1]])
        z_len = np.max(self.z_bounds) - np.mean([p[2][2], p[1][2]])
        center = (
            np.min([p[2][0], p[1][0]]) + x_len / 2,
            np.min([p[2][1], p[1][1]]) + y_len / 2,
            np.min([p[2][2], p[1][2]]) + z_len / 2,
        )
        top_plane = cq.Workplane("XY").box(x_len, y_len, z_len).translate(center)
        bounds = bounds.cut(top_plane)
        return bounds


class Logger:
    """Provides a print-based logging interface for the Builder."""

    def __init__(self, text="Building...", enabled=True):
        """Initialize the logger.

        :param str text: Descriptive text of what is done, defaults to "Building..."
        :param bool enabled: True if logging is enabled, defaults to True
        """
        self.text = text
        self.backend = None
        self.in_notebook = self.get_in_notebook()
        self.enabled = enabled

        if self.enabled:
            if self.in_notebook:
                from html_sanitizer import Sanitizer
                import ipywidgets as widgets
                from IPython.display import display

                self.sanitizer = Sanitizer()
                sanitized_text = self.sanitizer.sanitize(self.text)
                self.backend = widgets.HTML(value=f"⏳ <b>{sanitized_text}</b>")
                display(self.backend)
            else:
                from halo import Halo

                self.backend = Halo(text=self.text, spinner="dots", interval=33)
                self.backend.start()
                self.running = True

    def get_in_notebook(self):
        """Check if we are inside a notebook.

        :return _type_: True if inside a notebook, else false.
        """
        try:
            shell = get_ipython().__class__.__name__
            return shell == "ZMQInteractiveShell"
        except NameError:
            return False

    def print(self, msg, symbol="▶"):
        """Print a log message.

        :param _type_ msg: The message to print.
        """
        if not self.enabled:
            print(msg)
        elif self.in_notebook:
            import ipywidgets as widgets
            from IPython.display import display

            sanitized_symbol = self.sanitizer.sanitize(symbol)
            sanitized_text = self.sanitizer.sanitize(msg)
            self.backend = widgets.HTML(value=f"{sanitized_symbol} <pre>{sanitized_text}</pre>")
            display(self.backend)
        else:
            if not self.running:
                # Start the spinner, if not already running.
                self.backend.start()  # type: ignore
                self.running = True
            # Display the message, along with a custom symbol, while keeping the spinner going.
            self.backend.text = ""  # type: ignore
            self.backend.stop_and_persist(f"{symbol} {msg}")  # type: ignore
            self.backend.start()  # type: ignore

    def done(self):
        """Indicate the operation has succeeded."""
        if not self.in_notebook:
            self.backend.text = f"Done {self.text}"  # type: ignore
            self.backend.succeed()  # type: ignore
            if self.running:
                # Stop the spinner after the operation has completed.
                self.backend.stop()  # type: ignore
                self.running = False


class Builder:
    """The manifold builder creates the manifold objects and exports them as files for 3D printing."""

    def __init__(self, config=None, logger=None):
        """Initialize the builder."""
        self.config = config or AppConfig()
        self.logger = logger or Logger(enabled=False)
        self.P, self.V = self.config.get_p_v()

    @lru_cache
    def create_wire(self, name):
        """Create the wire.

        The wire defines the path around which the manifold is profiled.
        The wire connects the exhaust inlet and outlets across a 3D coordinate system.

        :param _type_ name: The name of the manifold
        :return _type_: The wire path
        """
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
        inlet_start, v_start, outlet_start, v_end = (
            self.P[inlet_key],
            self.V[inlet_key],
            self.P[outlet_key],
            self.V[outlet_key],
        )
        inlet_end = inlet_start + v_start * self.config.clamp_lengths[0]
        outlet_end = outlet_start + v_end * self.config.clamp_lengths[-1]

        wire = cq.Wire.assembleEdges(
            [
                cq.Edge.makeLine(cq.Vector(*inlet_start), cq.Vector(*inlet_end)),
                cq.Edge.makeSpline(
                    listOfVector=[cq.Vector(*inlet_end), cq.Vector(*outlet_start)],
                    tangents=(cq.Vector(*v_start), cq.Vector(*v_end)),
                    periodic=False,
                ),
                cq.Edge.makeLine(cq.Vector(*outlet_start), cq.Vector(*outlet_end)),
            ]
        )
        path = cq.Workplane("XY").add(wire)
        return path

    def create_profile(self, loc, start_deg, end_deg, outer_radius=None, inner_radius=None):
        """Create a profile section using the given radius.

        :param _type_ path_obj: The wire path.
        :param _type_ off: The section offset from the path start.
        :param int start_deg: If building part of the manifold, the start angle of the tube half in degrees, defaults to 0
        :param int end_deg: If building part of the manifold, the end angle of the half in degrees, defaults to 360
        :param int outer_radius: The optional outer radius of the profile.
        :param int inner_radius: The optional inner radius of the profile.
        :return _type_: The profile section.
        """
        if outer_radius is None:
            outer_radius = self.config.outer_diameter / 2
        if inner_radius is None:
            inner_radius = outer_radius - self.config.wall_thickness
        if inner_radius >= outer_radius:
            raise ValueError("Invalid radius or inner radius")
        sketch = (
            cq.Sketch()
            .arc((0, 0), outer_radius, start_deg, end_deg - start_deg)
            .segment((0, 0))
            .close()
            .assemble()
            .circle(outer_radius, mode="i")
        )
        if inner_radius > 0:
            # Subtract the center to make it hollow
            sketch = sketch.circle(inner_radius, mode="s")
        sketch = sketch.clean()
        profile = cq.Workplane(loc).placeSketch(sketch)
        return profile

    @lru_cache
    def build_tube(self, name, start_deg: float = 0, end_deg: float = 360):
        """Build an exhaust tube.

        :param _type_ name: The name of the manifold to build
        :param int start_deg: If building part of the manifold, the start angle of the tube half in degrees, defaults to 0
        :param int end_deg: If building part of the manifold, the end angle of the half in degrees, defaults to 360
        :return _type_: The exhaust manifold
        """
        path = self.create_wire(name)
        loc = path.val().locationAt(0)  # type: ignore
        profile = self.create_profile(loc, start_deg, end_deg)
        tube = (
            cq.Workplane(loc)
            .placeSketch(profile.val())  # type: ignore
            .sweep(path, transition="round")
            .fillet(self.config.edge_rounding)
        )
        return tube

    def create_ring(
        self, path, off, len, inner_radius=None, outer_radius=None, start_deg: float = 0, end_deg: float = 360
    ):
        """Create a ring at a given offset.

        :param _type_ path: The ring path
        :param _type_ path: The path offset
        :param _type_ len: The ring length
        :param _type_ inner_radius: The inner radius.
        :param _type_ outer_radius: The outer radius.
        :param _type_ start_deg: The start angle.
        :param _type_ end_deg: The end angle.
        :return _type_: The ring
        """
        loc = path.val().locationAt(off)
        tan = path.val().tangentAt(off)
        profile = self.create_profile(
            loc,
            start_deg,
            end_deg,
            outer_radius=outer_radius,
            inner_radius=inner_radius,
        )
        p1 = path.val().positionAt(off)
        p2 = p1 + (tan * len)
        path = cq.Workplane(loc).polyline([p1, p2])
        ring = cq.Workplane(loc).placeSketch(profile.val()).sweep(path)  # type: ignore
        return ring

    @lru_cache
    def build_clamp_bed(self, name, off, clamp_space=None, start_deg: float = 0, end_deg: float = 360):
        """Build a clamp bed.

        :param _type_ name: The part name to build.
        :param _type_ off: The tube offset to build the clamp bed
        :param int start_deg: If building part of the manifold, the start angle of the tube half in degrees, defaults to 0
        :param int end_deg: If building part of the manifold, the end angle of the half in degrees, defaults to 360
        :return _type_: The clamp bed
        """

        def clean_tube(path, bed, inner_radius):
            """Clean up the tube after adding the clamp bed.

            :param _type_ path: The tube path
            :param _type_ bed: The clamp bed
            :param _type_ inner_radius: The inner radius.
            :return _type_: The clamp bed.
            """
            # Cut the empty volume of tube out of the clamp bed
            loc = path.val().locationAt(off)
            profile = self.create_profile(loc, 0, 360, outer_radius=inner_radius)
            tube = cq.Workplane(loc).placeSketch(profile.val()).sweep(path, transition="round")  # type: ignore
            bed = bed.cut(tube)
            return bed

        if clamp_space is None:
            clamp_space = self.config.clamp_space

        path = self.create_wire(name)
        length = self.config.clamp_lengths[1]
        outer_radius = self.config.clamp_diameter / 2
        inner_radius = (self.config.outer_diameter - self.config.wall_thickness) / 2
        space_sign = 1 if start_deg < end_deg else -1
        space_deg = space_sign * clamp_space / 2
        start_deg, end_deg = start_deg + space_deg, end_deg - space_deg

        # Create the clamp bed out of multiple ring profiles
        top = self.create_ring(
            path,
            off,
            length,
            inner_radius=outer_radius - self.config.wall_thickness,
            outer_radius=outer_radius,
            start_deg=start_deg,
            end_deg=end_deg,
        )
        base = self.create_ring(
            path,
            off,
            length - self.config.wall_thickness,
            inner_radius=inner_radius,
            outer_radius=outer_radius - self.config.wall_thickness,
            start_deg=start_deg,
            end_deg=end_deg,
        ).cut(
            self.create_ring(
                path,
                off,
                self.config.wall_thickness,
                inner_radius=inner_radius,
                outer_radius=outer_radius - self.config.wall_thickness,
                start_deg=start_deg,
                end_deg=end_deg,
            ),
        )
        bed = top.union(base).fillet(self.config.edge_rounding)

        # Cut the empty volume of tube out of the clamp bed
        return clean_tube(path, bed, inner_radius)

    @lru_cache
    def build_part(self, name, right=False):
        """Build the left or right half of the manifold.

        :param _type_ name: The name of the manifold
        :param bool right: True if building the right half, defaults to False
        :return _type_: The manifold half
        """
        if name == "driver" or name == "passenger":
            # Create the main part body.
            build_args = {"start_deg": (0 if right else 180), "end_deg": (180 if right else 360)}
            part = self.build_tube(name, **build_args)
            if len(self.config.clamp_lengths) > 2:
                # Add the clamp bed
                clamp_bed = self.build_clamp_bed(name, 0.5, **build_args)
                part = part.union(clamp_bed)
        else:
            raise ValueError(f"Invalid name: {name}")
        return part

    @lru_cache
    def build_prepared_part(self, name, right=False):
        """Build the part and prepare it for export to STL.

        :param _type_ name: The name of the manifold
        :param bool right: True if building the right half, defaults to False
        """

        def facing_up(part):
            """Determine if the part is facing up.

            Uses Center of Mass method. Can only be called prior to rotating or translating the part.

            :return _type_: True if facing up, otherwise False
            """
            if name == "driver" or name == "passenger":
                full_part = self.build_tube(name)
            else:
                raise ValueError(f"Invalid name: {name}")
            diff = part.val().Center() - full_part.val().Center()  # type: ignore
            normal = diff.normalized()
            return normal.z > 0

        def rotation(part):
            """Determine the flattening rotation to perform on the part.

            :param _type_ part: The part to rotate.
            :return _type_: The rotation to perform.
            """
            # Find the path edge, then extract the first and last points from it
            path = sorted(part.edges(), key=lambda e: e.Length())[-1]
            p1, p2 = path.startPoint(), path.endPoint()
            diff = p2 - p1

            # Compute the tilt axis and angle
            axis = (-diff.y, diff.x, 0)
            horizontal_dist = math.sqrt(diff.x**2 + diff.y**2)
            angle_deg = math.degrees(math.atan2(diff.z, horizontal_dist))
            return axis, angle_deg

        def translation(part):
            """Determine the flattening translation to perform on the part.

            :param _type_ part: The part to translate.
            :return _type_: The translation to perform.
            """
            return (0, 0, -part.val().BoundingBox().zmin)

        # Ensure the part is facing up on the print bed in a way that is optimal for 3D printing
        part = self.build_part(name, right=right)
        if not facing_up(part):
            part = part.mirror("XY")
        axis, angle_deg = rotation(part)
        part = part.rotate((0, 0, 0), axis, angle_deg)
        part = part.translate(translation(part))
        return part.clean()

    def generate_parts(self, out_dir, names=None, right_vals=None):
        """Generate STL parts files for assembly.

        :param _type_ out_dir: The output directory.
        :param _type_ names: The optional names to generate.
        :param _type_ right_vals: The optional right values to use.
        """
        file_prefix = f"{self.config.project_name}_v{self.config.ver}"

        if names is None:
            names = self.config.names
        if right_vals is None:
            right_vals = [False, True]

        for name in names:
            for right in right_vals:
                side = "right" if right else "left"
                mesh_file_name = f"{file_prefix}_{name}_{side}.stl"
                prepared_part = self.build_prepared_part(name, right=right)
                path_str = str(Path(out_dir) / mesh_file_name)
                cq.exporters.export(prepared_part, path_str)
                self.logger.print(f"Saved {path_str}", symbol="📄")

    def generate_diagram(self, out_dir, names=None, right_vals=None):
        """Generate a diagram for the given part names.

        :param _type_ out_dir: The output directory.
        :param _type_ names: The optional names to generate.
        """

        def get_part_location(wire_obj, offset=0, dist=0, right=False):
            """Return the part location for the part in the exploded diagram.

            :param _type_ wire_obj: The wire object
            :param bool right: Right if True, defaults to False
            :return _type_: The part location in the exploded diagram
            """
            part_dist = dist if right else 0
            part_offset = offset + part_dist
            dir = wire_obj.tangentAt(0)
            loc = cq.Vector(dir) * part_dist + cq.Vector(0, 1, 0) * part_offset
            return loc

        if names is None:
            names = self.config.names
        if right_vals is None:
            right_vals = [False, True]

        diagram_name = f"{self.config.project_name}_v{self.config.ver}_diagram.svg"
        svg_opt = {
            "showAxes": False,
            "strokeWidth": 3,
            "strokeColor": (0, 0, 0),
            "projectionDir": (1, 1, 1),
            "width": 1024,
            "height": 1024,
        }
        part_offset, part_dist = 60, 120
        assy = cq.Assembly()
        wire_objs = [self.create_wire(name).val() for name in names]

        for i, wire_obj in enumerate(wire_objs):
            for right in right_vals:
                loc = get_part_location(wire_obj, right=right, offset=(i * part_offset), dist=part_dist)
                other_loc = get_part_location(wire_obj, right=(not right), offset=(i * part_offset), dist=part_dist)

                # Add parts to the diagram
                part = self.build_part(names[i], right=right)
                assy.add(part.translate(loc))

                # Connect parts to each other
                if right:
                    off = wire_obj.positionAt(0.5)  # type: ignore
                    line = cq.Workplane("XY").polyline([loc + off, other_loc + off])
                    assy.add(line)

        # Save the tech diagram
        path_str = str(Path(out_dir) / diagram_name)
        assy.toCompound().export(path_str, opt=svg_opt)
        self.logger.print(f"Saved {path_str}", symbol="📄")

    def generate_all(self, out_dir, right_vals=None, zip_name="build.zip"):
        """Generate all project files.

        :param str out_dir: The output directory generate all files in, defaults to "build"
        :param str zip_name: The name of the zip file containing all outputs, defaults to "build.zip"
        """

        def zip_build(zip_file_str):
            """Zip the build output.

            :param _type_ zip_file_str: The path to the ZIP file to write
            """
            with zipfile.ZipFile(zip_file_str, "w", zipfile.ZIP_DEFLATED) as zipf:
                for _, _, files in os.walk(out_dir):
                    for file in files:
                        file_str = str(Path(out_dir) / file)
                        if not os.path.samefile(zip_file_str, file_str):
                            zipf.write(file_str, file)

        # Export the diagram and files
        self.generate_diagram(names=self.config.names, out_dir=out_dir, right_vals=right_vals)
        self.generate_parts(names=self.config.names, out_dir=out_dir, right_vals=right_vals)

        # Compress the build
        zip_file_str = str(Path(out_dir) / zip_name)
        zip_build(zip_file_str)
        self.logger.print(f"Done writing {zip_file_str}", symbol="📦")


def get_args():
    """Get parsed arguments for the program.

    :return _type_: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Build Utility.")
    parser.add_argument("-e", "--env", required=False, default=None, help="Output environment to file.")

    parser.add_argument("-out", "--outdir", default="build", help="Target directory for outputs")

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-d", "--diagram", nargs="?", const=True, help="Generate diagram. Optional: provide a name.")
    group.add_argument(
        "-o",
        "--output",
        nargs="+",
        metavar=("NAME", "SIDE"),
        help="Generate a file and exit. Usage: -o <name> [<side>]",
    )

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-l", "--left", action="store_true", help="Write left side only")
    group.add_argument("-r", "--right", action="store_true", help="Write right side only")

    args = parser.parse_args()
    return args


def main(logger, args):
    """Initialize the build environment and perform build actions.

    :param _type_ args: The program arguments.
    """
    # Generate optional arguments
    gen_args = {}
    if args.outdir:
        gen_args["out_dir"] = args.outdir
    if args.left:
        gen_args["right_vals"] = [False]
    elif args.right:
        gen_args["right_vals"] = [True]

    # Create the output directory
    path = Path(args.outdir)
    path.mkdir(parents=True, exist_ok=True)

    builder = Builder(logger=logger)

    if not args.env is None:
        with open(args.env, "w") as f:
            for key, value in builder.config.model_dump().items():
                f.write(f"{key}={value}\n")
        logger.print(f"Saved environment to {args.env}", symbol="⚙️ ")

    if not args.diagram is None:
        if not args.diagram is True:
            gen_args["names"] = [args.diagram]
        builder.generate_diagram(**gen_args)
    elif not args.output is None:
        if args.output[0]:
            gen_args["names"] = [args.output[0]]
        builder.generate_parts(**gen_args)
    else:
        builder.generate_all(**gen_args)
    logger.done()


if __name__ == "__main__":
    """Program entry point.
    """
    logger = Logger()
    args = get_args()
    main(logger, args)
