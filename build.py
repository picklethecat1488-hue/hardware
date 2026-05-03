"""Contains the code to build exhaust manifolds."""

import math
import numpy as np
import os
from pathlib import Path
import pytest
import cadquery as cq
from functools import lru_cache
from itertools import combinations
import zipfile


class Builder:
    """The manifold builder creates the manifold objects and exports them as files for 3D printing."""

    def __init__(self):
        """Initialize the builder."""
        self.project_name = "exhaust_manifolds"
        self.ver = 4
        self.thickness = 3
        self.outer_diameter = 63.5
        self.inner_diameter = self.outer_diameter - self.thickness  # 60mm
        self.clamp_len = 50.4  # 2 inches

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
        edge_rounding=0.5,
        **kwargs,
    ):
        """Build the exhaust manifold shape.

        :param _type_ name: The name of the manifold to build
        :param int start_deg: If building part of the manifold, the start angle of the tube offset to include in degrees, defaults to 0
        :param int end_deg: If building part of the manifold, the end angle of the tube offset to include in degrees, defaults to 0
        :param int trim_start: If building part of the manifold, how much to trim from the start in mm, defaults to 0
        :param int trim_end: If building part of the manifold, how much to trim from the end in mm, defaults to 0
        :param float edge_rounding: How much rounding to perform on each edge of the manifold, defaults to 0.5
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
            if edge_rounding > 0:
                profile = profile.fillet(edge_rounding)
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
        if edge_rounding > 0:

            def wrap_fillet(part, edge_rounding):
                """Fillet every edge that can possibly be filleted.

                :param _type_ part: The part to fillet.
                :param _type_ edge_rounding: The amount of rounding to apply.
                :return _type_: A filleted part.
                """
                all_edges = part.vals()

                for edge in all_edges:
                    try:
                        new_part = part.newObject([edge]).fillet(edge_rounding)
                        part = new_part
                    except Exception as _:
                        continue

                return part

            # Micro fillet the tube first to generate new edge geometry, then perform a full fillet.
            tube = wrap_fillet(tube, edge_rounding)
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
    def build_guide(self, name, right=False, guide_angle_deg=10, extra_angle_dist=2, guide_space=0.1):
        """Build the right or left manifold guide.

        The guide helps align the parts to each other as well as reduce material deformation.

        :param _type_ name: The name of the manifold
        :param bool right: True if building the right half, defaults to False
        :param _type_ guide_angle_deg Determines the size of the guide (in degrees)
        :param _type_ extra_angle_dist Determines the inner guide space to keep (in mm)
        :param _type_ guide_space How much space between the guide and the other part (in mm)
        :return _type_: The manifold guide
        """

        def get_build_manifold_args(right):
            """Get the list of manifolds to add and cut for the given part.

            :param _type_ right: True if building the right hand part, otherwise false
            :return _type_: A tuple containing arguments of manifold parts to build and parts to cut
            """
            angle = 0 if right else 180
            add_args = [
                {
                    "inner_radius": (self.outer_diameter - guide_space) / 2,
                    "outer_radius": (self.outer_diameter + self.thickness + guide_space) / 2,
                    "start_deg": angle - guide_angle_deg,
                    "end_deg": angle,
                    "trim_start": self.clamp_len,
                    "trim_end": self.clamp_len,
                },
                {
                    "inner_radius": (self.outer_diameter + guide_space) / 2,
                    "outer_radius": (self.outer_diameter + self.thickness + guide_space) / 2,
                    "start_deg": angle - guide_angle_deg,
                    "end_deg": angle + guide_angle_deg,
                    "trim_start": self.clamp_len,
                    "trim_end": self.clamp_len,
                },
            ]
            cut_args = [
                {
                    "inner_radius": (self.outer_diameter + self.thickness / 2) / 2,
                    "outer_radius": (self.outer_diameter + self.thickness * 2) / 2,
                    "start_deg": angle - guide_angle_deg + extra_angle_dist,
                    "end_deg": angle - extra_angle_dist,
                    "trim_start": self.clamp_len + extra_angle_dist,
                    "trim_end": self.clamp_len + extra_angle_dist,
                },
            ]
            return add_args, cut_args

        add_args, cut_args = get_build_manifold_args(right=right)

        # Constuct guides and remove any extra space from them
        adds = [self.build_manifold(name, **add_arg) for add_arg in add_args]
        guide = adds[0]
        for add in adds[1:]:
            guide = guide.union(add)
        for cut in [self.build_manifold(name, **cut_arg) for cut_arg in cut_args]:
            guide = guide.cut(cut)
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

    def generate_parts(self, name, out_dir):
        """Generate STL parts files for assembly.

        :param _type_ name: The name of the manifold
        """

        @lru_cache
        def prepare_part(name, start, end, right=False):
            """Prepare the part for export.

            :param _type_ name: The name of the manifold
            :param _type_ start: The inlet endpoint
            :param _type_ end: The outlet endpoint
            :param bool right: True if building the right half, defaults to False
            """

            def rot_angle(start, end):
                """Get the rotation angle for the part in degrees.

                We rotate the part slope about the x axis to try and place it as close to the bed as possible.

                :param _type_ start: The inlet endpoint
                :param _type_ end: The outlet endpoint
                :return _type_: The rotation angle in degrees
                """
                # We rotate the part slope about the x axis to try and place it as close to the bed as possible
                dy, dz = (end[1] - start[1]), (end[2] - start[2])
                return -math.degrees(-math.atan2(dy, dz)) - 90

            angle_x = rot_angle(start, end)
            part = self.build_part(name, right=right)
            prepared_part = part.rotate((0, 0, 0), (1, 0, 0), angle_x)
            if right:
                # Flip right half upside down
                prepared_part = prepared_part.mirror("XY")
            # Ensure that the part is sitting directly on the bed
            z_min = prepared_part.val().BoundingBox().zmin
            prepared_part = prepared_part.translate((0, 0, -z_min))
            return prepared_part

        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
        file_prefix = f"{self.project_name}_{self.ver}"

        for side in ["left", "right"]:
            mesh_file_name = f"{file_prefix}_{name}_{side}.stl"
            prepared_part = prepare_part(name, self.P[inlet_key], self.P[outlet_key], right=("right" in side))
            path_str = str(Path(out_dir) / mesh_file_name)
            cq.exporters.export(prepared_part, path_str)
            print(f"Done writing {path_str}")

    def generate_diagram(self, names, out_dir):
        """Generate a diagram for the given part names."""

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
        print(f"Done writing {path_str}")

    def generate_all(self, out_dir="build", zip_name="build.zip"):
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

        # Create the output directory
        path = Path(out_dir)
        path.mkdir(parents=True, exist_ok=True)

        # Export the diagram
        self.generate_diagram(self.names, out_dir=out_dir)

        # Export the STL files
        for name in self.names:
            self.generate_parts(name, out_dir=out_dir)

        # Compress the build
        zip_file_str = str(Path(out_dir) / zip_name)
        zip_build(zip_file_str)
        print(f"Done writing {zip_file_str}")


class TestBuilder:
    """Manifold builder unit tests."""

    def pytest_generate_tests(self, metafunc):
        """Generate tests from test fixtures.

        :param _type_ metafunc: The test meta function
        """
        if "name" in metafunc.fixturenames:
            builder = Builder()
            metafunc.parametrize("name", builder.names)

    @pytest.fixture(scope="class")
    def builder(self):
        """Return the test fixture for the manifold builder.

        :return _type_: A manifold builder object
        """
        return Builder()

    def test_measurements(self, builder):
        """Validate physical measurements.

        Do some validation of the pointlists based on the measurements I took on graph paper.
        Adjust coordinates to be 2D, then check how the driver and passenger inlets and outlets related to each other
        The inlets are connected to midpipes with slip ring connectors, while the exhaust pipes have cuff style clamps.

        :param _type_ builder: The manifold builder to test
        """

        def dist(p1, p2):
            """Get the 2D distance between two points.

            :param _type_ p1: The first point
            :param _type_ p2: The second type
            :return _type_: The 2D point distance
            """
            x1, y1, z1 = p1
            x2, y2, z2 = p2
            return round(math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2))

        def get_end_points(name):
            """Get the inlet and output start and end points.

            The exhaust inlets and outlets are cuffs of size clamp_len. The inlet connects directly to the midpipe, and the outlet must fit inside the exhaust tip.

            :param _type_ name: The name of the part to test
            :return _type_: A tuple
            """
            inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
            return (
                # Inlet start
                builder.P[inlet_key],
                # Inlet end
                builder.P[inlet_key] + builder.V[inlet_key] * builder.clamp_len,
                # Outlet start
                builder.P[outlet_key],
                # Outlet end
                builder.P[outlet_key] + builder.V[outlet_key] * builder.clamp_len,
            )

        driver_inlet_start, driver_inlet_end, driver_outlet_start, _ = get_end_points("driver")
        (
            passenger_inlet_start,
            passenger_inlet_end,
            passenger_outlet_start,
            _,
        ) = get_end_points("passenger")

        # Check dist between inlets
        assert dist(passenger_inlet_start, driver_inlet_start) == pytest.approx(231)
        assert round(driver_inlet_end[2] - driver_inlet_start[2]) == pytest.approx(12)

        # Check dist between outlets
        assert dist(driver_outlet_start, passenger_outlet_start) == pytest.approx(695)
        assert abs(round(passenger_inlet_end[2] - passenger_inlet_start[2])) == pytest.approx(0)

        # Check dist between driver inlet and outlet
        assert dist(driver_inlet_start, driver_outlet_start) == pytest.approx(315)
        assert round(driver_outlet_start[2] - driver_inlet_start[2]) == pytest.approx(140)

        # Check dist between passenger inlet and outlet
        assert dist(passenger_inlet_start, passenger_outlet_start) == pytest.approx(485)
        assert round(passenger_outlet_start[2] - passenger_inlet_start[2]) == pytest.approx(170)

    def test_wire(self, name, builder):
        """Perform wire testing.

        :param _type_ name: The name of the part to test
        :param _type_ builder: The manifold builder to test
        """

        def calc_point_err(v, p):
            return abs((v - cq.Vector([p[0], p[1], p[2]])).Length)

        _, wire_obj = builder.build_wire(name)
        length = wire_obj.Length()
        inlet_clamp_start = wire_obj.positionAt(0.0)
        inlet_clamp_end = wire_obj.positionAt(builder.clamp_len / length)
        outlet_clamp_start = wire_obj.positionAt((length - builder.clamp_len) / length)
        outlet_clamp_end = wire_obj.positionAt(1.0)
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"

        # Make sure the clamp starts are correct
        assert calc_point_err(inlet_clamp_start, builder.P[inlet_key]) == pytest.approx(0)
        assert calc_point_err(outlet_clamp_start, builder.P[outlet_key]) == pytest.approx(0)

        # Check clamp direction and length
        assert calc_point_err(
            (inlet_clamp_end - inlet_clamp_start).normalized(), builder.V[inlet_key]
        ) == pytest.approx(0)
        assert calc_point_err(
            (outlet_clamp_end - outlet_clamp_start).normalized(), builder.V[outlet_key]
        ) == pytest.approx(0)
        assert (inlet_clamp_end - inlet_clamp_start).Length == pytest.approx(builder.clamp_len)
        assert (outlet_clamp_end - outlet_clamp_start).Length == pytest.approx(builder.clamp_len)

    def test_wire_trim(self, name, builder):
        """Test trimming related functionality for wires.

        :param _type_ name: The name of the part to test
        :param _type_ builder: The manifold builder to test
        """
        _, wire_obj = builder.build_wire(name)
        _, guide_wire_obj = builder.build_wire(name, trim_start=builder.clamp_len, trim_end=builder.clamp_len)
        max_error = 5e-2
        assert abs(wire_obj.Length() - guide_wire_obj.Length() - 2 * builder.clamp_len) < max_error

    def test_overlap(self, builder):
        """Test that the parts do not overlap with each other.

        :param _type_ builder: The manifold builder to test
        """

        def no_overlap(names):
            """Check if all the given manifolds do not overlap.

            :param _type_ names: An array of manifold names to check
            :return _type_: True if the manifolds don't overlap, else False
            """
            for name1, name2 in combinations(names, 2):
                part1, part2 = (
                    builder.build_manifold(name1),
                    builder.build_manifold(name2),
                )
                inter_result = part1.intersect(part2)

                # Check if the intersection contains any volume
                if inter_result.val().Volume() > 1e-6:  # Using a small tolerance
                    print(f"Intersection detected between {name1} and {name2}")
                    return False
            return True

        assert no_overlap(builder.names)

    def test_diameter(self, name, builder):
        """Test the exhaust inlets and outlets diameters.

        :param _type_ name: The name of the part to test
        :param _type_ builder: The manifold builder to test
        """

        def calc_outer(tube):
            """Calculate the outer diameter of an inlet or outlet.

            :param _type_ tube: The tube
            :return _type_: The tube outer diameter
            """
            circular_edges = tube.edges("%CIRCLE").vals()
            radii = [e.radius() for e in circular_edges]
            # Extract radii
            return max(radii) * 2

        outer = calc_outer(builder.build_manifold(name))
        assert outer == pytest.approx(builder.outer_diameter)

    def test_part(self, name, builder):
        """Test the assembled parts.

        Verifies that the assembled parts will create the manifold shape.

        :param _type_ name: The name of the part to test
        :param _type_ builder: The manifold builder to test
        """
        error_pct = builder.calc_part_error(name)
        assert error_pct < 2


if __name__ == "__main__":
    """When run, exports all parts as STL files.
    """
    builder = Builder()
    builder.generate_all()
