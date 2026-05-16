"""Contains the code to build exhaust manifolds."""

import argparse
import math
import numpy as np
import os
from pathlib import Path
from pydantic_changedetect import ChangeDetectionMixin
import cadquery as cq
from functools import lru_cache, cached_property
from IPython.core.getipython import get_ipython
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import zipfile


class AppConfig(ChangeDetectionMixin, BaseSettings):
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

    # Wall thickness ~3mm
    wall_thickness: float = 3.0

    # Inlet and outlet diameters, 2.5", inner clamp diameter 3"
    clamp_diameters: list[float] = [63.5, 76.2, 63.5]

    # Inlet and outlet clamp length 2", inner clamp length 1"
    clamp_lengths: list[float] = [50.4, 25.4, 50.4]

    # The clamp positions, each one is a tuple of path offset and angle offset
    clamp_positions: dict[str, list[tuple[float, float] | None]] = {
        "driver": [None, (0.5, 0), None],
        "passenger": [None, (0.5, 0), None],
    }

    # The minimum space between each clamp bed
    clamp_space: float = 10

    # The fillet or chamfer to apply to object edges
    edge_rounding: float = 0.75

    # The part names, driver and passenger
    names: list[str] = ["driver", "passenger"]

    # Path attractors to be used to change exhaust tube paths
    attractors: dict[str, list[tuple[float, float, float]] | None] = {
        "driver": None,
        "passenger": None,
    }

    # Raw measurements used for part construction
    _measurements: list[tuple[float, float, float]] = [
        # p[1] -> p[2] valve controller bottom plane
        (443, 152, 521),
        (652, 205, 500),
        # p(3) passenger exhaust input inlet start
        (565, 356, 352),
        # p(4) -> p(5) direction of passenger exhaust input
        (555, 327, 0),
        (480, 343, 0),
        # p(6) driver exhaust input inlet start
        (347, 279, 382),
        # p(7) -> p(8) direction of driver exhaust input
        (0, 0, 0),
        (-0.33871947, -0.90882745, 0.24351958),
        # p(9) driver exhaust output inlet start
        (200, 0, 522.5),
        # p(10) passenger exhaust output inlet start
        (895, 0, 522.5),
    ]

    # The logo text arguments
    logo_text_args: dict[str, str | int | float] = {
        "txt": "FHB",
        "fontsize": 10,
        "distance": 2,
        "fontPath": "DancingScript-VariableFont_wght.ttf",
        "halign": "center",
        "valign": "center",
        "kind": "bold",
    }

    # The logo text offset, pathwise and anglewise
    logo_text_positions: dict[str, tuple[float, float]] = {
        "driver": (0.4, 0),
        "passenger": (0.4, 0),
    }

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="APP_", alias_generator=str.upper, populate_by_name=True
    )

    @cached_property
    def measurements(self):
        """Get the raw measurements used for the project.

        :return _type_: The raw measurement points.
        """
        p = {}
        for idx, item in enumerate(self._measurements):
            p[idx + 1] = np.array(item)
        return p


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

        def dir_vector(start, end):
            """Generate a 3D direction vector for the given points, e.g. p[4] and p[5]."""
            return (end - start) / np.linalg.norm(end - start)

        self.config = config or AppConfig()
        self.logger = logger or Logger(enabled=False)
        self.p = self.config.measurements

        for idx in [3, 6]:
            self.p[idx][2] = self.p[idx][2] - (self.config.clamp_diameters[0] / 2)
        for idx in [9, 10]:
            self.p[idx][2] = self.p[idx][2] - (self.config.clamp_diameters[-1] / 2)

        self.P = {
            "driver_inlet": self.p[6],
            "driver_outlet": self.p[9],
            "passenger_inlet": self.p[3],
            "passenger_outlet": self.p[10],
        }

        self.V = {
            "driver_inlet": dir_vector(self.p[7], self.p[8]),
            "driver_outlet": np.array([-1, 0, 0]),
            "passenger_inlet": dir_vector(self.p[5], self.p[4]),
            "passenger_outlet": np.array([1, 0, 0]),
        }

    @lru_cache
    def build_bound_box(self):
        """Build the bounding box.

        The bounds are an Axis Aligned Boundary Box representing the valid space parts may occupy.

        :return _type_: The bounding box.
        """
        # Create the overall bounds.
        x_len = np.max(self.config.x_bounds) - np.min(self.config.x_bounds)
        y_len = np.max(self.config.y_bounds) - np.min(self.config.y_bounds)
        z_len = np.max(self.config.z_bounds) - np.min(self.config.z_bounds)
        center = (
            np.min(self.config.x_bounds) + x_len / 2,
            np.min(self.config.y_bounds) + y_len / 2,
            np.min(self.config.z_bounds) + z_len / 2,
        )
        bounds = cq.Workplane("XY").box(x_len, y_len, z_len).translate(center)

        # Subtract the valve controller bottom plane from the overall bounds.
        x_len = self.p[2][0] - self.p[1][0]
        y_len = np.max(self.config.y_bounds) - np.mean([self.p[2][1], self.p[1][1]])
        z_len = np.max(self.config.z_bounds) - np.mean([self.p[2][2], self.p[1][2]])
        center = (
            np.min([self.p[2][0], self.p[1][0]]) + x_len / 2,
            np.min([self.p[2][1], self.p[1][1]]) + y_len / 2,
            np.min([self.p[2][2], self.p[1][2]]) + z_len / 2,
        )
        top_plane = cq.Workplane("XY").box(x_len, y_len, z_len).translate(center)
        bounds = bounds.cut(top_plane)
        return bounds

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
        attractors = [cq.Vector(*attractor) for attractor in (self.config.attractors[name] or [])]
        points = [cq.Vector(*inlet_end)] + attractors + [cq.Vector(*outlet_start)]

        wire = cq.Wire.assembleEdges(
            [
                cq.Edge.makeLine(cq.Vector(*inlet_start), cq.Vector(*inlet_end)),
                cq.Edge.makeSpline(
                    listOfVector=points,
                    tangents=(cq.Vector(*v_start), cq.Vector(*v_end)),
                    periodic=False,
                ),
                cq.Edge.makeLine(cq.Vector(*outlet_start), cq.Vector(*outlet_end)),
            ]
        )
        path = cq.Workplane("XY").add(wire)
        return path

    @lru_cache
    def create_profile(self, center_deg, angle_deg, outer_radius=None, inner_radius=None):
        """Create a profile sketch using the given radius.

        :param float center_deg: The center angle of the tube profile in degrees.
        :param float angle_deg: The angular span of the tube profile in degrees.
        :param int outer_radius: The optional outer radius of the profile.
        :param int inner_radius: The optional inner radius of the profile.
        :return _type_: The profile section.
        """
        if outer_radius is None:
            outer_radius = min(self.config.clamp_diameters) / 2
        if inner_radius is None:
            inner_radius = outer_radius - self.config.wall_thickness
        if inner_radius >= outer_radius:
            raise ValueError("Invalid radius or inner radius")
        start_deg = center_deg - angle_deg / 2
        end_deg = center_deg + angle_deg / 2
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
        return sketch

    @lru_cache
    def build_tube(self, name, right=False):
        """Build an exhaust tube.

        :param _type_ name: The name of the manifold to build
        :param bool right: True if building the right half, defaults to False
        :return _type_: The exhaust manifold
        """
        path = self.create_wire(name)
        loc = path.val().locationAt(0)  # type: ignore
        center_deg = 90 if right else 270
        angle_deg = 180
        profile_sketch = self.create_profile(center_deg, angle_deg)
        tube = (
            cq.Workplane(loc)
            .placeSketch(profile_sketch)  # type: ignore
            .sweep(path, transition="round")
            .fillet(self.config.edge_rounding)
        )
        return tube

    def create_ring(
        self,
        name,
        off,
        len,
        inner_radius=None,
        outer_radius=None,
        center_deg: float = 0,
        angle_deg: float = 360,
    ):
        """Create a ring at a given offset.

        :param _type_ name: The part name.
        :param _type_ off: The ring offset
        :param _type_ len: The axial path length of the ring section
        :param _type_ inner_radius: The inner radius.
        :param _type_ outer_radius: The outer radius.
        :param float center_deg: The center angle of the ring section.
        :param float angle_deg: The angular width of the ring section in degrees.
        :return _type_: The ring
        """
        path = self.create_wire(name)
        wire = path.val()
        loc = wire.locationAt(off)  # type: ignore
        workplane = cq.Workplane(loc)
        profile_sketch = self.create_profile(
            center_deg=center_deg,
            angle_deg=angle_deg,
            outer_radius=outer_radius,
            inner_radius=inner_radius,
        )
        p1 = wire.positionAt(off)  # type: ignore
        p2 = wire.positionAt(off + len / wire.Length())  # type: ignore
        path = workplane.polyline([p1, p2])
        ring = workplane.placeSketch(profile_sketch).sweep(path)  # type: ignore
        return ring

    @lru_cache
    def build_clamp_bed(self, name, clamp_idx, right=False, offset_deg=None):
        """Build a clamp bed.

        :param _type_ name: The part name to build.
        :param _type_ clamp_idx: The clamp index to build
        :param bool right: True if building the right half, defaults to False
        :return _type_: The clamp bed
        """
        length = self.config.clamp_lengths[clamp_idx]
        outer_radius = self.config.clamp_diameters[clamp_idx] / 2
        inner_radius = (min(self.config.clamp_diameters) - self.config.wall_thickness) / 2
        clamp_pos, angle_offset = self.config.clamp_positions[name][clamp_idx]
        if offset_deg:
            angle_offset = offset_deg
        angle_span = 180 - 2 * self.config.clamp_space
        center_deg = (90 if right else 270) + angle_offset

        # Create the clamp bed
        bed = self.create_ring(
            name,
            clamp_pos,
            length,
            inner_radius=inner_radius,
            outer_radius=outer_radius,
            center_deg=center_deg,
            angle_deg=angle_span,
        ).fillet(self.config.edge_rounding)
        return bed

    @lru_cache
    def create_logo_text_shape(self):
        """Create and cache the raw logo text shape used for placement."""
        return cq.Workplane("XY").text(**self.config.logo_text_args)  # type: ignore

    @lru_cache
    def build_text(self, name, right=False, offset_deg=None):
        """Build and place the logo text.

        :param _type_ name: The name of the part to build for.
        :param _type_ angle_deg: The angle to place the text.
        :param bool right: True if building the right half, defaults to False
        :return _type_: The logo text.
        """
        path = self.create_wire(name)
        wire = path.val()
        off, angle_offset = self.config.logo_text_positions[name]  # type: ignore
        pos = wire.positionAt(off)  # type: ignore
        tan = wire.tangentAt(off)  # type: ignore
        plane = cq.Plane(origin=pos, normal=tan)
        outer_radius = (min(self.config.clamp_diameters) - self.config.wall_thickness) / 2  # type: ignore
        if offset_deg is not None:
            angle_offset = offset_deg
        angle_deg = (90 if right else 270) + angle_offset

        # Generate the cached base text shape once as a pure Workplane.
        text_wp = self.create_logo_text_shape()

        text = (
            cq.Workplane(plane)
            .transformed(rotate=(0, 90, 0))
            .transformed(rotate=(angle_deg, 0, 0))
            .transformed(offset=(0, 0, outer_radius))
            .eachpoint(lambda loc: text_wp.val().moved(loc), True)
        )
        return text

    @lru_cache
    def build_clean_tool(self, name, radius=None):
        """Build the clean tool.

        :param _type_ name: The name of the part to build for.
        :return _type_: The clean tool to cut excess inner part volume off of.
        """
        # Create the clean tool
        path = self.create_wire(name)
        wire = path.val()
        tube_loc = wire.locationAt(0)  # type: ignore
        if radius is None:
            radius = min(self.config.clamp_diameters) / 2 - self.config.wall_thickness
        profile_sketch = self.create_profile(center_deg=0, angle_deg=360, outer_radius=radius, inner_radius=0)
        tube = cq.Workplane(tube_loc).placeSketch(profile_sketch).sweep(path, transition="round")  # type: ignore
        return tube

    @lru_cache
    def build_part(self, name, right=False, tube_only=False):
        """Build the left or right half of the manifold.

        :param _type_ name: The name of the manifold
        :param bool right: True if building the right half, defaults to False
        :param bool tube_only: True if only building the tube
        :return _type_: The manifold half
        """
        if name == "driver" or name == "passenger":
            # Create the main part body.
            part = self.build_tube(name, right=right)
            if not tube_only:
                for idx in range(1, len(self.config.clamp_positions[name]) - 1):
                    # Add inner clamp beds.
                    clamp_bed = self.build_clamp_bed(name, idx, right=right)
                    part = part.union(clamp_bed)

                # Add the text
                if right:
                    text = self.build_text(name, right=right)
                    part = part.cut(text)

                # Clean the inner part volume
                clean_tool = self.build_clean_tool(name)
                part = part.cut(clean_tool)
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
            part = part.rotate((0, 0, 0), (1, 0, 0), 180)
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
        help="Generate a file and exit. Usage: -o <name>",
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
