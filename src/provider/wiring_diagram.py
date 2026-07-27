"""Wiring diagram generator from a Wiring model."""

import math
import heapq
from typing import Dict, List, Optional, Any
from pydantic import validate_call
from build123d import *  # type: ignore
from model.wiring import Wiring, FootprintModel, NetModel, PinSide
from model.text_args import TextArgs
from .room import Room


# Routing and rendering constants
GRID_STEP = 2.0
PAD_RADIUS = 0.7
PAD_CLEARANCE = 3.7
LABEL_OFFSET = 2.2
CROSSOVER_RADIUS = 1.2
WIRE_FILLET_RADIUS = 1.5
WIRE_DOT_RADIUS = 0.5
TEXT_FONT_SIZE = 1.8
TEXT_HEIGHT = 2.0
TEXT_WIDTH_FACTOR = 0.65

# A* routing penalty costs
TURN_PENALTY = 15.0
OBSTACLE_PENALTY = 400.0
CROSSING_PENALTY = 80.0


def smart_fillet(pts: list[Vector], default_radius: float) -> Any:
    """Fillet wire corners robustly, scaling down the radius if segments are short."""
    if len(pts) <= 2:
        return Polyline(pts)

    # 1. Identify 90-degree corners with adjacent segments longer than radius
    corners = []
    for i in range(1, len(pts) - 1):
        v1 = pts[i] - pts[i - 1]
        v2 = pts[i + 1] - pts[i]
        l1, l2 = v1.length, v2.length
        if l1 < 1e-5 or l2 < 1e-5:
            continue
        u1 = v1.normalized()
        u2 = v2.normalized()
        # Near-90-degree corner check
        if abs(u1.dot(u2)) < 0.15:
            if l1 >= default_radius and l2 >= default_radius:
                corners.append(pts[i])

    # 2. Try filleting only selected corners, falling back to smaller radii if needed
    if corners:
        for r in (default_radius, default_radius / 2.0, default_radius / 5.0):
            try:
                with BuildLine() as bl:
                    Polyline(pts)
                    vertices_to_fillet = [
                        v for v in bl.vertices() if any((v.center() - c).length < 1e-3 for c in corners)
                    ]
                    if vertices_to_fillet:
                        fillet(vertices_to_fillet, radius=r)
                    return bl.line
            except Exception:
                continue

    return Polyline(pts)


class Obstacle:
    """Represents a 2D bounding box obstacle for orthogonal wire routing."""

    def __init__(self, x1: float, y1: float, x2: float, y2: float, owner: Optional[Vector] = None):
        """Initialize the Obstacle with bounding coordinates and optional owner pin."""
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.owner = owner


class WiringDiagram:
    """Generates 2D wiring diagram elements (footprints, pads, labels, routed wires) in a Room."""

    @validate_call(config={"arbitrary_types_allowed": True})
    def __init__(self, wiring: Wiring):
        """Initialize the WiringDiagram generator with the specified Wiring model."""
        self.wiring = wiring

    @validate_call(config={"arbitrary_types_allowed": True})
    def _find_wire_path(
        self,
        start_pt: Vector,
        end_pt: Vector,
        obstacles: list[Obstacle],
        routed_cells: set[tuple[int, int]],
        bounds: tuple[float, float, float, float, float],
        grid_step: float = GRID_STEP,
    ) -> list[Vector]:
        """Find an optimal orthogonal path from start_pt to end_pt avoiding obstacles and other wires."""
        # Define bounding box and max radius of search area dynamically
        min_x, max_x, min_y, max_y, max_r = bounds

        # Helper to convert physical coordinate to grid index
        def to_grid(x: float, y: float) -> tuple[int, int]:
            return int(round((x - min_x) / grid_step)), int(round((y - min_y) / grid_step))

        def to_phys(gx: int, gy: int) -> tuple[float, float]:
            return min_x + gx * grid_step, min_y + gy * grid_step

        start_g = to_grid(start_pt.X, start_pt.Y)
        end_g = to_grid(end_pt.X, end_pt.Y)

        max_gx = int((max_x - min_x) / grid_step)
        max_gy = int((max_y - min_y) / grid_step)

        # Identify start/end component footprint bounding boxes (where owner is None)
        start_obs = None
        end_obs = None
        for obs in obstacles:
            if obs.owner is None:
                if obs.x1 <= start_pt.X <= obs.x2 and obs.y1 <= start_pt.Y <= obs.y2:
                    start_obs = obs
                if obs.x1 <= end_pt.X <= obs.x2 and obs.y1 <= end_pt.Y <= obs.y2:
                    end_obs = obs

        queue = []
        g_score = {}
        came_from = {}

        g_score[(start_g[0], start_g[1], None)] = 0.0
        heapq.heappush(queue, (0.0, 0.0, start_g[0], start_g[1], None))

        found = False
        best_last_dir = None
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]

        while queue:
            f, g, gx, gy, last_dir = heapq.heappop(queue)

            if (gx, gy) == end_g:
                found = True
                best_last_dir = last_dir
                break

            current_g = g_score.get((gx, gy, last_dir), float("inf"))
            if g > current_g + 1e-9:
                continue

            for dx, dy in dirs:
                ngx, ngy = gx + dx, gy + dy

                if not (0 <= ngx <= max_gx and 0 <= ngy <= max_gy):
                    continue

                px, py = to_phys(ngx, ngy)
                if px * px + py * py > max_r * max_r:
                    continue

                # Base cost is grid step distance
                step_cost = grid_step

                # Direction change (turn) penalty
                if last_dir is not None and (dx, dy) != last_dir:
                    step_cost += TURN_PENALTY

                # Footprint and label obstacles
                for obs in obstacles:
                    ox1, oy1, ox2, oy2, owner = obs.x1, obs.y1, obs.x2, obs.y2, obs.owner
                    if ox1 <= px <= ox2 and oy1 <= py <= oy2:
                        # Allow routing near/through own start/end pins
                        if owner is not None:
                            if (abs(owner.X - start_pt.X) < 1e-3 and abs(owner.Y - start_pt.Y) < 1e-3) or (
                                abs(owner.X - end_pt.X) < 1e-3 and abs(owner.Y - end_pt.Y) < 1e-3
                            ):
                                continue
                        else:
                            # Footprint obstacle: allow close to start/end points
                            if obs == start_obs or obs == end_obs:
                                dist_start = math.hypot(px - start_pt.X, py - start_pt.Y)
                                dist_end = math.hypot(px - end_pt.X, py - end_pt.Y)
                                if dist_start < 6.0 or dist_end < 6.0:
                                    continue

                        # Heavily penalize going across other components or labels
                        step_cost += OBSTACLE_PENALTY

                # Wire crossing/intersection penalty
                if (ngx, ngy) in routed_cells:
                    step_cost += CROSSING_PENALTY

                tentative_g = current_g + step_cost
                neighbor_state = (ngx, ngy, (dx, dy))

                if tentative_g < g_score.get(neighbor_state, float("inf")):
                    g_score[neighbor_state] = tentative_g
                    came_from[neighbor_state] = (gx, gy, last_dir)
                    h = (abs(ngx - end_g[0]) + abs(ngy - end_g[1])) * grid_step
                    heapq.heappush(queue, (tentative_g + h, tentative_g, ngx, ngy, (dx, dy)))

        if not found:
            # Fall back to a simple orthogonal L-bend (x1, y1) -> (x2, y1) -> (x2, y2)
            mid_pt = Vector(end_pt.X, start_pt.Y, 0.0)
            return [start_pt, mid_pt, end_pt]

        path = []
        curr = (end_g[0], end_g[1], best_last_dir)
        while curr in came_from:
            path.append(Vector(*to_phys(curr[0], curr[1]), 0.0))
            curr = came_from[curr]
        path.append(start_pt)
        path.reverse()

        if path:
            path[0] = start_pt
            path[-1] = end_pt

        # Simplify path by merging collinear segments
        simplified = [path[0]]
        for i in range(1, len(path) - 1):
            prev = simplified[-1]
            curr = path[i]
            nxt = path[i + 1]

            dir1 = (curr - prev).normalized() if (curr - prev).length > 1e-9 else Vector(0, 0, 0)
            dir2 = (nxt - curr).normalized() if (nxt - curr).length > 1e-9 else Vector(0, 0, 0)

            if (dir1 - dir2).length > 1e-5:
                simplified.append(curr)
        simplified.append(path[-1])

        if len(simplified) < 2:
            return [start_pt, end_pt]
        return simplified

    @validate_call(config={"arbitrary_types_allowed": True})
    def build(self, room: Room) -> None:
        """Populate the room with the footprints, pads, labels, and routed wire paths."""
        components = self.wiring.footprints

        def parse_align(align_str: str) -> Align:
            if align_str == "min":
                return Align.MIN
            elif align_str == "max":
                return Align.MAX
            return Align.CENTER

        def get_pin_side(pin_pos: tuple[float, float, float]) -> PinSide:
            """Determine the side of a pin based on its physical offset from component center."""
            if pin_pos[0] < -1e-3:
                return PinSide.LEFT
            elif pin_pos[0] > 1e-3:
                return PinSide.RIGHT
            elif pin_pos[1] > 1e-3:
                return PinSide.TOP
            else:
                return PinSide.BOTTOM

        pin_positions = {}
        for fp in components:
            cx, cy = fp.position[0], fp.position[1]
            w, l, thickness = fp.dimensions

            # Build footprint sketch
            with BuildSketch() as f_sketch:
                Rectangle(w, l)
                if not self.wiring.is_surface_mount(fp.name):
                    fillet(f_sketch.vertices(), radius=1.5)

            room.add(f"{fp.name}_footprint", f_sketch.sketch.moved(Location((cx, cy))), color="grey", line_weight=2.0)

            # Add component label centered inside the footprint
            room.add_label(
                f"{fp.name}_label",
                fp.label.text,
                Vector(cx, cy, 0.0),
                options=TextArgs(font_size=TEXT_FONT_SIZE, align=(Align.CENTER, Align.CENTER), font="Serif"),
            )

            # Add pins
            pin_positions[fp.name] = {}
            for pin in fp.pins:
                gx, gy = cx + pin.position[0], cy + pin.position[1]
                pin_positions[fp.name][pin.name] = Vector(gx, gy, 0.0)

                with BuildSketch() as pad:
                    Circle(radius=PAD_RADIUS)
                room.add(f"{fp.name}_pad_{pin.name}", pad.sketch.moved(Location((gx, gy))), color="grey")

                lbl_offset = LABEL_OFFSET
                match get_pin_side(pin.position):
                    case PinSide.LEFT:
                        lbl_pos = Vector(gx - lbl_offset, gy, 0.0)
                        align = (Align.MAX, Align.CENTER)
                    case PinSide.RIGHT:
                        lbl_pos = Vector(gx + lbl_offset, gy, 0.0)
                        align = (Align.MIN, Align.CENTER)
                    case PinSide.TOP:
                        lbl_pos = Vector(gx, gy + lbl_offset, 0.0)
                        align = (Align.CENTER, Align.MIN)
                    case PinSide.BOTTOM:
                        lbl_pos = Vector(gx, gy - lbl_offset, 0.0)
                        align = (Align.CENTER, Align.MAX)

                room.add_label(
                    f"{fp.name}_lbl_{pin.name}",
                    pin.label,
                    lbl_pos,
                    options=TextArgs(font_size=TEXT_FONT_SIZE, align=align, font="Serif"),
                )

        # Pins helper mapping to get global coordinate vectors from layout
        def get_pin_pos(component, pin):
            return pin_positions[component][pin]

        # Line intersection helper to detect crossover points
        def line_intersection(A, B, C, D):
            # Line AB represented as a1x + b1y = c1
            a1 = B.Y - A.Y
            b1 = A.X - B.X
            c1 = a1 * A.X + b1 * A.Y

            # Line CD represented as a2x + b2y = c2
            a2 = D.Y - C.Y
            b2 = C.X - D.X
            c2 = a2 * C.X + b2 * C.Y

            determinant = a1 * b2 - a2 * b1

            if abs(determinant) < 1e-9:
                return None  # Parallel or collinear

            x = (b2 * c1 - b1 * c2) / determinant
            y = (a1 * c2 - a2 * c1) / determinant
            P = Vector(x, y, 0.0)

            # Check if P lies on both line segments
            def on_segment(P_pt, start, end):
                return (
                    min(start.X, end.X) - 1e-5 <= P_pt.X <= max(start.X, end.X) + 1e-5
                    and min(start.Y, end.Y) - 1e-5 <= P_pt.Y <= max(start.Y, end.Y) + 1e-5
                )

            if on_segment(P, A, B) and on_segment(P, C, D):
                return P
            return None

        # Bounding box obstacles for footprints and pin labels
        obstacles = []
        for fp in components:
            cx, cy = fp.position[0], fp.position[1]

            # Add pin label obstacles (owner=pin position)
            for pin in fp.pins:
                gx, gy = cx + pin.position[0], cy + pin.position[1]
                # Add pin pad obstacle (owner=pin position) so wires avoid other pins (aligned to grid step)
                obstacles.append(
                    Obstacle(
                        gx - PAD_CLEARANCE,
                        gy - PAD_CLEARANCE,
                        gx + PAD_CLEARANCE,
                        gy + PAD_CLEARANCE,
                        Vector(gx, gy, 0.0),
                    )
                )
                lbl_offset = LABEL_OFFSET

                # Estimate text label dimensions to route wires around them
                text_width = len(pin.label) * TEXT_FONT_SIZE * TEXT_WIDTH_FACTOR
                text_height = TEXT_HEIGHT

                match get_pin_side(pin.position):
                    case PinSide.LEFT:
                        lox1 = gx - lbl_offset - text_width
                        lox2 = gx - 0.5
                        loy1 = gy - text_height / 2.0
                        loy2 = gy + text_height / 2.0
                    case PinSide.RIGHT:
                        lox1 = gx + 0.5
                        lox2 = gx + lbl_offset + text_width
                        loy1 = gy - text_height / 2.0
                        loy2 = gy + text_height / 2.0
                    case PinSide.TOP:
                        lox1 = gx - text_width / 2.0
                        lox2 = gx + text_width / 2.0
                        loy1 = gy + 0.5
                        loy2 = gy + lbl_offset + text_height
                    case PinSide.BOTTOM:
                        lox1 = gx - text_width / 2.0
                        lox2 = gx + text_width / 2.0
                        loy1 = gy - lbl_offset - text_height
                        loy2 = gy - 0.5

                obstacles.append(Obstacle(lox1, loy1, lox2, loy2, Vector(gx, gy, 0.0)))

        # 1. Gather and automatically route wire paths
        raw_paths = []
        routed_cells = set()

        # Get bounding box of all elements in the room to dynamically define the search limits
        bb = room.compound.bounding_box()
        # The enclosing boundary radius is the maximum extent of the bounding box
        max_r = max(abs(bb.min.X), abs(bb.max.X), abs(bb.min.Y), abs(bb.max.Y)) + 15.0

        # Add padding to search area bounds to allow wires to route outside components comfortably
        pad = 8.0
        min_x = bb.min.X - pad
        max_x = bb.max.X + pad
        min_y = bb.min.Y - pad
        max_y = bb.max.Y + pad
        grid_step = 2.0

        bounds = (min_x, max_x, min_y, max_y, max_r)

        def to_grid(x: float, y: float) -> tuple[int, int]:
            return int(round((x - min_x) / grid_step)), int(round((y - min_y) / grid_step))

        # Sort nets to route those with the most connections first
        sorted_nets = sorted(self.wiring.nets, key=lambda n: len(n.pins), reverse=True)
        for net in sorted_nets:
            sub_paths = []
            current_path = []

            # Start tracking the active routing pin
            active_component, active_pin = net.pins[0]
            segments_info = []

            for i in range(len(net.pins) - 1):
                component_b, pin_b = net.pins[i + 1]
                pt_a = get_pin_pos(active_component, active_pin)
                pt_b = get_pin_pos(component_b, pin_b)

                # Get pin definitions to determine their layout sides
                fp_a = next(f for f in components if f.name == active_component)
                pin_a_obj = next(p for p in fp_a.pins if p.name == active_pin)
                fp_b = next(f for f in components if f.name == component_b)
                pin_b_obj = next(p for p in fp_b.pins if p.name == pin_b)

                start_side = get_pin_side(pin_a_obj.position)
                end_side = get_pin_side(pin_b_obj.position)

                # Route between current active pin and next pin using A* router
                segment_path = self._find_wire_path(pt_a, pt_b, obstacles, routed_cells, bounds)

                # Add segment path to routed cells so future routes avoid it
                for k in range(len(segment_path) - 1):
                    p1 = segment_path[k]
                    p2 = segment_path[k + 1]
                    g1_x, g1_y = to_grid(p1.X, p1.Y)
                    g2_x, g2_y = to_grid(p2.X, p2.Y)
                    x_start, x_end = min(g1_x, g2_x), max(g1_x, g2_x)
                    y_start, y_end = min(g1_y, g2_y), max(g1_y, g2_y)
                    for gx in range(x_start, x_end + 1):
                        for gy in range(y_start, y_end + 1):
                            routed_cells.add((gx, gy))

                # Append the segment path directly to sub_paths
                sub_paths.append(segment_path)
                segments_info.append((segment_path, start_side, end_side))

                # Move the active routing pin forward only if the target is not surface mount
                if not self.wiring.is_surface_mount(component_b):
                    active_component, active_pin = component_b, pin_b

            # Apply parallel offsets (e.g. SCL running alongside SDA) to intermediate path vertices
            if net.offset != (0.0, 0.0):
                dx, dy = net.offset
                new_sub_paths = []
                for path, start_side, end_side in segments_info:
                    if len(path) <= 1:
                        new_sub_paths.append(path)
                    else:
                        offset_path = [path[0]]

                        # 1. Start exit point: project horizontally or vertically based on pin layout side
                        if start_side in (PinSide.LEFT, PinSide.RIGHT):
                            p_start_exit = Vector(path[1].X + dx, path[0].Y, 0.0)
                        else:
                            p_start_exit = Vector(path[0].X, path[1].Y + dy, 0.0)

                        if (p_start_exit - path[0]).length > 1e-5:
                            offset_path.append(p_start_exit)

                        # 2. Offset intermediate points
                        for p in path[1:-1]:
                            offset_path.append(Vector(p.X + dx, p.Y + dy, 0.0))

                        # 3. End exit point: project horizontally or vertically based on pin layout side
                        if end_side in (PinSide.LEFT, PinSide.RIGHT):
                            p_end_exit = Vector(path[-2].X + dx, path[-1].Y, 0.0)
                        else:
                            p_end_exit = Vector(path[-1].X, path[-2].Y + dy, 0.0)

                        if (p_end_exit - offset_path[-1]).length > 1e-5 and (p_end_exit - path[-1]).length > 1e-5:
                            offset_path.append(p_end_exit)

                        offset_path.append(path[-1])

                        # Deduplicate consecutive identical points
                        dedup_offset_path = []
                        for pt in offset_path:
                            if not dedup_offset_path or (pt - dedup_offset_path[-1]).length > 1e-5:
                                dedup_offset_path.append(pt)
                        new_sub_paths.append(dedup_offset_path)
                sub_paths = new_sub_paths

            raw_paths.append((net.name, net.color, sub_paths))

        # 2. Process paths to insert crossover bumps (radius = CROSSOVER_RADIUS)
        processed_paths = []
        R = CROSSOVER_RADIUS

        for i in range(len(raw_paths)):
            name_i, color_i, sub_paths_i = raw_paths[i]
            for sub_idx, pts_i in enumerate(sub_paths_i):
                new_pts_i = [pts_i[0]] if pts_i else []

                for k in range(len(pts_i) - 1):
                    A = pts_i[k]
                    B = pts_i[k + 1]

                    # Find all intersections of segment AB with segments of already-drawn/lower index wires
                    intersections = []
                    for j in range(i):
                        name_j, color_j, sub_paths_j = raw_paths[j]
                        for pts_j in sub_paths_j:
                            for m in range(len(pts_j) - 1):
                                C = pts_j[m]
                                D = pts_j[m + 1]
                                P = line_intersection(A, B, C, D)
                                if P is not None:
                                    dist_A = (P - A).length
                                    dist_B = (P - B).length
                                    if dist_A > R and dist_B > R:
                                        intersections.append((dist_A, P))

                    # Sort intersections by distance from segment start A
                    intersections.sort(key=lambda x: x[0])

                    # Build path with semi-circular bump arches over intersections
                    last_pt = A
                    dir_vec = (B - A).normalized() if (B - A).length > 1e-9 else Vector(0.0, 0.0, 0.0)
                    normal_vec = Vector(-dir_vec.Y, dir_vec.X, 0.0)

                    for dist, P in intersections:
                        P_start = P - dir_vec * R
                        new_pts_i.append(P_start)

                        # Sample 6 points to draw a smooth crossover arc
                        steps = 6
                        for step in range(1, steps):
                            theta = math.pi - (step * math.pi / steps)
                            pt = P + dir_vec * R * math.cos(theta) + normal_vec * R * math.sin(theta)
                            new_pts_i.append(pt)

                        P_end = P + dir_vec * R
                        new_pts_i.append(P_end)
                        last_pt = P_end

                    new_pts_i.append(B)

                # Deduplicate consecutive identical points
                dedup_pts = []
                for pt in new_pts_i:
                    if not dedup_pts or (pt - dedup_pts[-1]).length > 1e-5:
                        dedup_pts.append(pt)

                wire_name = name_i if sub_idx == 0 else f"{name_i}_{sub_idx}"
                processed_paths.append((wire_name, color_i, dedup_pts))

        # 3. Add all processed polylines/wires to the room
        for name, color, pts in processed_paths:
            wire_geom = smart_fillet(pts, WIRE_FILLET_RADIUS)
            room.add(f"wire_{name}", wire_geom, color=color)

            # Add connection dots at the start and end of the wire segment
            if len(pts) >= 2:
                with BuildSketch() as dot_sketch:
                    Circle(radius=WIRE_DOT_RADIUS)
                room.add(f"wire_dot_start_{name}", dot_sketch.sketch.moved(Location(pts[0])), color=color)
                room.add(f"wire_dot_end_{name}", dot_sketch.sketch.moved(Location(pts[-1])), color=color)
