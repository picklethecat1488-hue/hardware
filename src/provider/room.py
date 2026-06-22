"""Specialized container for visualization items."""

import io
import math
import os
import shutil
import tempfile
import time
import pybullet as p
from pathlib import Path
from typing import Any, Union, Optional, TYPE_CHECKING, cast, Callable
from build123d import (
    BoundBox,
    BuildPart,
    BuildSketch,
    BuildLine,
    Compound,
    Edge,
    Vector,
    Plane,
    Text,
    Align,
    Location,
    Sketch,
    RigidJoint,
    RevoluteJoint,
    LinearJoint,
    BallJoint,
)
from build123d.exporters import ExportSVG, Drawing
import rerun as rr
import socket
from model import DiagramOptions, TextArgs
from .types import ColorType, URDFShape, Simulate, CollisionGroup, CollisionMask
from .utils import get_rgba_color

if TYPE_CHECKING:
    from model.app_config import AppConfig


def _is_real_physics_client(physics_client: Any) -> bool:
    """Check if the given physics client ID is connected to a real physics server."""
    if not isinstance(physics_client, int) or physics_client < 0:
        return False
    try:
        info = p.getConnectionInfo(physicsClientId=physics_client)
        return bool(info.get("isConnected", False))
    except Exception:
        return False


class BulletStateTracker:
    """Helper class to track and query PyBullet body and particle states efficiently."""

    def __init__(self, body_id: int, physics_client: int, label_to_link_idx: dict[str, int]):
        """Initialize the Tracker."""
        self.body_id = body_id
        self.physics_client = physics_client
        self.label_to_link_idx = label_to_link_idx
        self.particle_body_ids: list[int] = []
        self.particle_colors: list[list[float]] = []
        self.particle_radii: list[float] = []
        self.transforms: dict[str, tuple[list[float], list[float]]] = {}
        self.particle_positions: list[list[float]] = []
        self._last_checked_num_bodies = 0

    def _discover_new_particles(self) -> None:
        """Scan for newly created bodies since the last check and add them to particles."""
        is_real = _is_real_physics_client(self.physics_client)
        if not is_real:
            return

        num_bodies = p.getNumBodies(physicsClientId=self.physics_client)
        if num_bodies <= self._last_checked_num_bodies:
            return

        for i in range(self._last_checked_num_bodies, num_bodies):
            if i == self.body_id:
                continue
            dynamics = p.getDynamicsInfo(i, -1, physicsClientId=self.physics_client)
            mass = dynamics[0]
            if mass > 0.0:
                self.particle_body_ids.append(i)
                visual_data = p.getVisualShapeData(i, physicsClientId=self.physics_client)
                color = [0.5, 0.8, 1.0, 0.7]  # Default fallback color
                if visual_data:
                    color = list(visual_data[0][7])
                self.particle_colors.append(color)

                shape_data = p.getCollisionShapeData(i, -1, physicsClientId=self.physics_client)
                radius = 0.003  # Default fallback
                if shape_data:
                    radius = shape_data[0][3][0]
                self.particle_radii.append(radius)
        self._last_checked_num_bodies = num_bodies

    def update_state(self) -> None:
        """Query and update internal state properties from PyBullet."""
        self._discover_new_particles()

        self.transforms = {}
        for label, idx in self.label_to_link_idx.items():
            if idx == -1:
                base_pos, base_orn = p.getBasePositionAndOrientation(self.body_id, physicsClientId=self.physics_client)
                try:
                    dynamics = p.getDynamicsInfo(self.body_id, -1, physicsClientId=self.physics_client)
                    local_inertia_pos = dynamics[3]
                    local_inertia_orn = dynamics[4]
                    inv_inertia_pos, inv_inertia_orn = p.invertTransform(local_inertia_pos, local_inertia_orn)
                    pos, orn = p.multiplyTransforms(base_pos, base_orn, inv_inertia_pos, inv_inertia_orn)
                except Exception:
                    pos, orn = base_pos, base_orn
            else:
                state = p.getLinkState(self.body_id, idx, physicsClientId=self.physics_client)
                pos, orn = state[4], state[5]
            self.transforms[label] = (pos, orn)

        self.particle_positions = []
        for i in self.particle_body_ids:
            pos, _ = p.getBasePositionAndOrientation(i, physicsClientId=self.physics_client)
            self.particle_positions.append(pos)


class Room(dict[str, tuple[Any, tuple[float, float, float, float]]]):
    """
    A dictionary-like container for CAD geometry and its visualization metadata.

    Keys are unique names for the items, and values are tuples of (geometry, rgba_tuple).
    """

    def __init__(self, config: Optional["AppConfig"] = None, is_simulate: bool = False):
        """Initialize the room with an optional application configuration."""
        super().__init__()
        self.config = config
        self.is_simulate = is_simulate
        self._labels: list[tuple[str, str, Any, TextArgs]] = []
        self.gravity: tuple[float, float, float] = (0.0, 0.0, -9.81)

    def add(
        self,
        name: str,
        geometry: Any,
        color: Optional[Union[str, ColorType, tuple[float, float, float]]] = None,
        alpha: float = 1.0,
    ) -> None:
        """
        Add a geometry item (Part, Sketch, Wire, or Builder) to the room.

        Args:
            name: Unique name for the item.
            geometry: The CAD object or build123d builder.
            color: The color name, enum member, RGB 3-tuple, or None to use default.
            alpha: Transparency value from 0.0 to 1.0.
        """
        if name in self:
            raise ValueError(f"An item with the name '{name}' already exists in the Room.")

        # Support BuildPart objects by extracting the underlying geometry
        if isinstance(geometry, BuildPart):
            geometry = geometry.part
        elif isinstance(geometry, BuildSketch):
            geometry = geometry.sketch
        elif isinstance(geometry, BuildLine):
            geometry = geometry.line

        default_rgb = self.config.color[:3] if self.config else (1.0, 1.0, 1.0)

        final_color: Union[str, ColorType, tuple[float, float, float]] = ColorType.GREY
        final_alpha = alpha

        if color is not None:
            final_color = color
        elif self.config:
            final_color = self.config.color[:3]
            if alpha == 1.0:
                final_alpha = self.config.color[3]

        rgba = get_rgba_color(final_color, final_alpha, default_rgb)
        self[name] = (geometry, rgba)

    def add_label(self, name: str, text: str, location: Any, options: Optional[TextArgs] = None) -> None:
        """Add a camera-aligned text annotation at a 3D location."""
        self._labels.append((name, text, Vector(location), options or TextArgs()))

    @property
    def compound(self) -> Compound:
        """Return the room contents as a single build123d Compound."""
        children = []

        for name, (obj, rgba) in self.items():
            if hasattr(obj, "label"):
                # Setting the label allows visualization tools like ocp_vscode to identify parts.
                setattr(obj, "label", name)
                # Setting the color metadata for visualization.
                if hasattr(obj, "color"):
                    setattr(obj, "color", rgba)
                children.append(obj)
            else:
                raise ValueError(f"Item '{name}' in Room could not be converted to a build123d object.")

        return Compound(children=children)

    def export_diagram(self, path: Union[str, Path, io.BytesIO], options: Optional["DiagramOptions"] = None) -> None:
        """Export the room contents to a file, inferring format from extension."""
        if isinstance(path, (str, Path)) and not str(path).lower().endswith(".svg"):
            raise ValueError(f"Unsupported diagram format for '{path}'. Only .svg is supported.")

        svg_opts = self._parse_options(options)
        look_from, look_at, up_vector = self._get_projection_vectors(svg_opts)
        drawing = Drawing(
            self.compound,
            look_from=look_from,
            look_at=look_at,
            look_up=up_vector,
            with_hidden=svg_opts.get("show_hidden", False),
        )
        export_shapes = [drawing.visible_lines]

        if svg_opts.get("show_hidden"):
            export_shapes.append(drawing.hidden_lines)

        # Get the bounding box of the projected geometry to calculate triad placement.
        model_bb = drawing.visible_lines.bounding_box()

        # Add debug axes if requested, placed in the corner and scaled to the viewpane.
        if svg_opts.get("show_axes"):
            axes = self._create_debug_axes(model_bb, look_from, look_at, up_vector)
            if axes:
                export_shapes.append(axes)

        # Define the view plane for projecting annotations to match the Drawing's 2D space.
        # The view direction is the vector from the target back to the camera.
        view_dir = (look_from - look_at).normalized()
        view_x = up_vector.cross(view_dir).normalized()
        view_plane = Plane(origin=look_at, x_dir=view_x, z_dir=view_dir)

        export_shapes.extend(self._project_labels(view_plane))

        # Combine projected geometry and flat annotations for final scaling and export.
        final_drawing = Compound(children=export_shapes)
        bb = final_drawing.bounding_box()

        # ExportSVG uses 'scale' to determine physical dimensions from model units.
        width = bb.max.X - bb.min.X
        height = bb.max.Y - bb.min.Y
        if "width" in svg_opts and width > 0:
            svg_opts["scale"] = svg_opts.pop("width") / width
        elif "height" in svg_opts and height > 0:
            svg_opts["scale"] = svg_opts.pop("height") / height

        # Filter for fields explicitly supported by build123d's ExportSVG class.
        supported_fields = {
            "unit",
            "scale",
            "margin",
            "fit_to_stroke",
            "precision",
            "fill_color",
            "line_weight",
            "line_color",
            "line_type",
            "dot_length",
        }
        filtered_opts = {k: v for k, v in svg_opts.items() if k in supported_fields}

        exporter = ExportSVG(**filtered_opts)
        exporter.add_shape(final_drawing)
        exporter.write(cast(Any, path))

    def _parse_options(self, options: Optional["DiagramOptions"]) -> dict[str, Any]:
        """Extract and normalize diagram options from Pydantic models or mock objects."""
        if not options:
            return {}

        if hasattr(options, "model_dump"):
            # Use aliases to map stroke_width/color to line_weight/color
            return options.model_dump(by_alias=True, exclude_none=True)

        # Fallback for simple objects or mocks
        fields = [
            "width",
            "height",
            "stroke_width",
            "stroke_color",
            "margin",
            "view_from",
            "projection_dir",
            "projection_origin",
            "show_axes",
            "show_hidden",
            "look_up",
        ]
        svg_opts = {}
        for field in fields:
            if hasattr(options, field):
                val = getattr(options, field)
                if val is not None:
                    svg_opts[field] = val

        # Manual mapping for mock objects if they don't use aliases
        if "stroke_width" in svg_opts:
            svg_opts["line_weight"] = svg_opts.pop("stroke_width")
        if "stroke_color" in svg_opts:
            svg_opts["line_color"] = svg_opts.pop("stroke_color")

        return svg_opts

    def _get_projection_vectors(self, svg_opts: dict[str, Any]) -> tuple[Vector, Vector, Vector]:
        # Calculate the camera projection direction and a stable "up" vector.
        look_at = Vector(self.compound.center())
        if svg_opts.get("projection_dir") is not None:
            look_at = Vector(svg_opts["projection_dir"])

        view_dir = Vector(-1, -1, 1)  # Default ISO
        view_from = svg_opts.get("view_from", "iso").lower()

        mapping = {
            "top": Vector(0, 0, 1),
            "bottom": Vector(0, 0, -1),
            "front": Vector(0, -1, 0),
            "rear": Vector(0, 1, 0),
            "left": Vector(-1, 0, 0),
            "right": Vector(1, 0, 0),
            "iso": Vector(-1, -1, 1),
        }

        if view_from != "iso":
            parts = view_from.replace(",", " ").split()
            combined = Vector(0, 0, 0)
            for p in parts:
                if p in mapping:
                    combined += mapping[p]
            if combined.length > 0:
                view_dir = combined

        # Scale the view direction based on the bounding box to ensure the camera
        # is outside the model. Using 2x the diagonal provides a safe distance.
        bb = self.compound.bounding_box()
        distance = bb.diagonal * 2 if bb.diagonal > 0 else 1000.0
        look_from = look_at + (view_dir.normalized() * distance)
        if svg_opts.get("projection_origin") is not None:
            look_from = Vector(svg_opts["projection_origin"])

        view_dir_norm = (look_from - look_at).normalized()

        z_axis = Vector(0, 0, 1)
        up_vector = Vector(svg_opts.get("look_up", z_axis))
        if abs(view_dir_norm.dot(up_vector)) > 0.99 and "look_up" not in svg_opts:
            up_vector = Vector(0, 1, 0)
        return look_from, look_at, up_vector

    def _project_labels(self, view_plane: Plane) -> list[Sketch]:
        """Project 3D annotations into 2D sketches aligned with the view plane."""
        projected_sketches = []
        for _, text, loc, opts in self._labels:
            local_loc = cast(Vector, view_plane.to_local_coords(loc))
            l_loc = cast(Vector, local_loc)
            with BuildSketch() as s:
                Text(
                    text,
                    font_size=opts.font_size,
                    font=opts.font,
                    font_style=opts.font_style,
                    align=opts.align,
                )

            # Place the 2D text at the projected X/Y coordinates.
            projected_sketches.append(s.sketch.moved(Location((l_loc.X, l_loc.Y))))
        return projected_sketches

    def _create_debug_axes(
        self,
        model_bb: BoundBox,
        look_from: Vector,
        look_at: Vector,
        up_vector: Vector,
    ) -> Optional[Any]:
        """Create a projected coordinate system triad scaled and positioned for the viewpane."""
        # Create our own axes and arrows to ensure correct orientation and avoid issues with make_triad.
        # The base_axis_length will be scaled later by axes_scale.
        base_axis_length = 1.0
        arrow_length_factor = 0.15
        arrow_width_factor = 0.07

        axes = [Vector(1, 0, 0), Vector(0, 1, 0), Vector(0, 0, 1)]
        custom_triad_parts = []
        for direction in axes:
            tip = direction * base_axis_length
            custom_triad_parts.append(Edge.make_line(Vector(0, 0, 0), tip))
            custom_triad_parts.extend(self._create_arrowhead(tip, direction, arrow_length_factor, arrow_width_factor))

        axes_triad = Compound(children=custom_triad_parts).moved(Location(look_at))
        axes_drawing = Drawing(axes_triad, look_from=look_from, look_at=look_at, look_up=up_vector)
        projected_axes = axes_drawing.visible_lines

        # Calculate projection for labels to ensure they face the camera.
        view_dir = (look_from - look_at).normalized()
        view_x = up_vector.cross(view_dir).normalized()
        view_plane = Plane(origin=look_at, x_dir=view_x, z_dir=view_dir)

        def project_to_2d(p3d: Vector) -> Vector:
            # Project world vectors (relative to triad origin) to the view plane.
            local = cast(Vector, view_plane.to_local_coords(look_at + p3d))
            return Vector(local.X, local.Y)

        # Create 2D text labels at the projected endpoints of the 3D unit vectors.
        # This ensures they are always flat to the viewpane (facing the camera).
        labels = []
        label_margin_factor = 0.1  # Small margin beyond the arrow tip
        label_offset_for_direct_view = 0.5  # Offset factor relative to font_size
        label_font_size = 0.2  # From Text constructor

        for text, vec in [
            ("X", Vector(base_axis_length + label_margin_factor, 0, 0)),
            ("Y", Vector(0, base_axis_length + label_margin_factor, 0)),
            ("Z", Vector(0, 0, base_axis_length + label_margin_factor)),
        ]:
            p2d = cast(Vector, project_to_2d(vec))
            # If the axis is pointing almost directly at the camera, apply a small 2D offset
            if view_dir.dot(vec.normalized()) > 0.95:  # Check 3D vector alignment with view direction
                p2d += Vector(
                    label_font_size * label_offset_for_direct_view, label_font_size * label_offset_for_direct_view, 0
                )

            with BuildSketch() as s:
                Text(text, font_size=label_font_size, align=(Align.CENTER, Align.CENTER))
            labels.append(s.sketch.moved(Location((p2d.X, p2d.Y))))

        # Combine the projected lines with the camera-facing labels.
        projected_axes = Compound(children=[projected_axes] + labels)

        # Scale to ~15% of the model's larger dimension.
        m_width = model_bb.max.X - model_bb.min.X
        m_height = model_bb.max.Y - model_bb.min.Y
        model_dim = max(m_width, m_height)

        axes_bb = projected_axes.bounding_box()
        a_width = axes_bb.max.X - axes_bb.min.X
        a_height = axes_bb.max.Y - axes_bb.min.Y
        axes_dim = max(a_width, a_height)

        # Size of the debug axes as a ratio of model size
        projection_scale = 0.15

        if axes_dim > 0:
            axes_scale = (model_dim * projection_scale) / axes_dim
            projected_axes = projected_axes.scale(axes_scale)

            # Move to bottom-left corner.
            new_axes_bb = projected_axes.bounding_box()
            offset = Vector(
                model_bb.min.X - new_axes_bb.min.X,
                model_bb.min.Y - new_axes_bb.min.Y,
            )
            return projected_axes.translate(offset)
        return None

    def _create_arrowhead(self, tip: Vector, direction: Vector, length: float, width: float) -> list[Edge]:
        """Create a V-shaped arrowhead pointing along direction at tip."""
        # Find a vector perpendicular to direction to define the 'width' of the V.
        # We try (0,0,1) first, unless direction is also along Z.
        z_axis = Vector(0, 0, 1)
        cross_p = z_axis.cross(direction)
        if cross_p.length < 1e-5:
            cross_p = Vector(0, 1, 0).cross(direction)
        perp = cross_p.normalized()

        p1 = tip - (direction * length) + (perp * width)
        p2 = tip - (direction * length) - (perp * width)
        return [Edge.make_line(tip, p1), Edge.make_line(tip, p2)]

    def disconnect_joints(self) -> None:
        """Clear all URDF joint properties from shapes in the room as a precautionary step."""
        for geom, _ in self.values():
            u_geom = cast(URDFShape, geom)
            if hasattr(u_geom, "urdf_parent"):
                u_geom.urdf_parent = None
            if hasattr(u_geom, "urdf_joint_type"):
                u_geom.urdf_joint_type = None
            if hasattr(u_geom, "urdf_joint_axis"):
                u_geom.urdf_joint_axis = None
            if hasattr(u_geom, "urdf_joint_lower"):
                u_geom.urdf_joint_lower = None
            if hasattr(u_geom, "urdf_joint_upper"):
                u_geom.urdf_joint_upper = None

    def translate_joints(self) -> None:
        """Map build123d joints defined on shapes in the room to URDF-compatible properties."""
        self.disconnect_joints()

        def format_coord(v: float) -> str:
            return str(int(v)) if v.is_integer() else f"{v:.6f}".rstrip("0").rstrip(".")

        # Map from python object id of geometry to its label/name in the room
        geom_to_label = {}
        for name, (geom, _) in self.items():
            u_geom = cast(URDFShape, geom)
            label = getattr(u_geom, "urdf_label", name)
            geom_to_label[id(u_geom)] = label

        # Also populate urdf_label for all room geometries if not already set, to make sure
        # they are recognized as URDF links.
        for name, (geom, _) in self.items():
            u_geom = cast(URDFShape, geom)
            if not getattr(u_geom, "urdf_label", None):
                u_geom.urdf_label = name

        for name, (geom, _) in self.items():
            u_geom = cast(URDFShape, geom)
            joints = getattr(u_geom, "joints", None)
            if not isinstance(joints, dict):
                continue

            for joint in joints.values():
                if getattr(joint, "connected_to", None) is not None:
                    parent_geom = u_geom
                    child_geom = cast(URDFShape, joint.connected_to.parent)

                    parent_label = geom_to_label.get(id(parent_geom))
                    child_label = geom_to_label.get(id(child_geom))

                    if parent_label is not None and child_label is not None:
                        child_geom.urdf_parent = parent_label
                        child_joint = joint.connected_to

                        # Map joint types and attributes
                        self._map_joint_properties(child_geom, child_joint, format_coord)

    def _map_joint_properties(self, child_geom: URDFShape, child_joint: Any, format_coord: Any) -> None:
        """Map build123d joint attributes or custom overrides to child geometry properties."""
        if hasattr(child_joint, "urdf_joint_type"):
            u_joint = cast(URDFShape, child_joint)
            child_geom.urdf_joint_type = u_joint.urdf_joint_type
            if hasattr(u_joint, "urdf_joint_axis"):
                child_geom.urdf_joint_axis = u_joint.urdf_joint_axis
            if hasattr(u_joint, "urdf_joint_lower"):
                child_geom.urdf_joint_lower = u_joint.urdf_joint_lower
            if hasattr(u_joint, "urdf_joint_upper"):
                child_geom.urdf_joint_upper = u_joint.urdf_joint_upper
        else:
            match child_joint:
                case RigidJoint():
                    child_geom.urdf_joint_type = "fixed"
                case RevoluteJoint():
                    is_continuous = False
                    if getattr(child_joint, "angular_range", None) is not None:
                        lower, upper = child_joint.angular_range
                        if abs(upper - lower) >= 360.0:
                            is_continuous = True

                    if is_continuous:
                        child_geom.urdf_joint_type = "continuous"
                    else:
                        child_geom.urdf_joint_type = "revolute"
                        if getattr(child_joint, "angular_range", None) is not None:
                            child_geom.urdf_joint_lower = math.radians(child_joint.angular_range[0])
                            child_geom.urdf_joint_upper = math.radians(child_joint.angular_range[1])

                    if getattr(child_joint, "relative_axis", None) is not None:
                        dir_vec = child_joint.relative_axis.direction
                        child_geom.urdf_joint_axis = (
                            f"{format_coord(dir_vec.X)} {format_coord(dir_vec.Y)} {format_coord(dir_vec.Z)}"
                        )
                case LinearJoint():
                    child_geom.urdf_joint_type = "prismatic"
                    if getattr(child_joint, "relative_axis", None) is not None:
                        dir_vec = child_joint.relative_axis.direction
                        child_geom.urdf_joint_axis = (
                            f"{format_coord(dir_vec.X)} {format_coord(dir_vec.Y)} {format_coord(dir_vec.Z)}"
                        )
                    if getattr(child_joint, "linear_range", None) is not None:
                        child_geom.urdf_joint_lower = child_joint.linear_range[0] * 0.001
                        child_geom.urdf_joint_upper = child_joint.linear_range[1] * 0.001
                case BallJoint():
                    child_geom.urdf_joint_type = "spherical"

    def reset_camera(self, physics_client: int, view_from: str = "iso") -> None:
        """Reset the PyBullet visualizer camera based on a view string."""
        bb = self.compound.bounding_box()
        center_m = [
            bb.center().X * 0.001,
            bb.center().Y * 0.001,
            bb.center().Z * 0.001,
        ]
        max_dim = max(
            (bb.max.X - bb.min.X) * 0.001,
            (bb.max.Y - bb.min.Y) * 0.001,
            (bb.max.Z - bb.min.Z) * 0.001,
        )
        camera_distance = max(max_dim * 2.0, 0.3)

        mapping = {
            "iso": (45.0, -30.0),
            "top": (0.0, -89.0),
            "bottom": (0.0, 89.0),
            "front": (0.0, 0.0),
            "rear": (180.0, 0.0),
            "left": (270.0, 0.0),
            "right": (90.0, 0.0),
        }

        view_from_lower = view_from.lower()
        yaw, pitch = mapping.get(view_from_lower, (45.0, -30.0))
        parts = view_from_lower.replace(",", " ").split()
        if len(parts) > 1:
            yaws = []
            pitches = []
            for part in parts:
                if part in mapping:
                    yaws.append(mapping[part][0])
                    pitches.append(mapping[part][1])
            if yaws and pitches:
                yaw = sum(yaws) / len(yaws)
                pitch = sum(pitches) / len(pitches)

        p.resetDebugVisualizerCamera(
            cameraDistance=camera_distance,
            cameraYaw=yaw,
            cameraPitch=pitch,
            cameraTargetPosition=center_m,
            physicsClientId=physics_client,
        )

    def export_urdf(self, path: Union[str, Path, io.StringIO], project_name: str) -> None:
        """Export a combined URDF from a Room object."""
        import yaml
        from build123d import CenterOf

        self.translate_joints()

        # Build map of labels to geometries to resolve relative joint coordinates
        label_to_geom = {}
        for geom, _ in self.values():
            u_geom = cast(URDFShape, geom)
            label = getattr(u_geom, "urdf_label", None)
            if label:
                label_to_geom[label] = u_geom

        template_path = Path(__file__).parent.parent / "urdf_template.yaml"
        with open(template_path, "r") as f:
            templates = yaml.safe_load(f)
        robot_template = templates["robot_template"].strip()
        link_template = templates["link_template"].strip()
        joint_template = templates["joint_template"].strip()
        axis_limit_template = templates["axis_limit_template"].strip()
        collision_template = templates["collision_template"].strip()

        links_info = []
        for geom, rgba in self.values():
            u_geom = cast(URDFShape, geom)
            label = getattr(u_geom, "urdf_label", None)
            if not label:
                continue

            parent = getattr(u_geom, "urdf_parent", None)
            joint_type = getattr(u_geom, "urdf_joint_type", "fixed")
            joint_axis = getattr(u_geom, "urdf_joint_axis", "0 0 1")
            density = getattr(u_geom, "urdf_density", 1.0)
            collision_type = getattr(u_geom, "urdf_collision_type", "convex")

            # Compute relative location if the link has a parent
            parent_label = getattr(u_geom, "urdf_parent", None)
            if parent_label and parent_label in label_to_geom:
                parent_geom = label_to_geom[parent_label]
                rel_loc = parent_geom.location.inverse() * u_geom.location
            else:
                rel_loc = u_geom.location

            pos = rel_loc.position
            xyz = [pos.X * 0.001, pos.Y * 0.001, pos.Z * 0.001]
            rpy = [
                math.radians(rel_loc.orientation.X),
                math.radians(rel_loc.orientation.Y),
                math.radians(rel_loc.orientation.Z),
            ]

            # Invert the translation to get the local shape centered at local origin

            local_shape = u_geom.location.inverse() * u_geom

            # Mass and inertia calculations using local shape and density
            density_g_mm3 = density * 1e-3
            volume_mm3 = local_shape.volume
            mass_kg = volume_mm3 * density_g_mm3 * 1e-3

            com = local_shape.center(CenterOf.MASS)
            com_m = [com.X * 0.001, com.Y * 0.001, com.Z * 0.001]

            raw_inertia = local_shape.matrix_of_inertia
            scale_factor = density * 1e-12

            com_m = [com.X * 0.001, com.Y * 0.001, com.Z * 0.001]

            raw_inertia = local_shape.matrix_of_inertia
            scale_factor = density * 1e-12

            ixx = raw_inertia[0][0] * scale_factor
            ixy = raw_inertia[0][1] * scale_factor
            ixz = raw_inertia[0][2] * scale_factor
            iyy = raw_inertia[1][1] * scale_factor
            iyz = raw_inertia[1][2] * scale_factor
            izz = raw_inertia[2][2] * scale_factor

            rgba_str = f"{rgba[0]:.6f} {rgba[1]:.6f} {rgba[2]:.6f} {rgba[3]:.6f}"
            joint_lower = getattr(u_geom, "urdf_joint_lower", -3.14159)
            joint_upper = getattr(u_geom, "urdf_joint_upper", 3.14159)

            links_info.append(
                {
                    "name": label,
                    "parent": parent,
                    "joint_type": joint_type,
                    "joint_axis": joint_axis,
                    "joint_lower": joint_lower,
                    "joint_upper": joint_upper,
                    "xyz": xyz,
                    "rpy": rpy,
                    "mass_kg": mass_kg,
                    "com_x": com_m[0],
                    "com_y": com_m[1],
                    "com_z": com_m[2],
                    "ixx": ixx,
                    "ixy": ixy,
                    "ixz": ixz,
                    "iyy": iyy,
                    "iyz": iyz,
                    "izz": izz,
                    "obj_filename": f"{label}.obj",
                    "rgba_str": rgba_str,
                    "collision_type": collision_type,
                }
            )

        if not links_info:
            return

        # Validate that the URDF has exactly one root link
        roots = [link["name"] for link in links_info if link["parent"] is None]
        if len(roots) > 1:
            raise ValueError(f"URDF file with multiple root links found: {' '.join(roots)}")
        elif len(roots) == 0:
            raise ValueError("URDF file with no root links found (contains cycles).")

        links_strings = []
        for link in links_info:
            c_type = link["collision_type"]
            if c_type == "none":
                collision_section = ""
            else:
                collision_section = (
                    collision_template.format(
                        project_name=project_name,
                        obj_filename=link["obj_filename"],
                        collision_type=c_type,
                    )
                    + "\n"
                )

            links_strings.append(
                link_template.format(
                    link_name=link["name"],
                    com_x=link["com_x"],
                    com_y=link["com_y"],
                    com_z=link["com_z"],
                    mass_kg=link["mass_kg"],
                    ixx=link["ixx"],
                    ixy=link["ixy"],
                    ixz=link["ixz"],
                    iyy=link["iyy"],
                    iyz=link["iyz"],
                    izz=link["izz"],
                    project_name=project_name,
                    obj_filename=link["obj_filename"],
                    rgba=link["rgba_str"],
                    collision_section=collision_section,
                )
            )

        joints_strings = []
        for link in links_info:
            if link["parent"] is not None:
                axis_limit_str = ""
                if link["joint_type"] in ("revolute", "prismatic"):
                    axis_limit_str = (
                        axis_limit_template.format(
                            joint_axis=link["joint_axis"], lower=link["joint_lower"], upper=link["joint_upper"]
                        )
                        + "\n  "
                    )
                elif link["joint_type"] in ("continuous", "planar"):
                    axis_limit_str = f'  <axis xyz="{link["joint_axis"]}"/>\n  '

                joints_strings.append(
                    joint_template.format(
                        parent_name=link["parent"],
                        child_name=link["name"],
                        joint_type=link["joint_type"],
                        xyz_x=link["xyz"][0],
                        xyz_y=link["xyz"][1],
                        xyz_z=link["xyz"][2],
                        rpy_r=link["rpy"][0],
                        rpy_p=link["rpy"][1],
                        rpy_y=link["rpy"][2],
                        axis_limit=axis_limit_str,
                    )
                )

        urdf_content = robot_template.format(
            robot_name=project_name,
            links="\n".join(links_strings),
            joints="\n".join(joints_strings),
        )

        if isinstance(path, (str, Path)):
            with open(path, "w") as f:
                f.write(urdf_content)
        else:
            path.write(urdf_content)

    def _log_rerun(
        self,
        transforms: dict[str, tuple[list[float], list[float]]],
        particle_positions: list[list[float]],
        particle_colors: Optional[list[list[float]]] = None,
        particle_radii: Optional[list[float]] = None,
        step_idx: Optional[int] = None,
    ) -> None:
        """Log the given state data to Rerun."""
        if step_idx is not None:
            rr.set_time("step", sequence=step_idx)

        # Log link transforms
        for label, (pos, orn) in transforms.items():
            rr.log(
                f"world/{label}",
                rr.Transform3D(
                    translation=pos,
                    rotation=rr.Quaternion(xyzw=orn),
                    scale=0.001,
                ),
            )

        # Log particles
        if particle_positions:
            active_indices = [idx for idx, pos in enumerate(particle_positions) if pos[2] < 100.0]
            if active_indices:
                filtered_positions = [particle_positions[idx] for idx in active_indices]
                filtered_radii = (
                    [particle_radii[idx] for idx in active_indices] if particle_radii is not None else 0.003
                )
                colors_arg = [128, 204, 255, 178]
                if particle_colors:
                    colors_arg = []
                    for idx in active_indices:
                        col = particle_colors[idx]
                        is_float = any(isinstance(c, float) for c in col) or all(c <= 1.0 for c in col)
                        if is_float:
                            colors_arg.append([int(round(c * 255.0)) for c in col])
                        else:
                            colors_arg.append([int(c) for c in col])

                rr.log(
                    "world/particles",
                    rr.Points3D(
                        positions=filtered_positions,
                        radii=filtered_radii,
                        colors=colors_arg,
                    ),
                )

    def _copy_project_assets(self, build_proj_dir: str, proj_dir: str) -> None:
        """Copy required OBJ files for the room geometries to the temporary directory."""
        for geom, _ in self.values():
            u_geom = cast(URDFShape, geom)
            label = getattr(u_geom, "urdf_label", None)
            if label:
                real_obj_path = os.path.join(build_proj_dir, f"{label}.obj")
                temp_obj_path = os.path.join(proj_dir, f"{label}.obj")
                if os.path.exists(real_obj_path):
                    shutil.copy(real_obj_path, temp_obj_path)
                else:
                    raise FileNotFoundError(f"Required OBJ file not found for simulation: {real_obj_path}")

    def _init_simulation_objects(
        self,
        physics_client: int,
        body_id: int,
        proj_dir: str,
        urdf_path: str,
    ) -> dict[str, int]:
        """Configure motor controls, log static assets, and setup concave collisions for Room simulation."""
        rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
        num_joints = p.getNumJoints(body_id, physicsClientId=physics_client)
        is_real = _is_real_physics_client(physics_client)
        # Configure collision filter for base and all links to group CONTAINER, mask ALL to allow particle collision
        if is_real:
            p.setCollisionFilterGroupMask(
                body_id, -1, CollisionGroup.CONTAINER, CollisionMask.ALL, physicsClientId=physics_client
            )
            for i in range(num_joints):
                p.setCollisionFilterGroupMask(
                    body_id, i, CollisionGroup.CONTAINER, CollisionMask.ALL, physicsClientId=physics_client
                )

        joint_name_to_index = {}
        for i in range(num_joints):
            info = p.getJointInfo(body_id, i, physicsClientId=physics_client)
            joint_name = info[1].decode("utf-8")
            joint_name_to_index[joint_name] = i

        label_to_link_idx = {}
        for geom, _ in self.values():
            u_geom = cast(URDFShape, geom)
            label = getattr(u_geom, "urdf_label", None)
            if label:
                parent_label = getattr(u_geom, "urdf_parent", None)
                if not parent_label:
                    label_to_link_idx[label] = -1
                else:
                    joint_name = f"{parent_label}_to_{label}"
                    if joint_name in joint_name_to_index:
                        label_to_link_idx[label] = joint_name_to_index[joint_name]

        # Parse URDF XML to find concave collision links
        import xml.etree.ElementTree as ET

        concave_links = set()
        if urdf_path and os.path.exists(urdf_path):
            try:
                tree = ET.parse(urdf_path)
                root = tree.getroot()
                for link_node in root.findall(".//link"):
                    link_name = link_node.attrib.get("name")
                    col_type_node = link_node.find(".//collision/collision_type")
                    if col_type_node is not None and col_type_node.text == "concave":
                        concave_links.add(link_name)
            except Exception:
                pass

        # Configure concave trimeshes for links marked concave
        for link_name in concave_links:
            if link_name in label_to_link_idx:
                link_idx = label_to_link_idx[link_name]
                # Disable default collision in PyBullet
                p.setCollisionFilterGroupMask(body_id, link_idx, 0, 0, physicsClientId=physics_client)

                # Fetch shape details from PyBullet
                shapes = p.getCollisionShapeData(body_id, link_idx, physicsClientId=physics_client)
                for shape in shapes:
                    geom_type = shape[2]
                    if geom_type == p.GEOM_MESH:
                        mesh_scale = shape[3]

                        # Locate local mesh OBJ file in proj_dir
                        local_mesh_path = os.path.join(proj_dir, f"{link_name}.obj")
                        if not os.path.exists(local_mesh_path):
                            shape_filename = shape[4].decode("utf-8")
                            base_filename = os.path.basename(shape_filename)
                            local_mesh_path = os.path.join(proj_dir, base_filename)

                        if os.path.exists(local_mesh_path):
                            # Get link world position and orientation (inertial frame)
                            if link_idx == -1:
                                link_pos, link_orn = p.getBasePositionAndOrientation(
                                    body_id, physicsClientId=physics_client
                                )
                            else:
                                state = p.getLinkState(body_id, link_idx, physicsClientId=physics_client)
                                link_pos = state[0]
                                link_orn = state[1]

                            # Account for shape local offset relative to the link's inertial frame
                            local_pos = shape[5]
                            local_orn = shape[6]
                            world_pos, world_orn = p.multiplyTransforms(link_pos, link_orn, local_pos, local_orn)

                            # Create concave trimesh static body at correct world coordinates
                            col_id = p.createCollisionShape(
                                shapeType=p.GEOM_MESH,
                                fileName=local_mesh_path,
                                flags=p.GEOM_FORCE_CONCAVE_TRIMESH,
                                meshScale=mesh_scale,
                                physicsClientId=physics_client,
                            )
                            static_body_id = p.createMultiBody(
                                baseMass=0.0,
                                baseCollisionShapeIndex=col_id,
                                basePosition=world_pos,
                                baseOrientation=world_orn,
                                physicsClientId=physics_client,
                            )
                            # Enable collision with particles (group PARTICLE, mask CONTAINER)
                            if is_real:
                                p.setCollisionFilterGroupMask(
                                    static_body_id,
                                    -1,
                                    CollisionGroup.CONTAINER,
                                    CollisionMask.ALL,
                                    physicsClientId=physics_client,
                                )
                            # Disable collisions between all links of the main body and this separate static collision body
                            p.setCollisionFilterPair(body_id, static_body_id, -1, -1, 0, physicsClientId=physics_client)
                            for l_idx in range(num_joints):
                                p.setCollisionFilterPair(
                                    body_id, static_body_id, l_idx, -1, 0, physicsClientId=physics_client
                                )

        for geom, _ in self.values():
            u_geom = cast(URDFShape, geom)
            label = getattr(u_geom, "urdf_label", None)
            parent_label = getattr(u_geom, "urdf_parent", None)
            if label and parent_label:
                joint_name = f"{parent_label}_to_{label}"
                if joint_name in joint_name_to_index:
                    idx = joint_name_to_index[joint_name]
                    motor_type = getattr(u_geom, "urdf_motor_type", None)
                    if motor_type:
                        target = getattr(u_geom, "urdf_motor_target", 0.0)
                        force = getattr(u_geom, "urdf_motor_force", 10.0)
                        if motor_type == "velocity":
                            p.setJointMotorControl2(
                                bodyUniqueId=body_id,
                                jointIndex=idx,
                                controlMode=p.VELOCITY_CONTROL,
                                targetVelocity=target,
                                force=force,
                                physicsClientId=physics_client,
                            )
                        elif motor_type == "torque":
                            p.setJointMotorControl2(
                                bodyUniqueId=body_id,
                                jointIndex=idx,
                                controlMode=p.TORQUE_CONTROL,
                                force=target,
                                physicsClientId=physics_client,
                            )
                    else:
                        p.setJointMotorControl2(
                            bodyUniqueId=body_id,
                            jointIndex=idx,
                            controlMode=p.VELOCITY_CONTROL,
                            force=0,
                            physicsClientId=physics_client,
                        )

        for geom, _ in self.values():
            u_geom = cast(URDFShape, geom)
            label = getattr(u_geom, "urdf_label", None)
            if label:
                temp_obj_path = os.path.join(proj_dir, f"{label}.obj")
                if os.path.exists(temp_obj_path):
                    rr.log(f"world/{label}", rr.Asset3D(path=temp_obj_path), static=True)

        return label_to_link_idx

    def _init_rerun(
        self,
        proj_name: str,
        spawn_viewer: bool,
        rerun_port: Optional[int] = None,
    ) -> None:
        """Initialize Rerun connection, connecting to an existing viewer or spawning a new one."""
        rr.init(proj_name or "pybullet_simulation")
        if not spawn_viewer:
            return

        def is_port_in_use(port: int) -> bool:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.1)
                    return s.connect_ex(("127.0.0.1", port)) == 0
            except Exception:
                return False

        target_port = rerun_port if rerun_port is not None else 9876
        if is_port_in_use(target_port):
            rr.connect_grpc(f"rerun+http://127.0.0.1:{target_port}/proxy")
        else:
            rr.spawn(port=target_port)

    def simulate(
        self,
        provider_hooks: dict[Simulate, Callable[..., Any]],
        proj_name: str,
        sim_target: str,
        steps: int,
        manager: Any,
        logger: Any,
        build_dir: str = "build",
        save_rrd: Optional[str] = None,
        rerun_port: Optional[int] = None,
        spawn_viewer: bool = True,
    ) -> None:
        """Run a PyBullet physics simulation for the room geometries."""
        from provider import Provider
        from list import Lister

        logger.print("Running Simulation (Ctrl-C to exit)...", symbol="🤖")

        if not self:
            raise ValueError("Cannot simulate an empty Room.")

        Provider.validate_simulate_hooks(provider_hooks)

        temp_dir = tempfile.mkdtemp()
        try:
            # Create the simulation project assets
            proj_dir = os.path.join(temp_dir, proj_name)
            os.makedirs(proj_dir, exist_ok=True)
            build_proj_dir = os.path.join(build_dir, proj_name)
            self.translate_joints()
            self._copy_project_assets(build_proj_dir, proj_dir)

            # Determine URDF filename using Lister
            lister = Lister(manager, logger)
            urdf_rel_path = lister.get_urdf_output(sim_target)
            real_urdf_path = os.path.join(build_dir, urdf_rel_path)
            temp_urdf_filename = os.path.basename(urdf_rel_path)
            urdf_path = os.path.join(temp_dir, temp_urdf_filename)

            if os.path.exists(real_urdf_path):
                shutil.copy(real_urdf_path, urdf_path)
            else:
                raise FileNotFoundError(f"Required URDF file not found for simulation: {real_urdf_path}")

            physics_client = p.connect(p.DIRECT)

            self._init_rerun(proj_name, spawn_viewer, rerun_port)

            if save_rrd:
                rr.save(save_rrd)

            try:
                is_real = _is_real_physics_client(physics_client)
                # Temporarily disable rendering to make particle spawning fast
                if is_real:
                    p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 0, physicsClientId=physics_client)

                p.setGravity(*self.gravity, physicsClientId=physics_client)
                if is_real:
                    p.setPhysicsEngineParameter(numSubSteps=2, physicsClientId=physics_client)
                body_id = p.loadURDF(urdf_path, useFixedBase=True, physicsClientId=physics_client)
                if body_id < 0:
                    raise RuntimeError("PyBullet failed to load the URDF.")

                label_to_link_idx = self._init_simulation_objects(physics_client, body_id, proj_dir, urdf_path)
                state_tracker = BulletStateTracker(body_id, physics_client, label_to_link_idx)

                # Setup Hooks
                setup_hook = provider_hooks.get(Simulate.SETUP, None)
                if setup_hook:
                    setup_hook(body_id, physics_client, sim_target)

                # Re-enable rendering
                if is_real:
                    p.configureDebugVisualizer(p.COV_ENABLE_RENDERING, 1, physicsClientId=physics_client)

                is_logging_enabled = spawn_viewer or (save_rrd is not None)

                for step_idx in range(steps):
                    # Step Hooks
                    step_hook = provider_hooks.get(Simulate.STEP, None)
                    terminated = False
                    if step_hook:
                        res = step_hook(body_id, physics_client, step_idx, sim_target)
                        if isinstance(res, str):
                            logger.print(f"Simulation terminated: {res}", symbol="🛑")
                            terminated = True

                    # Fetch state data of step_idx
                    if is_logging_enabled:
                        state_tracker.update_state()

                    # Step physics
                    if not terminated:
                        p.stepSimulation(physicsClientId=physics_client)

                    if is_logging_enabled:
                        self._log_rerun(
                            state_tracker.transforms,
                            state_tracker.particle_positions,
                            state_tracker.particle_colors,
                            particle_radii=state_tracker.particle_radii,
                            step_idx=step_idx,
                        )

                    if terminated:
                        # Simulation early termination conditions met.
                        break

                # Teardown Hooks
                teardown_hook = provider_hooks.get(Simulate.TEARDOWN, None)
                if teardown_hook:
                    teardown_hook(body_id, physics_client, sim_target)

            except KeyboardInterrupt:
                logger.print("Simulation stopped.", symbol="💥")
            finally:
                try:
                    p.disconnect(physicsClientId=physics_client)
                except Exception:
                    pass
                try:
                    rr.disconnect()
                except Exception:
                    pass

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
