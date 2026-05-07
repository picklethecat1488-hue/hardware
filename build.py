"""Contains the code to build exhaust manifolds."""

import argparse
import math
import numpy as np
import os
from pathlib import Path
import cadquery as cq
from functools import lru_cache
from itertools import combinations
from IPython import get_ipython
import zipfile


class Logger:
    """Provides a print-based logging interface for the Builder."""

    def __init__(self, text="Building...", enabled=True):
        """Initialize the logger.

        :param str text: Descriptive text of what is done, defaults to "Building..."
        :param bool enabled: True if logging is enabled, defaults to True
        """
        self.text = text
        self.backend = None
        self.in_notebook = Logger.in_notebook()
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

    def in_notebook():
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
                self.backend.start()
                self.running = True
            # Display the message, along with a custom symbol, while keeping the spinner going.
            self.backend.text = ""
            self.backend.stop_and_persist(f"{symbol} {msg}")
            self.backend.start()

    def done(self):
        """Indicate the operation has succeeded."""
        if not self.in_notebook:
            self.backend.text = f"Done {self.text}"
            self.backend.succeed()
            if self.running:
                # Stop the spinner after the operation has completed.
                self.backend.stop()
                self.running = False


class Builder:
    """The manifold builder creates the manifold objects and exports them as files for 3D printing."""

    def __init__(self, logger=None):
        """Initialize the builder."""
        self.project_name = "exhaust_manifolds"
        self.ver = 4
        # Wall thickness ~1.4mm
        self.wall_thickness = 1.4
        # Inlet diameter 2.5", outlet diameter is slightly bigger
        self.clamp_diameters = [63.5, 65]
        # Inlet and outlet clamp length 2"
        self.clamp_lengths = [50.4, 50.4]
        # Inlet and outlet clamp positions (-1) means offset by clamp length from the end
        self.clamp_positions = [0, -1]
        self.boolean_tolerance = 0.01
        # Normal axis and hinge axis for workspace locating
        self.norm_axis = cq.Vector(0, 0, 1)
        self.ref_axis = cq.Vector(0, 1, 0)
        self.logger = logger if logger else Logger(enabled=False)

        # Define the raw measurements taken here
        p = {
            # p[1] -> p[2] valve controller bottom plane
            1: np.array([443, 152, 521]),
            2: np.array([652, 205, 500]),
            # p[3] passenger exhaust input inlet start
            3: np.array([565, 356, 352]),
            # p[4] -> p[5] direction of driver exhaust input
            4: np.array([555, 327, 0]),
            5: np.array([480, 343, 0]),
            # p[6] driver exhaust input inlet start
            6: np.array([347, 279, 382]),
            # p[7] -> p[8] direction of driver exhaust output
            7: np.array([410, 350, 0]),
            8: np.array([392, 300, 0]),
            # p[9] driver exhaust output inlet start
            9: np.array([200, 0, 520]),
            # p[10] passenger exhaust output inlet start
            10: np.array([895, 0, 525]),
        }

        # Do some data correction here
        outlet_arrays = np.stack([p[9], p[10]])
        outlet_height = np.mean(outlet_arrays[:, 2])
        p[9][2] = p[10][2] = outlet_height

        vc_arrays = np.stack([p[1], p[2]])
        vc_depth, vc_height = np.mean(vc_arrays[:, 1]), np.mean(vc_arrays[:, 2])
        p[1][1] = p[2][1] = vc_depth
        p[1][2] = p[2][2] = vc_height

        for idx in [3, 6]:
            p[idx][2] = p[idx][2] - (self.clamp_diameters[0] / 2)
        for idx in [9, 10]:
            p[idx][2] = p[idx][2] - (self.clamp_diameters[-1] / 2)

        def dir_vector(start, end):
            """Generate a 3D direction vector for the given points, e.g. p[4] and p[5]."""
            return (end - start) / np.linalg.norm(end - start)

        theta = np.radians(15)
        c, s = np.cos(theta), np.sin(theta)
        R_driver_inlet = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])

        self.names = ["driver", "passenger"]

        self.P = {
            "driver_inlet": p[6],
            "driver_outlet": p[9],
            "passenger_inlet": p[3],
            "passenger_outlet": p[10],
        }

        self.V = {
            "driver_inlet": dir_vector(p[7], p[8]) @ R_driver_inlet,
            "driver_outlet": np.array([-1, 0, 0]),
            "passenger_inlet": dir_vector(p[5], p[4]),
            "passenger_outlet": np.array([1, 0, 0]),
        }

    def create_wire(self, name):
        """Create the wire.

        The wire defines the path around which the manifold is profiled.
        The wire connects the exhaust inlet and outlets across a 3D coordinate system.

        :param _type_ name: The name of the manifold
        :return _type_: The wire path
        """
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
        p_start, v_start, p_end, v_end = self.P[inlet_key], self.V[inlet_key], self.P[outlet_key], self.V[outlet_key]

        # Inlet start
        p1 = p_start
        # Inlet end
        p2 = p_start + v_start * self.clamp_lengths[0]
        # Outlet start
        p3 = p_end
        # Outlet end
        p4 = p_end + v_end * self.clamp_lengths[-1]
        wire = cq.Wire.assembleEdges(
            [
                cq.Edge.makeLine(cq.Vector(*p1), cq.Vector(*p2)),
                cq.Edge.makeSpline(
                    listOfVector=[cq.Vector(*p2), cq.Vector(*p3)],
                    tangents=(cq.Vector(*v_start), cq.Vector(*v_end)),
                    periodic=False,
                ),
                cq.Edge.makeLine(cq.Vector(*p3), cq.Vector(*p4)),
            ]
        )
        path = cq.Workplane("XY").add(wire)
        return path

    def create_profile(self, loc, radius, start_deg, end_deg):
        """Create a profile section using the given radius.

        :param _type_ path_obj: The wire path.
        :param _type_ off: The section offset from the path start.
        :param _type_ radius: The profile radius
        :param int start_deg: If building part of the manifold, the start angle of the tube half in degrees, defaults to 0
        :param int end_deg: If building part of the manifold, the end angle of the half in degrees, defaults to 360
        :return _type_: The profile section.
        """
        profile = cq.Workplane(loc).placeSketch(
            cq.Sketch().arc((0, 0), radius, start_deg, end_deg - start_deg).segment((0, 0)).close().assemble()
        )
        return profile

    def get_clamp_offsets(self, length):
        """Get array of clamp start positions.

        :param _type_ length: The wire length.
        """
        offsets = (
            np.array(
                [
                    (length - clamp_length) if (clamp_position == -1) else clamp_position
                    for clamp_position, clamp_length in zip(self.clamp_positions, self.clamp_lengths)
                ]
            )
            / length
        )
        return offsets

    def create_tube(self, path, radii, start_deg, end_deg):
        """Create a tube shape for the given part.

        :param _type_ path: The path to use
        :param int radii: The tube radii in mm
        :param int start_deg: The start angle of the tube in degrees
        :param int end_deg: The end angle of the tube in degrees
        :return _type_: The exhaust manifold
        """
        length = path.val().Length()
        start_offsets = self.get_clamp_offsets(length)
        end_offsets = np.array(start_offsets) + np.array(self.clamp_lengths) / length
        sections = []
        for start_off, end_off, cur_radius in zip(start_offsets, end_offsets, radii):
            sections.extend(
                [
                    self.create_profile(path.val().locationAt(start_off), cur_radius, start_deg, end_deg).val(),
                    self.create_profile(path.val().locationAt(end_off), cur_radius, start_deg, end_deg).val(),
                ]
            )
        tube = (
            cq.Workplane(path.val().locationAt(0))
            .add(sections[0])
            .sweep(path, transition="round", multisection=True, sweepAlongWires=sections[1:])
        )
        return tube

    @lru_cache
    def build_tube(self, name, start_deg=0, end_deg=360):
        """Build an exhaust tube.

        :param _type_ name: The name of the manifold to build
        :param int start_deg: If building part of the manifold, the start angle of the tube half in degrees, defaults to 0
        :param int end_deg: If building part of the manifold, the end angle of the half in degrees, defaults to 360
        :return _type_: The exhaust manifold
        """
        # Create the tube using boolean operations
        path = self.create_wire(name)
        radii = np.array(self.clamp_diameters) / 2
        tube = self.create_tube(path, radii, 0, 360).cut(
            self.create_tube(path, radii - self.wall_thickness, 0, 360),
            tol=self.boolean_tolerance,
        )
        tube = tube.intersect(self.create_tube(path, radii, start_deg, end_deg), tol=self.boolean_tolerance)
        return tube

    @lru_cache
    def build_part(self, name, right=False):
        """Build the left or right half of the manifold.

        :param _type_ name: The name of the manifold
        :param bool right: True if building the right half, defaults to False
        :param _type_ offset_deg: The rotational start offset in degrees, default to -90
        :return _type_: The manifold half
        """
        if name == "driver" or name == "passenger":
            # Create the 3D printable tube part
            part = (
                self.build_tube(name, start_deg=0, end_deg=180)
                if right
                else self.build_tube(name, start_deg=180, end_deg=360)
            )
        else:
            raise ValueError(f"Invalid name: {name}")
        return part

    @lru_cache
    def build_back_manifold(self, name):
        """Build back the manifold shape from parts.

        :param _type_ name: The name of the manifold
        :return _type_: A tuple containing the exhaust manifiold, and the manifold built from parts
        """
        if name != "driver" and name != "passenger":
            raise ValueError(f"Invalid name: {name}")
        left_part, right_part = self.build_part(name), self.build_part(name, right=True)
        manifold = self.build_tube(name)
        manifold_from_parts = left_part.union(right_part, tol=self.boolean_tolerance)
        return manifold, manifold_from_parts

    @lru_cache
    def calc_part_error(self, name):
        """Calculate the build error for parts.

        This method provides a percentage index which can be used in testing.

        :param _type_ name: The name of the manifold
        :return _type_: A percentage indicating the part error when attempting to assemble the manifold from parts
        """
        if name != "driver" and name != "passenger":
            raise ValueError(f"Invalid name: {name}")
        manifold, manifold_from_parts = self.build_back_manifold(name)
        manifold_vol, manifold_from_parts_vol = (
            manifold.val().Volume(),
            manifold_from_parts.val().Volume(),
        )
        error_pct = abs(manifold_vol - manifold_from_parts_vol) / (manifold_vol + manifold_from_parts_vol) / 2 * 100
        return error_pct

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
            diff = part.val().Center() - full_part.val().Center()
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
        file_prefix = f"{self.project_name}_v{self.ver}"

        if names is None:
            names = self.names
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
            names = self.names
        if right_vals is None:
            right_vals = [False, True]

        diagram_name = f"{self.project_name}_v{self.ver}_diagram.svg"
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
                    off = wire_obj.positionAt(0.5)
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
        self.generate_diagram(names=self.names, out_dir=out_dir, right_vals=right_vals)
        self.generate_parts(names=self.names, out_dir=out_dir, right_vals=right_vals)

        # Compress the build
        zip_file_str = str(Path(out_dir) / zip_name)
        zip_build(zip_file_str)
        self.logger.print(f"Done writing {zip_file_str}", symbol="📦")


def get_args():
    """Get parsed arguments for the program.

    :return _type_: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Build Utility.")
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
