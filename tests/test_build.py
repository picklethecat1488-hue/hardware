"""Contains Build system unit tests."""

from build import Builder
import cadquery as cq
from itertools import combinations
import math
import numpy as np
import pytest
import zipfile


class TestBuilder:
    """Manifold builder unit tests."""

    def pytest_generate_tests(self, metafunc):
        """Generate tests from test fixtures.

        :param _type_ metafunc: The test meta function
        """
        if "name" in metafunc.fixturenames:
            builder = Builder()
            metafunc.parametrize("name", builder.config.names)
        if "clamp_idx" in metafunc.fixturenames:
            builder = Builder()
            clamp_idxes = range(len(builder.config.clamp_lengths))
            metafunc.parametrize("clamp_idx", clamp_idxes)
        if "right" in metafunc.fixturenames:
            metafunc.parametrize("right", [False, True])

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
                    builder.build_tube(name1),
                    builder.build_tube(name2),
                )
                inter_result = part1.intersect(part2)

                # Check if the intersection contains any volume
                if inter_result.val().Volume() > 1e-6:  # Using a small tolerance
                    print(f"Intersection detected between {name1} and {name2}")
                    return False
            return True

        assert no_overlap(builder.config.names)

    def test_in_bounds(self, builder, name, right):
        """Test the parts are in bounds.

        :param _type_ builder: The builder to test
        :param _type_ name: The name of the part to test
        :param _type_ right: True if testing the right side
        """
        part = builder.build_part(name, right=right)
        proj_bounds = builder.config.get_bounds()
        volume = part.cut(proj_bounds).val().Volume()

        assert volume == pytest.approx(0)

    def test_can_clamp(self, name, clamp_idx, right, builder):
        """Test if the given clamp bed satisfies the clamp property.

        :param _type_ name: The name of the part to test
        :param _type_ clamp_idx: The clamp index to test
        :param _type_ right: True if testing the right side
        :param _type_ builder: The manifold builder to test
        """
        path = builder.create_wire(name)
        length = path.val().Length()

        # Map clamp_idx to clamp paraeters
        offsets = [0, 0.5, (length - builder.config.clamp_lengths[-1]) / length]
        expected = [
            builder.config.outer_diameter / 2,
            builder.config.clamp_diameter / 2,
            builder.config.outer_diameter / 2,
        ]
        part = builder.build_part(name, right=right)
        pos, len, expected = (
            offsets[clamp_idx],
            builder.config.clamp_lengths[clamp_idx],
            expected[clamp_idx],
        )

        # Check if we can move clamp over section
        clamp_off = builder.create_ring(
            path, pos, len, outer_radius=expected + builder.config.wall_thickness, inner_radius=expected
        )
        assert part.intersect(clamp_off).val().Volume() == pytest.approx(0)

        # Check if we can push clamp onto section
        clamp_on = builder.create_ring(
            path, pos, len, outer_radius=expected + builder.config.wall_thickness, inner_radius=expected - 0.01
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
        build_args = {"start_deg": (0 if right else 180), "end_deg": (180 if right else 360)}
        manifold = builder.build_tube(name, **build_args)
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
        part = builder.build_prepared_part(name, right=right)
        part_val = part.val()

        # Ensure the part is a watertight solid
        assert part_val.isValid()
        assert part_val.Volume() > 0

        # Ensure the part is touching the print bed
        bottom_faces = part.faces("<Z").vals()
        face_area = sum(f.Area() for f in bottom_faces)
        assert face_area > 0

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
