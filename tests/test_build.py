"""Contains Build system unit tests."""

from build import Builder
import cadquery as cq
import math
import numpy as np
import pytest
import zipfile
from pathlib import Path
from unittest.mock import patch


class TestBuilder:
    """Manifold builder unit tests."""

    @pytest.fixture(scope="class")
    def builder(self):
        """Return the test fixture for the manifold builder.

        :return _type_: A manifold builder object
        """
        return Builder()

    @pytest.fixture(scope="class", params=["driver", "passenger"])
    def name(self, request):
        """Return the name o test.

        :param _type_ request: The test request.
        :return _type_: A name.
        """
        return request.param

    @pytest.fixture(scope="class", params=[False, True])
    def right(self, request):
        """Return the right patameter.

        :param _type_ request: The test request.
        :return _type_: True or False.
        """
        return request.param

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

            The exhaust inlets and outlets are fixed size cuffs. The inlet connects directly to the midpipe, and the outlet must fit inside the exhaust tip.

            :param _type_ name: The name of the part to test
            :return _type_: A tuple
            """
            inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"
            return (
                # Inlet start
                builder.P[inlet_key],
                # Inlet end
                builder.P[inlet_key] + builder.V[inlet_key] * builder.config.clamp_lengths[0],
                # Outlet start
                builder.P[outlet_key],
                # Outlet end
                builder.P[outlet_key] + builder.V[outlet_key] * builder.config.clamp_lengths[-1],
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
        assert round(driver_outlet_start[2] - driver_inlet_start[2]) == pytest.approx(141)
        print(f"{driver_outlet_start[2]} {driver_inlet_start[2]}")

        # Check dist between passenger inlet and outlet
        assert dist(passenger_inlet_start, passenger_outlet_start) == pytest.approx(485)
        assert round(passenger_outlet_start[2] - passenger_inlet_start[2]) == pytest.approx(171)

    def test_wire(self, name, builder):
        """Perform wire testing.

        :param _type_ name: The name of the part to test
        :param _type_ builder: The manifold builder to test
        """

        def calc_point_err(v, p):
            return abs((v - cq.Vector([p[0], p[1], p[2]])).Length)

        wire = builder.create_wire(name)
        wire_obj = wire.val()
        length = wire_obj.Length()
        inlet_clamp_start = wire_obj.positionAt(0.0)
        inlet_clamp_end = wire_obj.positionAt(builder.config.clamp_lengths[0] / length)
        outlet_clamp_start = wire_obj.positionAt((length - builder.config.clamp_lengths[-1]) / length)
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
        assert (inlet_clamp_end - inlet_clamp_start).Length == pytest.approx(builder.config.clamp_lengths[0])
        assert (outlet_clamp_end - outlet_clamp_start).Length == pytest.approx(builder.config.clamp_lengths[-1])

    def test_create_profile_sketch(self, builder):
        """Test profile sketch generation for a valid radius."""
        sketch = builder.create_profile_sketch(0, 90, outer_radius=10, inner_radius=5)
        assert sketch is not None
        assert sketch.val().Area() > 0

    def test_create_profile_sketch_invalid_inner_radius(self, builder):
        """Ensure invalid profile radii raise ValueError."""
        with pytest.raises(ValueError):
            builder.create_profile_sketch(0, 90, outer_radius=10, inner_radius=10)

    def test_build_clean_tool(self, name, builder):
        """Test clean tool creation for a given part name."""
        clean_tool = builder.build_clean_tool(name)
        assert clean_tool is not None
        assert clean_tool.val().Volume() > 0

    def test_part_fits_together(self, builder, name, right):
        """Test that the parts can fit together.

        :param _type_ builder: The manifold builder to test
        :param _type_ name: The name of the part to test
        :param _type_ right: True if building the right part
        """
        # Make sure parts do not self intersect
        part = builder.build_part(name, right=right)
        other_part = builder.build_part(name, right=(not right))
        assert part.intersect(other_part).val().Volume() == pytest.approx(0), (
            f"intersection detected between {name} parts"
        )

    def test_part_doesnt_overlap(self, builder, name, right):
        """Test that the part does not interlap with another assembly.

        :param _type_ builder: The manifold builder to test
        :param _type_ name: The name of the part to test
        :param _type_ right: True if building the right part
        """
        part = builder.build_part(name, right=right)
        other_name = next(x for x in builder.config.names if x != name)
        other_part = builder.build_part(other_name, right=not right)
        assert part.intersect(other_part).val().Volume() == pytest.approx(0), (
            f"intersection detected between {name},right={right} and {other_name},right={not right}"
        )

    def test_in_bounds(self, builder, name, right):
        """Test the parts are in bounds.

        :param _type_ builder: The builder to test
        :param _type_ name: The name of the part to test
        :param _type_ right: True if testing the right side
        """
        part = builder.build_part(name, right=right)
        proj_bounds = builder.build_bound_box()
        volume = part.cut(proj_bounds).val().Volume()

        assert volume == pytest.approx(0)

    def test_can_clamp(self, name, right, builder):
        """Test if a representative clamp bed satisfies the clamp property."""
        clamp_idx = 1
        path = builder.create_wire(name)
        length = path.val().Length()

        # Map clamp_idx to clamp parameters
        offsets = (
            [0]
            + [clamp_pos[0] for clamp_pos in builder.config.clamp_positions[name][1:-1]]
            + [(length - builder.config.clamp_lengths[-1]) / length]
        )
        expected = np.array(builder.config.clamp_diameters) / 2
        part = builder.build_part(name, right=right)
        pos, len, expected = (
            offsets[clamp_idx],
            builder.config.clamp_lengths[clamp_idx],
            expected[clamp_idx],
        )

        # Check if we can move clamp over section
        clamp_off = builder.create_ring(
            name, pos, len, outer_radius=expected + builder.config.wall_thickness, inner_radius=expected
        )
        assert part.intersect(clamp_off).val().Volume() == pytest.approx(0)

        # Check if we can push clamp onto section
        clamp_on = builder.create_ring(
            name, pos, len, outer_radius=expected + builder.config.wall_thickness, inner_radius=expected - 0.01
        )
        assert part.intersect(clamp_on).val().Volume() > 0

    def test_part(self, name, right, builder):
        """Test the parts.

        Verifies that the assembled parts will create the manifold shape.

        :param _type_ name: The name of the part to test
        :param _type_ right: True if building the right part, else False
        :param _type_ builder: The manifold builder to test
        """
        if name != "driver" and name != "passenger":
            raise ValueError(f"Invalid name: {name}")
        manifold = builder.build_tube(name, right=right)
        part = builder.build_part(name, right=right)
        manifold_vol, manifold_from_parts_vol = (
            manifold.val().Volume(),
            part.intersect(manifold).val().Volume(),
        )
        error_pct = abs(manifold_vol - manifold_from_parts_vol) / (manifold_vol + manifold_from_parts_vol) / 2 * 100
        # less than 0.5% error for each rebuilt part.
        assert error_pct < 0.5

    def test_prepared_part(self, name, right, builder):
        """Test the part is suitable for 3D printing.

        :param _type_ name: The name of the part to test
        :param _type_ right: True if building the right part, else False
        :param _type_ builder: The manifold builder to test
        """
        orig_part = builder.build_part(name, right=right)
        part = builder.build_prepared_part(name, right=right)

        # Ensure the part is a watertight solid
        assert part.val().isValid()
        assert part.val().Volume() > 0

        # Ensure the part is touching the print bed
        bottom_faces = part.faces("<Z").vals()
        face_area = sum(f.Area() for f in bottom_faces)
        assert face_area > 0

        # Run a few more checks to see if the part was mutated during preparation
        assert abs(orig_part.val().Volume() - part.val().Volume()) < 1, "Volume changed"
        assert abs(orig_part.val().Area() - part.val().Area()) < 1, "Surface area changed"

    def test_generate_all(self, builder, tmp_path):
        """Test the part generation happy path.

        :param _type_ builder: The Builder to test.
        :param _type_ tmp_path: A temporary path to generate files in.
        """
        builder.generate_all(out_dir=tmp_path, zip_name="build.zip")
        zip_path = tmp_path / "build.zip"
        assert zip_path.exists()

        # Open the resulting zip and verify its contents.
        with zipfile.ZipFile(zip_path, "r") as z:
            contents = z.namelist()
            assert f"{builder.config.project_name}_v{builder.config.ver}_diagram.svg" in contents
            for name in builder.config.names:
                for side in ["left", "right"]:
                    assert f"{builder.config.project_name}_v{builder.config.ver}_{name}_{side}.stl" in contents

    def test_end_angle(self, builder, name):
        """Test the inlet slope on the driver inlet.

        :param _type_ builder: The Builder to test.
        :param _type_ name: The name of the part to test
        """

        def get_angle(key):
            """Return the veritcal angle for the given exhaust end.

            :param _type_ key: The key to return.
            :return _type_: The angle in degrees.
            """
            z_axis = cq.Vector(0, 0, 1)
            v_test = cq.Vector(*builder.V[key])
            angle = 90 - math.degrees(v_test.getAngle(z_axis))
            return angle

        # Horizontal magnitude (distance in XY plane)
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"

        # Test inlet angle
        angle = get_angle(inlet_key)
        expected_angle = 14.09 if name == "driver" else 0
        assert round(angle, 2) == pytest.approx(expected_angle)

        # Test outlet angle
        angle = get_angle(outlet_key)
        expected_angle = 0
        assert round(angle, 2) == pytest.approx(expected_angle)

    def test_overall_bounds(self, builder, name):
        """Test the overall bounds of an assembly.

        :param _type_ builder: The Builder to test.
        :param _type_ name: The name of the part to test
        """
        part = builder.build_part(name).union(builder.build_part(name, right=True))
        bbox = part.val().BoundingBox()

        if name == "driver":
            xmin, xlen = 150, 227
            ymin, ylen = -32, 324
            zmin, zlen = 319, 203
        elif name == "passenger":
            xmin, xlen = 559, 387
            ymin, ylen = -32, 419
            zmin, zlen = 288, 234
        else:
            raise ValueError("Invalid part name")

        # Make sure the overall dimensions of the part haven't changed since last revision.
        assert round(bbox.xmin) == xmin
        assert round(bbox.xlen) == xlen

        assert round(bbox.ymin) == ymin
        assert round(bbox.ylen) == ylen

        assert round(bbox.zmin) == zmin
        assert round(bbox.zlen) == zlen
