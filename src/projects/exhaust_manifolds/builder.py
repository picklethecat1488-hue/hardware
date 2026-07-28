"""Builder for manifold tube geometry."""

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, cast, Annotated, Literal, Sequence
from build123d import *  # type: ignore
from pydantic import validate_call, Field
from model.utils import method_cache
from provider import Mode as ProviderMode, Room
from model import AppConfig, TextArgs
from projects_config import ExhaustManifoldsConfig


class ExhaustManifoldsBuilder:
    """Builder for exhaust manifold geometry."""

    def __init__(
        self,
        config: AppConfig,
        exhaust_manifolds_config: ExhaustManifoldsConfig,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """Initialize the builder with configuration."""
        self.config = config
        self.exhaust_manifolds_config = exhaust_manifolds_config
        self.executor = executor or ThreadPoolExecutor()

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_wire(self, name: str) -> Wire:
        """Create the manifold path wire."""
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
        inlet_start, v_start = self.exhaust_manifolds_config.P[inlet_key], self.exhaust_manifolds_config.V[inlet_key]
        outlet_start, v_end = self.exhaust_manifolds_config.P[outlet_key], self.exhaust_manifolds_config.V[outlet_key]
        inlet_end = inlet_start + v_start * self.exhaust_manifolds_config.clamp_lengths[0]

        with BuildLine() as path:
            Line(inlet_start, inlet_end)
            Spline([inlet_end, outlet_start], tangents=(v_start, v_end))
            Line(outlet_start, outlet_start + v_end * self.exhaust_manifolds_config.clamp_lengths[-1])
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
    ) -> BuildSketch:
        """Create a circular tube profile sketch."""
        if outer_radius is None:
            outer_radius = min(self.exhaust_manifolds_config.clamp_diameters) / 2
        if inner_radius is None:
            inner_radius = outer_radius - self.exhaust_manifolds_config.wall_thickness
        if joint_space is None:
            joint_space = self.exhaust_manifolds_config.joint_space

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
                    h = (outer_radius + self.exhaust_manifolds_config.joint_radius) * 2
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
                    Circle(self.exhaust_manifolds_config.joint_radius)
                with Locations(c_right):
                    Circle(self.exhaust_manifolds_config.joint_radius + joint_space, mode=Mode.SUBTRACT)
        return sketch

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
    ) -> BuildSketch:
        """Create a circular tube profile sketch with rotation applied."""
        with BuildSketch() as sketch_builder:
            with Locations(Rotation(0, 0, center_deg)):
                add(self.create_profile_sketch(angle_deg, outer_radius, inner_radius, lap_joint, joint_space))
        return sketch_builder

    @method_cache
    def create_manifold(self, name, right=False, lap_joint=False, half_tube=False, joint_space=None) -> BuildPart:
        """Build a manifold part."""
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
        return tube

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
    ) -> BuildPart:
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
        return ring

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_clamp_bed(
        self,
        name: str,
        clamp_idx: int,
        right: bool = False,
        offset_deg: Optional[float] = None,
        joint_space: Optional[float] = None,
    ) -> BuildPart:
        """Create a clamp bed on the tube."""
        length = self.exhaust_manifolds_config.clamp_lengths[clamp_idx]
        outer_radius = self.exhaust_manifolds_config.clamp_diameters[clamp_idx] / 2
        inner_radius = (
            min(self.exhaust_manifolds_config.clamp_diameters) - self.exhaust_manifolds_config.wall_thickness
        ) / 2
        clamp_pos, angle_offset = cast(
            tuple[float, float], self.exhaust_manifolds_config.clamp_positions[name][clamp_idx]
        )
        if offset_deg is not None:
            angle_offset = offset_deg
        angle_span = 180
        center_deg = ((0 if right else 180) + angle_offset) % 360
        if joint_space is None:
            joint_space = self.exhaust_manifolds_config.clamp_space

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
    def create_text_shape(self, text: Annotated[str, Field(min_length=1)]) -> BuildSketch:
        """Return a cached logo text shape."""
        args = self.exhaust_manifolds_config.logo_text_args
        with BuildSketch() as s:
            Text(
                text,
                font_size=args.font_size,
                font=args.font,
                font_style=args.font_style,
                align=args.align,
            )
        return s

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_text(
        self,
        name: str,
        text: str,
        right: bool = False,
        offset_deg: Optional[float] = None,
    ) -> BuildPart:
        """Generate text geometry wrapped to the tube surface."""
        path = self.create_wire(name)
        off, angle_offset = self.exhaust_manifolds_config.logo_text_positions[name]
        loc = path.location_at(off)
        outer_radius = (
            cast(float, min(self.exhaust_manifolds_config.clamp_diameters))
            - self.exhaust_manifolds_config.wall_thickness
        ) / 2
        if offset_deg is not None:
            angle_offset = offset_deg
        angle_deg = ((0 if right else 180) + angle_offset) % 360

        # Generate the cached base text shape once as a pure Sketch.
        with BuildPart() as text_part:
            with BuildSketch():
                add(self.create_text_shape(text))
            args = self.exhaust_manifolds_config.logo_text_args
            extrude(amount=args.height)

        transformation = loc * Rotation(0, 90, 0) * Rotation(angle_deg, 0, 0) * Pos(0, 0, outer_radius)
        text_part.part = cast(Part, text_part.part).moved(transformation)
        return text_part

    def create_chamfer_cone(self, origin: VectorLike, normal: VectorLike, radius: float) -> BuildPart:
        """Create a cone used for chamfering."""
        with BuildPart() as cone:
            Cone(radius, 0, radius, align=(Align.CENTER, Align.CENTER, Align.MIN))
        cone.part = cast(Part, cone.part).moved(Plane(origin=origin, z_dir=normal).location)
        return cone

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_clean_tool(
        self,
        name: str,
        radius: Annotated[float | None, Field(ge=0)] = None,
        chamfer_radius: Annotated[float | None, Field(ge=0)] = None,
    ) -> BuildPart:
        """Build a cutting tool used to clean the internal tube volume."""
        path = self.create_wire(name)
        if radius is None:
            radius = (
                min(self.exhaust_manifolds_config.clamp_diameters) / 2 - self.exhaust_manifolds_config.wall_thickness
            )

        # Build the main cylindrical part of the clean tool
        profile_sketch = self.create_profile(center_deg=0, angle_deg=360, outer_radius=radius, inner_radius=0)
        with BuildPart() as clean_tool:
            with BuildSketch(path.location_at(0)):
                add(profile_sketch)
            sweep(path=path, transition=Transition.ROUND)
            if chamfer_radius is not None and chamfer_radius > 0:
                add(self.create_chamfer_cone(path.position_at(0), path.tangent_at(0), chamfer_radius))
                add(self.create_chamfer_cone(path.position_at(1), path.tangent_at(1) * -1, chamfer_radius))
        return clean_tool

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_part(
        self,
        name: Literal["driver", "passenger"],
        right: bool = False,
        tube_only: bool = False,
    ) -> BuildPart:
        """Build one half of the manifold assembly."""
        # Determine part parameters based on mode
        lap_joint = not tube_only
        joint_space = 0 if tube_only else self.exhaust_manifolds_config.joint_space

        with BuildPart() as p:
            add(
                self.create_manifold(
                    name,
                    right=right,
                    lap_joint=lap_joint,
                    half_tube=True,
                    joint_space=joint_space,
                )
            )
            if not tube_only:
                for idx in range(1, len(self.exhaust_manifolds_config.clamp_positions[name]) - 1):
                    add(self.create_clamp_bed(name, idx, right=right))
                label = "R" if right else ("L" if (name == "driver") else "R")
                add(self.create_text(name, text=label, right=right))

            # Clean the inner part volume and chamfer the ends
            chamfer_radius = (
                min(self.exhaust_manifolds_config.clamp_diameters) - self.exhaust_manifolds_config.wall_thickness
            ) / 2
            clean_tool_gen = self.create_clean_tool(name, chamfer_radius=chamfer_radius)
            add(clean_tool_gen, mode=Mode.SUBTRACT)

        return p

    @validate_call(config={"arbitrary_types_allowed": True})
    @method_cache
    def create_prepared_part(self, name: Literal["driver", "passenger"], right: bool = False) -> BuildPart:
        """Prepare a part for STL export."""

        def facing_up(part):
            """Return whether the part is oriented upward."""
            full_part = self.create_manifold(name)
            center_part = part.center()
            center_full = full_part.part.center()
            diff = center_part - center_full
            normal = diff.normalized()
            return normal.Z > 0

        def rotation(part):
            """Compute the rotation needed to flatten the part."""
            path_edge = sorted(part.edges(), key=lambda e: e.length)[-1]
            p1, p2 = path_edge.start_point(), path_edge.end_point()
            diff = p2 - p1
            axis = Vector(-diff.Y, diff.X, 0)
            horizontal_dist = math.sqrt(diff.X**2 + diff.Y**2)
            angle_deg = math.degrees(math.atan2(diff.Z, horizontal_dist))
            return axis, angle_deg

        def translation(part):
            """Compute the Z translation to flatten the part."""
            return (0, 0, -part.bounding_box().min.Z)

        part_gen = self.create_part(name, right=right)
        part = part_gen.part

        # Ensure we have a single manipulatable object if the part is fragmented
        if isinstance(part, ShapeList):
            part = Compound(part.solids())

        if not facing_up(part):
            part = part.rotate(Axis.X, 180)
        axis, angle_deg = rotation(part)
        part = part.rotate(Axis((0, 0, 0), axis), angle_deg)
        part = part.translate(translation(part))
        with BuildPart() as prepared:
            add(part)
        return prepared

    @validate_call(config={"arbitrary_types_allowed": True})
    def build_part(self, target: str, subassembly: Optional[str], mode: ProviderMode) -> Any:
        """Build part geometry supporting subassemblies and various modes."""
        name = cast(Literal["driver", "passenger"], target)
        if subassembly is None:
            return self.create_manifold(name)
        right = subassembly == "right"
        if mode == ProviderMode.PRINT:
            return self.create_prepared_part(name, right=right)
        return self.create_part(name, right=right, tube_only=False)

    @validate_call(config={"arbitrary_types_allowed": True})
    def build_diagram(
        self,
        room: Room,
        targets: Sequence[str],
        mode: ProviderMode,
    ) -> None:
        """Build an exploded diagram for the parts."""

        def get_part_location(part, full_part, offset=0, dist=0):
            """Compute part placement positions for the diagram."""
            center_part = part.center()
            center_full = full_part.center()
            move_dir = (center_part - center_full).normalized()
            return move_dir * dist + Vector(0, offset, 0)

        if "product" in targets:
            names = ["driver", "passenger"]
        else:
            names = cast(Sequence[Literal["driver", "passenger"]], targets)
        right_vals = (False, True)
        results = []
        for i, name in enumerate(names):
            full_f = self.executor.submit(self.create_manifold, name)
            parts_fs = {r: self.executor.submit(self.create_part, name, right=r) for r in right_vals}
            results.append((i, name, full_f, parts_fs))

        for i, name, full_f, parts_fs in results:
            full_part = full_f.result()
            parts = {r: f.result() for r, f in parts_fs.items()}
            wire_obj = self.create_wire(name)
            locs = {}

            for right in right_vals:
                side = "right" if right else "left"
                loc_vec = get_part_location(
                    parts[right].part,
                    full_part.part,
                    offset=(i * self.exhaust_manifolds_config.diagram_part_offset),
                    dist=self.exhaust_manifolds_config.diagram_part_dist,
                )
                locs[right] = loc_vec
                room.add(f"{name}_{side}", parts[right].part.translate(loc_vec))

            if True in locs and False in locs:
                mid_point = wire_obj.position_at(0.5)
                connector = Line(locs[True] + mid_point, locs[False] + mid_point)
                room.add(f"{name}_connector", connector)

            text_pos = wire_obj.position_at(1)
            label_loc = text_pos + Vector(
                self.exhaust_manifolds_config.diagram_label_dist,
                i * self.exhaust_manifolds_config.diagram_part_offset,
                self.exhaust_manifolds_config.diagram_part_dist,
            )
            label_text = f"{name.upper()} ({'L' if (name == 'driver') else 'R'})"
            room.add_label(f"{name}_label", label_text, label_loc, options=TextArgs(font_size=45))
