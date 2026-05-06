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
            metafunc.parametrize("name", builder.names)
        if "clamp_idx" in metafunc.fixturenames:
            builder = Builder()
            metafunc.parametrize("clamp_idx", range(len(builder.clamp_lengths)))
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
                builder.P[inlet_key] + builder.V[inlet_key] * builder.clamp_lengths[0],
                # Outlet start
                builder.P[outlet_key],
                # Outlet end
                builder.P[outlet_key] + builder.V[outlet_key] * builder.clamp_lengths[-1],
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
        assert round(driver_outlet_start[2] - driver_inlet_start[2]) == pytest.approx(139)

        # Check dist between passenger inlet and outlet
        assert dist(passenger_inlet_start, passenger_outlet_start) == pytest.approx(485)
        assert round(passenger_outlet_start[2] - passenger_inlet_start[2]) == pytest.approx(169)

    def test_wire(self, name, builder):
        """Perform wire testing.

        :param _type_ name: The name of the part to test
        :param _type_ builder: The manifold builder to test
        """

        def calc_point_err(v, p):
            return abs((v - cq.Vector([p[0], p[1], p[2]])).Length)

        _, wire_obj = builder.create_wire(name)
        length = wire_obj.Length()
        inlet_clamp_start = wire_obj.positionAt(0.0)
        inlet_clamp_end = wire_obj.positionAt(builder.clamp_lengths[0] / length)
        outlet_clamp_start = wire_obj.positionAt((length - builder.clamp_lengths[-1]) / length)
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
        assert (inlet_clamp_end - inlet_clamp_start).Length == pytest.approx(builder.clamp_lengths[0])
        assert (outlet_clamp_end - outlet_clamp_start).Length == pytest.approx(builder.clamp_lengths[-1])

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

        assert no_overlap(builder.names)

    def test_clamp_radius(self, name, clamp_idx, right, builder):
        """Test the exhaust clamp volume to see if it has a hollow cylinder profile.

        :param _type_ name: The name of the part to test
        :param _type_ clamp_idx: The clamp index to test
        :param _type_ right: True if testing the right side
        :param _type_ builder: The manifold builder to test
        """

        def get_radius(part, off, len, radius):
            """Get radii of clamp at offset and length.

            :param _type_ part: The part
            :param _type_ off: The part offset
            :param _type_: The clamp length
            :return _type_: The expected radius
            """
            volume = cq.Workplane(path.val().positionAt(off)).circle(radius).extrude(len)
            volume = volume.intersect(part)
            edges = volume.edges("%Circle").vals()
            radii = [edge.radius() for edge in edges]
            return np.min(radii), np.max(radii)

        path, _ = builder.create_wire(name)
        offsets = builder.get_clamp_offsets(path.val().Length())
        part = builder.build_part(name, right=right)
        pos, len, expected = (
            offsets[clamp_idx],
            builder.clamp_lengths[clamp_idx],
            builder.clamp_diameters[clamp_idx] / 2,
        )
        min, max = get_radius(part, pos, len, expected)
        assert min == pytest.approx(expected), f"clamp length invalid at {pos}"
        assert max == pytest.approx(expected), f"clamp length invalid at {pos}"

    def test_part(self, name, builder):
        """Test the parts.

        Verifies that the assembled parts will create the manifold shape.

        :param _type_ name: The name of the part to test
        :param _type_ builder: The manifold builder to test
        """
        error_pct = builder.calc_part_error(name)
        assert round(error_pct) < 5

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
            assert f"{builder.project_name}_v{builder.ver}_diagram.svg" in contents
            for name in builder.names:
                for side in ["left", "right"]:
                    assert f"{builder.project_name}_v{builder.ver}_{name}_{side}.stl" in contents
