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
        self.thickness = 3
        self.outer_diameter = 63.5
        self.inner_diameter = self.outer_diameter - self.thickness  # 60mm
        self.clamp_len = 50.4  # 2 inches
        self.edge_rounding = 0.5
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

        for idx in [3, 6, 9, 10]:
            p[idx][2] = p[idx][2] - (self.outer_diameter / 2)

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

    @lru_cache
    def build_wire(self, name, trim_start=0, trim_end=0):
        """Build the wire.

        The wire defines the path around which the manifold is profiled.
        The wire connects the exhaust inlet and outlets across a 3D coordinate system.

        :param _type_ name: The name of the manifold
        :param int trim_start: How much to trim from the start of the wire in mm, defaults to 0
        :param int trim_end: How much to trim from the end of the wire in mm, defaults to 0
        """

        def create_wire(p_start, v_start, p_end, v_end):
            """Create the wire based on the input and output path.

            :param _type_ p_start: The inlet endpoint
            :param _type_ v_start: The inlet direction
            :param _type_ p_end: The outlet endpoint
            :param _type_ v_end: The output direction
            :return _type_: A tuple containing the wire path information
            """
            p1 = p_start  # Manifold start
            p2 = p_start + v_start * self.clamp_len  # Spline start
            p3 = p_end  # Spline end
            p4 = p_end + v_end * self.clamp_len  # Manifold end
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
            return path, path.val()

        def trim_wire(path_obj, start, end):
            """Trim the wire.

            :param _type_ path: The wire assembly
            :param _type_ path_obj: The underlying wire object
            :param _type_ start: The start offset in mm
            :param _type_ end: The end offset in mm
            :return _type_: The trimmed wire
            """
            s, e = path_obj.positionAt(start), path_obj.positionAt(end)
            dx, dy, dz = (abs(s.x - e.x), abs(s.y - e.y), abs(s.z - e.z))
            cx, cy, cz = (
                (s.x + e.x) / 2.0,
                (s.y + e.y) / 2.0,
                (s.z + e.z) / 2.0,
            )

            # Create a trim box to remove unwanted portions of the wire
            clip_region = cq.Workplane("XY").center(cx, cy).workplane(offset=cz).box(dx, dy, dz)
            wires = path_obj.intersect(clip_region.val()).Wires()

            # Extract a trimmed path from the compound created by trimming the wire
            if len(wires) != 1:
                raise ValueError("Trim failed")
            path = cq.Workplane("XY").add(wires[0])
            return path, path.val()

        # Create the wire which defines the manifold shape
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
        path, path_obj = create_wire(self.P[inlet_key], self.V[inlet_key], self.P[outlet_key], self.V[outlet_key])

        # Apply wire trimming if needed
        if (trim_start > 0) or (trim_end > 0):
            length = path_obj.Length()
            s = trim_start / length
            e = (length - trim_end) / length
            path, path_obj = trim_wire(path_obj, s, e)
        return path, path_obj

    @lru_cache
    def build_manifold(
        self,
        name,
        start_deg=0,
        end_deg=0,
        trim_start=0,
        trim_end=0,
        **kwargs,
    ):
        """Build the exhaust manifold shape.

        :param _type_ name: The name of the manifold to build
        :param int start_deg: If building part of the manifold, the start angle of the tube offset to include in degrees, defaults to 0
        :param int end_deg: If building part of the manifold, the end angle of the tube offset to include in degrees, defaults to 0
        :param int trim_start: If building part of the manifold, how much to trim from the start in mm, defaults to 0
        :param int trim_end: If building part of the manifold, how much to trim from the end in mm, defaults to 0
        :return _type_: The exhaust manifold
        """
        path, path_obj = self.build_wire(name, trim_start=trim_start, trim_end=trim_end)
        start_point, start_tangent = path_obj.positionAt(0), path_obj.tangentAt(0)
        inner_radius = kwargs.pop("inner_radius", self.inner_diameter / 2)
        outer_radius = kwargs.pop("outer_radius", self.outer_diameter / 2)

        if (start_deg != 0) or (end_deg != 0):
            # We might want to cut a portion of the circle to use in building only part of the tube profile
            circle = cq.Sketch().circle(outer_radius).circle(inner_radius, "s")
            pie_slice = (
                cq.Sketch().arc((0, 0), outer_radius, start_deg, end_deg - start_deg).segment((0, 0)).close().assemble()
            )
            # Make the sides of the tube more rounded
            profile = (circle * pie_slice).vertices()
            tube = (
                cq.Workplane(cq.Plane(origin=start_point, normal=start_tangent))
                .placeSketch(profile)
                .sweep(path, transition="round")
            )

        else:
            # Create our hollow tube profile instead
            tube = (
                cq.Workplane(cq.Plane(origin=start_point, normal=start_tangent))
                .circle(outer_radius)
                .circle(inner_radius)
                .sweep(path, transition="round")
            )
        # Round the ends of the tube
        if self.edge_rounding > 0:

            def wrap_fillet(part):
                """Fillet every edge that can possibly be filleted.

                :param _type_ part: The part to fillet.
                :return _type_: A filleted part.
                """
                all_edges = part.vals()

                for edge in all_edges:
                    try:
                        new_part = part.newObject([edge]).fillet(self.edge_rounding)
                        part = new_part
                    except Exception as _:
                        continue

                return part

            # Micro fillet the tube first to generate new edge geometry, then perform a full fillet.
            tube = wrap_fillet(tube)
        return tube

    @lru_cache
    def build_manifold_half(self, name, right=False):
        """Build the left or right half of the manifold.

        :param _type_ name: The name of the manifold
        :param bool right: True if building the right half, defaults to False
        :return _type_: The manifold half
        """
        return (
            self.build_manifold(name, start_deg=180, end_deg=360) if right else self.build_manifold(name, end_deg=180)
        )

    @lru_cache
    def build_guide(self, name, right=False, guide_range=(-2, 4), guide_space=0.1):
        """Build the right or left manifold guide.

        The guide helps align the parts to each other as well as reduce material deformation.

        :param _type_ name: The name of the manifold
        :param bool right: True if building the right half, defaults to False
        :param _type_ guide_range Determine the start and end offsets of the guide
        :param _type_ guide_space How much space between the guide and the other part (in mm)
        :return _type_: The manifold guide
        """

        def get_build_manifold_args(right):
            """Get the list of manifolds to add and cut for the given part.

            :param _type_ right: True if building the right hand part, otherwise false
            :return _type_: An array of arguments to build_manifold
            """
            guide_start, guide_end = guide_range
            if guide_start > 0 or guide_end < 0:
                raise ValueError("Invalid guide range")
            angle = 0 if right else 180
            args = [
                {
                    "inner_radius": (self.outer_diameter - guide_space) / 2,
                    "outer_radius": (self.outer_diameter + self.thickness + guide_space) / 2,
                    "start_deg": angle + guide_start,
                    "end_deg": angle,
                    "trim_start": self.clamp_len,
                    "trim_end": self.clamp_len,
                },
                {
                    "inner_radius": (self.outer_diameter + guide_space) / 2,
                    "outer_radius": (self.outer_diameter + self.thickness + guide_space) / 2,
                    "start_deg": angle + guide_start,
                    "end_deg": angle + guide_end,
                    "trim_start": self.clamp_len,
                    "trim_end": self.clamp_len,
                },
            ]
            return args

        args = get_build_manifold_args(right=right)

        # Constuct guides and remove any extra space from them
        adds = [self.build_manifold(name, **arg) for arg in args]
        guide = adds[0]
        for add in adds[1:]:
            guide = guide.union(add)
        return guide

    @lru_cache
    def build_part(self, name, right=False):
        """Build a 3D printable manifold part.

        :param _type_ name: The name of the manifold
        :param bool right: True if building the right half, defaults to False
        :return _type_: The manifold part
        """
        part = self.build_manifold_half(name, right=right).union(self.build_guide(name, right=right))
        return part

    @lru_cache
    def build_back_manifold(self, name):
        """Build back the manifold shape from parts.

        :param _type_ name: The name of the manifold
        :return _type_: A tuple containing the exhaust manifiold, and the manifold built from parts
        """
        left_guide, right_guide = (
            self.build_guide(name),
            self.build_guide(name, right=True),
        )
        left_part, right_part = self.build_part(name), self.build_part(name, right=True)
        manifold = self.build_manifold(name)
        manifold_from_parts = left_part.union(right_part).cut(left_guide).cut(right_guide)
        return manifold, manifold_from_parts

    @lru_cache
    def calc_part_error(self, name):
        """Calculate the build error for parts.

        This method provides a percentage index which can be used in testing.

        :param _type_ name: The name of the manifold
        :return _type_: A percentage indicating the part error when attempting to assemble the manifold from parts
        """
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
            manifold = self.build_manifold(name)
            diff = part.val().Center() - manifold.val().Center()
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

    def generate_parts(self, out_dir, names=None):
        """Generate STL parts files for assembly.

        :param _type_ out_dir: The output directory.
        :param _type_ names: The optional names to generate.
        """
        file_prefix = f"{self.project_name}_v{self.ver}"

        if names is None:
            names = self.names

        for name in names:
            for right in [False, True]:
                side = "right" if right else "left"
                mesh_file_name = f"{file_prefix}_{name}_{side}.stl"
                prepared_part = self.build_prepared_part(name, right=right)
                path_str = str(Path(out_dir) / mesh_file_name)
                cq.exporters.export(prepared_part, path_str)
                self.logger.print(f"Saved {path_str}", symbol="📄")

    def generate_diagram(self, out_dir, names=None):
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
        wire_objs = [self.build_wire(name)[1] for name in names]

        for i, wire_obj in enumerate(wire_objs):
            for right in [False, True]:
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

    def generate_all(self, out_dir, zip_name="build.zip"):
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
        self.generate_diagram(names=self.names, out_dir=out_dir)
        self.generate_parts(names=self.names, out_dir=out_dir)

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
    args = parser.parse_args()
    return args


def main(logger, args):
    """Initialize the build environment and perform build actions.

    :param _type_ args: The program arguments.
    """
    gen_args = {}
    if args.outdir:
        gen_args["out_dir"] = args.outdir

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
