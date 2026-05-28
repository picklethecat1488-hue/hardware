"""Build exhaust manifold geometry and export 3D printable parts using build123d."""

import argparse
import math
import os
from pathlib import Path
import OCP.TopoDS  # type: ignore
from model import AppConfig, method_cache
import cadquery as cq  # type: ignore
from build123d import *  # type: ignore
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, cast, Annotated, Literal
from pydantic import validate_call, Field
import zipfile
from shell import Logger

# Monkey-patch TopoDS_Shape to resolve Pydantic validation errors.
# Pydantic 2 probes for a HashCode method when validating OCP-wrapped types.
if not hasattr(OCP.TopoDS.TopoDS_Shape, "HashCode"):
    OCP.TopoDS.TopoDS_Shape.HashCode = lambda self, upper: id(self) % upper  # type: ignore


class Builder:
    """Builds manifold geometry and exports parts using build123d."""

    def __init__(self, config=None, logger=None):
        """Initialize builder dependencies and measurements."""
        self.config = config or AppConfig()
        self.logger = logger or Logger(enabled=False)
        self.executor = ThreadPoolExecutor()

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_wire(self, name: str) -> Wire:
        """Create the manifold path wire."""
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
        inlet_start, v_start = self.config.tube.P[inlet_key], self.config.tube.V[inlet_key]
        outlet_start, v_end = self.config.tube.P[outlet_key], self.config.tube.V[outlet_key]
        inlet_end = inlet_start + v_start * self.config.tube.clamp_lengths[0]

        with BuildLine() as path:
            Line(inlet_start, inlet_end)
            Spline([inlet_end, outlet_start], tangents=(v_start, v_end))
            Line(outlet_start, outlet_start + v_end * self.config.tube.clamp_lengths[-1])
        return path.wire()

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_profile_sketch(
        self,
        angle_deg: Annotated[float, Field(ge=0, le=360)],
        outer_radius: Annotated[float | None, Field(ge=0)] = None,
        inner_radius: Annotated[float | None, Field(ge=0)] = None,
        lap_joint: bool = False,
        joint_space: Annotated[float | None, Field(ge=0)] = None,
    ) -> Sketch:
        """Create a circular tube profile sketch."""
        if outer_radius is None:
            outer_radius = min(self.config.tube.clamp_diameters) / 2
        if inner_radius is None:
            inner_radius = outer_radius - self.config.tube.wall_thickness
        if joint_space is None:
            joint_space = self.config.tube.joint_space

        # Narrow types for the static analyzer
        outer_radius = cast(float, outer_radius)
        inner_radius = cast(float, inner_radius)
        joint_space = cast(float, joint_space)

        if inner_radius >= outer_radius:
            raise ValueError(f"Inner radius must be smaller than outer: {inner_radius=}, {outer_radius=}")
        if angle_deg == 360 and lap_joint:
            raise ValueError("Lap joints cannot be used with a 360 degree full circle profile")

        with BuildSketch() as sketch:
            if angle_deg == 360:
                # Construct full circle
                Circle(radius=outer_radius)
            else:
                # Construct a partial circle
                start_deg = -angle_deg / 2
                with BuildLine():
                    p1 = Vector(outer_radius, 0).rotate(Axis.Z, start_deg)
                    p2 = p1.rotate(Axis.Z, angle_deg)
                    Line((0, 0), p1)
                    CenterArc((0, 0), outer_radius, start_deg, angle_deg)
                    Line(p2, (0, 0))
                make_face()

            if inner_radius > 0:
                # Hollow out the circle
                Circle(radius=inner_radius, mode=Mode.SUBTRACT)

            if angle_deg < 360:
                start_deg = -angle_deg / 2
                end_deg = angle_deg / 2
                if joint_space > 0:
                    # Apply a gap between the half-tubes to account for part deformation and epoxy.
                    # We rotate the rectangle by (angle - 90) because the default Sketch.rect
                    # has its height axis aligned with Y (90°). This ensures the gap is
                    # subtracted perpendicular to each parting line.
                    h = (outer_radius + self.config.tube.joint_radius) * 2
                    Rectangle(joint_space, h, rotation=start_deg - 90, mode=Mode.SUBTRACT)
                    Rectangle(joint_space, h, rotation=end_deg - 90, mode=Mode.SUBTRACT)

            if lap_joint:
                # Calculate shifted center points for the lap joint circles so they remain
                # attached to the part after the joint_space gap is subtracted.
                # The shift is applied perpendicular to the rotated parting line.
                end_rad = math.radians(end_deg)
                start_rad = math.radians(start_deg)
                face_shift = joint_space / 2
                c_left = (
                    inner_radius * math.cos(end_rad) + face_shift * math.sin(end_rad),
                    inner_radius * math.sin(end_rad) - face_shift * math.cos(end_rad),
                )
                c_right = (
                    inner_radius * math.cos(start_rad) - face_shift * math.sin(start_rad),
                    inner_radius * math.sin(start_rad) + face_shift * math.cos(start_rad),
                )
                # Create the interlocking protrusion and recess using full circles.
                with Locations(c_left):
                    Circle(self.config.tube.joint_radius)
                with Locations(c_right):
                    Circle(self.config.tube.joint_radius + joint_space, mode=Mode.SUBTRACT)
        return sketch.sketch

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_profile(
        self,
        center_deg: Annotated[float, Field(ge=0, le=360)],
        angle_deg: Annotated[float, Field(ge=0, le=360)],
        outer_radius: Annotated[float | None, Field(ge=0)] = None,
        inner_radius: Annotated[float | None, Field(ge=0)] = None,
        lap_joint: bool = False,
        joint_space: Annotated[float | None, Field(ge=0)] = None,
    ) -> Sketch:
        """Create a circular tube profile sketch with rotation applied."""
        sketch = self.create_profile_sketch(angle_deg, outer_radius, inner_radius, lap_joint, joint_space)
        return sketch.moved(Rotation(0, 0, center_deg))

    @method_cache
    def build_tube(self, name, right=False, lap_joint=False, half_tube=False, joint_space=None) -> Part:
        """Build a manifold tube."""
        path = self.create_wire(name)

        if half_tube:
            center_deg = 90 if right else 270
            angle_deg = 180
        else:
            center_deg = 0
            angle_deg = 360
            lap_joint = False

        profile_sketch = self.create_profile(center_deg, angle_deg, lap_joint=lap_joint, joint_space=joint_space)
        with BuildPart() as tube:
            with BuildSketch(path.location_at(0)):
                add(profile_sketch)
            sweep(path=path, transition=Transition.ROUND)
        return cast(Part, tube.part)

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_ring(
        self,
        name: str,
        off: Annotated[float, Field(ge=0, le=1)],
        length: Annotated[float, Field(gt=0)],
        inner_radius: Annotated[float | None, Field(ge=0)] = None,
        outer_radius: Annotated[float | None, Field(ge=0)] = None,
        center_deg: Annotated[float, Field(ge=0, le=360)] = 0,
        angle_deg: Annotated[float, Field(ge=0, le=360)] = 360,
        joint_space: Optional[float] = None,
    ) -> Part:
        """Create a ring-shaped tube segment."""
        path = self.create_wire(name)
        p1, p2 = path.position_at(off), path.position_at(off + length / path.length)
        with BuildLine() as ring_path:
            Line(p1, p2)

        profile_sketch = self.create_profile(
            center_deg=center_deg,
            angle_deg=angle_deg,
            outer_radius=outer_radius,
            inner_radius=inner_radius,
            joint_space=joint_space,
        )
        with BuildPart() as ring:
            with BuildSketch(path.location_at(off)):
                add(profile_sketch)
            sweep(path=ring_path.line)
        return cast(Part, ring.part)

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def build_clamp_bed(
        self,
        name: str,
        clamp_idx: int,
        right: bool = False,
        offset_deg: Optional[float] = None,
        joint_space: Optional[float] = None,
    ) -> Part:
        """Create a clamp bed on the tube."""
        length = self.config.tube.clamp_lengths[clamp_idx]
        outer_radius = self.config.tube.clamp_diameters[clamp_idx] / 2
        inner_radius = (min(self.config.tube.clamp_diameters) - self.config.tube.wall_thickness) / 2
        clamp_pos, angle_offset = cast(tuple[float, float], self.config.tube.clamp_positions[name][clamp_idx])
        if offset_deg is not None:
            angle_offset = offset_deg
        angle_span = 180
        center_deg = ((0 if right else 180) + angle_offset) % 360
        if joint_space is None:
            joint_space = self.config.tube.clamp_space

        # Create the clamp bed
        return self.create_ring(
            name,
            clamp_pos,
            length,
            inner_radius=inner_radius,
            outer_radius=outer_radius,
            center_deg=center_deg,
            angle_deg=angle_span,
            joint_space=joint_space,
        )

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_text_shape(self, text: Annotated[str, Field(min_length=1)]) -> Sketch:
        """Return a cached logo text shape."""
        args = self.config.tube.logo_text_args
        with BuildSketch() as s:
            Text(
                text,
                font_size=args.font_size,
                font=args.font,
                font_style=args.font_style,
                align=args.align,
            )
        return s.sketch

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def build_text(
        self,
        name: str,
        text: str,
        right: bool = False,
        offset_deg: Optional[float] = None,
    ) -> Part:
        """Generate text geometry wrapped to the tube surface."""
        path = self.create_wire(name)
        off, angle_offset = self.config.tube.logo_text_positions[name]
        loc = path.location_at(off)
        outer_radius = (cast(float, min(self.config.tube.clamp_diameters)) - self.config.tube.wall_thickness) / 2
        if offset_deg is not None:
            angle_offset = offset_deg
        angle_deg = ((0 if right else 180) + angle_offset) % 360

        # Generate the cached base text shape once as a pure Sketch.
        with BuildPart() as text_part:
            with BuildSketch():
                add(self.create_text_shape(text))
            args = self.config.tube.logo_text_args
            extrude(amount=args.height)

        transformation = loc * Rotation(0, 90, 0) * Rotation(angle_deg, 0, 0) * Pos(0, 0, outer_radius)
        return cast(Part, text_part.part).moved(transformation)

    def create_chamfer_cone(self, origin: VectorLike, normal: VectorLike, radius: float) -> Part:
        """Create a cone used for chamfering."""
        with BuildPart() as cone:
            Cone(radius, 0, radius, align=(Align.CENTER, Align.CENTER, Align.MIN))
        return cast(Part, cone.part).moved(Plane(origin=origin, z_dir=normal).location)

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def build_clean_tool(
        self,
        name: str,
        radius: Annotated[float | None, Field(ge=0)] = None,
        chamfer_radius: Annotated[float | None, Field(ge=0)] = None,
    ) -> Part:
        """Build a cutting tool used to clean the internal tube volume."""
        path = self.create_wire(name)
        if radius is None:
            radius = min(self.config.tube.clamp_diameters) / 2 - self.config.tube.wall_thickness

        # Build the main cylindrical part of the clean tool
        profile_sketch = self.create_profile(center_deg=0, angle_deg=360, outer_radius=radius, inner_radius=0)
        with BuildPart() as clean_tool:
            with BuildSketch(path.location_at(0)):
                add(profile_sketch)
            sweep(path=path, transition=Transition.ROUND)
            if chamfer_radius is not None and chamfer_radius > 0:
                add(self.create_chamfer_cone(path.position_at(0), path.tangent_at(0), chamfer_radius))
                add(self.create_chamfer_cone(path.position_at(1), path.tangent_at(1) * -1, chamfer_radius))
        return cast(Part, clean_tool.part)

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def build_part(
        self,
        name: Literal["driver", "passenger"],
        right: bool = False,
        tube_only: bool = False,
    ) -> Part:
        """Build one half of the manifold assembly."""
        # Determine part parameters based on mode
        lap_joint = not tube_only
        joint_space = 0 if tube_only else self.config.tube.joint_space

        # Create the main part body.
        part = self.build_tube(
            name,
            right=right,
            lap_joint=lap_joint,
            half_tube=True,
            joint_space=joint_space,
        )
        if not tube_only:
            to_fuse = []
            for idx in range(1, len(self.config.tube.clamp_positions[name]) - 1):
                to_fuse.append(self.build_clamp_bed(name, idx, right=right))

            label = f"{self.config.ver}" if right else ("L" if (name == "driver") else "R")
            to_fuse.append(self.build_text(name, text=label, right=right))

            if to_fuse:
                part = part.fuse(*to_fuse)

        # Clean the inner part volume and chamfer the ends
        chamfer_radius = (min(self.config.tube.clamp_diameters) - self.config.tube.wall_thickness) / 2
        clean_tool = self.build_clean_tool(name, chamfer_radius=chamfer_radius)
        part = part.cut(clean_tool)
        return part

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def build_prepared_part(self, name: Literal["driver", "passenger"], right: bool = False) -> Part:
        """Prepare a part for STL export."""

        def facing_up(part):
            """Return whether the part is oriented upward."""
            if name == "driver" or name == "passenger":
                full_part = self.build_tube(name)
            else:
                raise ValueError(f"Invalid name: {name}")
            center_part = part.center()
            center_full = full_part.center()
            diff = center_part - center_full
            normal = diff.normalized()
            return normal.Z > 0

        def rotation(part):
            """Compute the rotation needed to flatten the part."""
            # Find the path edge, then extract the first and last points from it
            path_edge = sorted(part.edges(), key=lambda e: e.length)[-1]
            p1, p2 = path_edge.start_point(), path_edge.end_point()
            diff = p2 - p1

            # Compute the tilt axis and angle
            axis = Vector(-diff.Y, diff.X, 0)
            horizontal_dist = math.sqrt(diff.X**2 + diff.Y**2)
            angle_deg = math.degrees(math.atan2(diff.Z, horizontal_dist))
            return axis, angle_deg

        def translation(part):
            """Compute the Z translation to flatten the part."""
            return (0, 0, -part.bounding_box().min.Z)

        # Ensure the part is facing up on the print bed in a way that is optimal for 3D printing
        part = self.build_part(name, right=right)
        if not facing_up(part):
            part = part.rotate(Axis.X, 180)
        axis, angle_deg = rotation(part)
        part = part.rotate(Axis((0, 0, 0), axis), angle_deg)
        part = part.translate(translation(part))
        return part

    def generate_parts(self, out_dir, names=None, right_vals=None):
        """Export STL files for generated parts."""
        file_prefix = f"{self.config.project_name}_v{self.config.ver}"

        if names is None:
            names = self.config.tube.names
        if right_vals is None:
            right_vals = [False, True]

        def export_task(name, right):
            side = "right" if right else "left"
            mesh_file_name = f"{file_prefix}_{name}_{side}.stl"
            prepared_part = self.build_prepared_part(name, right=right)
            path_str = str(Path(out_dir) / mesh_file_name)
            export_stl(prepared_part, path_str)
            self.logger.print(f"Saved {path_str}", symbol="📄")

        # Run STL meshing and file export in parallel to utilize all CPU cores.
        tasks = [(name, right) for name in names for right in right_vals]
        list(self.executor.map(lambda p: export_task(*p), tasks))

    @validate_call(config={"arbitrary_types_allowed": True})
    def generate_diagram(
        self, out_dir, names: list[Literal["driver", "passenger"]] = ["driver", "passenger"], right_vals=None
    ):
        """Export an exploded diagram for the parts."""

        def get_part_location(part, full_part, offset=0, dist=0):
            """Compute part placement positions for the diagram."""
            # Separate the halves by moving them away from the common center.
            center_part = part.center()
            center_full = full_part.center()
            move_dir = (center_part - center_full).normalized()
            return move_dir * dist + Vector(0, offset, 0)

        def to_cq_shape(b123d_obj) -> cq.Shape:
            """Convert a build123d shape to a CadQuery shape."""
            # Extract the underlying OCP shape and cast it to a CadQuery Shape object
            return cq.Shape.cast(b123d_obj.wrapped)

        if names is None:
            names = self.config.tube.names
        if right_vals is None:
            right_vals = [False, True]

        diagram_name = f"{self.config.project_name}_v{self.config.ver}_diagram.svg"
        assy = cq.Assembly()

        # Pre-submit all tasks to the executor to allow actual parallel processing
        results = []
        for i, name in enumerate(names):
            full_f = self.executor.submit(self.build_tube, name)
            parts_fs = {r: self.executor.submit(self.build_part, name, right=r) for r in right_vals}
            results.append((i, name, full_f, parts_fs))

        for i, name, full_f, parts_fs in results:
            full_part = full_f.result()
            parts = {r: f.result() for r, f in parts_fs.items()}
            wire_obj = self.create_wire(name)
            locs = {}

            for right in right_vals:
                loc_vec = get_part_location(
                    parts[right],
                    full_part,
                    offset=(i * self.config.diagram_part_offset),
                    dist=self.config.diagram_part_dist,
                )
                locs[right] = loc_vec
                assy.add(to_cq_shape(parts[right].translate(loc_vec)))

            # Connect parts to each other with a centerline
            if True in locs and False in locs:
                mid_point = wire_obj.position_at(0.5)
                connector = Line(locs[True] + mid_point, locs[False] + mid_point)
                assy.add(to_cq_shape(connector))

            # Label parts with 3D text oriented toward the camera
            projection_dir = self.config.diagram_options.projection_dir
            text_pos = wire_obj.position_at(1)
            label_loc = text_pos + Vector(
                self.config.diagram_label_dist,
                i * self.config.diagram_part_offset,
                self.config.diagram_part_dist,
            )
            label_text = f"{name.upper()} ({'L' if (name == 'driver') else 'R'})"

            with BuildPart() as label_gen:
                # Align the text plane to the camera projection for clarity
                with BuildSketch(Plane(origin=label_loc, z_dir=projection_dir)):
                    Text(label_text, font_size=45)
                extrude(amount=5)
                assy.add(to_cq_shape(cast(Part, label_gen.part)))

        path_str = str(Path(out_dir) / diagram_name)
        # Use CadQuery's exporter via the assembly's compound shape
        assy.toCompound().export(path_str, opt=self.config.diagram_options.model_dump(by_alias=True))
        self.logger.print(f"Saved {path_str}", symbol="📄")

    def generate_all(self, out_dir, right_vals=None, zip_name="build.zip"):
        """Generate diagrams, parts, and package them."""

        def zip_build(zip_file_str):
            """Write generated files into a zip archive."""
            with zipfile.ZipFile(zip_file_str, "w", zipfile.ZIP_DEFLATED) as zipf:
                for _, _, files in os.walk(out_dir):
                    for file in files:
                        file_str = str(Path(out_dir) / file)
                        if not os.path.samefile(zip_file_str, file_str):
                            zipf.write(file_str, file)

        # Export the diagram and files
        self.generate_diagram(names=self.config.tube.names, out_dir=out_dir, right_vals=right_vals)
        self.generate_parts(names=self.config.tube.names, out_dir=out_dir, right_vals=right_vals)

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
        builder.config.dump_env(args.env)
        logger.print(f"Saved environment to {args.env}", symbol="⚙️ ")

    if not args.diagram is None:
        if not args.diagram is True:
            gen_args["names"] = [args.diagram]
        builder.generate_diagram(**gen_args)
    elif not args.output is None:
        if args.output:
            gen_args["names"] = [args.output]
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
