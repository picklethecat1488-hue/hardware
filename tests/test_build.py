"""Contains Build system unit tests."""

from build import Builder
import cadquery as cq
import math
import numpy as np
import pytest
import zipfile
from pathlib import Path
from unittest.mock import patch
from typing import cast, Any


class TestBuilder:
    """Manifold builder unit tests."""

    @pytest.fixture(scope="class")
    def builder(self):
        """Return the manifold builder fixture."""
        return Builder()

    @pytest.fixture(scope="class", params=["driver", "passenger"])
    def name(self, request):
        """Return a test part name."""
        return request.param

    @pytest.fixture(scope="class", params=[False, True])
    def right(self, request):
        """Return a side selection fixture."""
        return request.param

    def test_measurements(self, builder):
        """Validate key manifold measurement relationships."""

        def dist(p1, p2):
            """Compute the 2D distance between two points."""
            x1, y1, z1 = p1
            x2, y2, z2 = p2
            return round(math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2))

        def get_end_points(name):
            """Return the inlet and outlet endpoint locations for a part."""
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
        """Verify wire path and clamp endpoints."""

        def calc_point_err(v, p):
            return abs((v - cq.Vector([p[0], p[1], p[2]])).Length)

        wire = builder.create_wire(name)
        # Use Any to bypass linter protocol mismatch in CadQuery Wire stubs
        wire_obj = cast(Any, wire.val())
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

    def test_create_profile(self, builder):
        """Test profile sketch generation for a valid center/angle profile."""
        sketch = builder.create_profile(45, 90, outer_radius=10, inner_radius=5)
        assert sketch is not None
        assert sketch.val().Area() > 0

    def test_create_profile_invalid_inner_radius(self, builder):
        """Ensure invalid profile radii raise ValueError."""
        with pytest.raises(ValueError):
            builder.create_profile(45, 90, outer_radius=10, inner_radius=10)

    def test_build_clean_tool(self, name, builder):
        """Test clean tool creation for a given part name."""
        clean_tool = builder.build_clean_tool(name)
        assert clean_tool is not None
        assert clean_tool.val().Volume() > 0

    def test_part_fits_together(self, builder, name, right):
        """Test that mirrored parts do not intersect."""
        # Make sure parts do not self intersect
        part = builder.build_part(name, right=right)
        other_part = builder.build_part(name, right=(not right))
        assert part.intersect(other_part).val().Volume() == pytest.approx(0), (
            f"intersection detected between {name} parts"
        )

    def test_part_doesnt_overlap(self, builder, name, right):
        """Ensure parts from different assemblies do not intersect."""
        part = builder.build_part(name, right=right)
        other_name = next(x for x in builder.config.names if x != name)
        other_part = builder.build_part(other_name, right=not right)
        assert part.intersect(other_part).val().Volume() == pytest.approx(0), (
            f"intersection detected between {name},right={right} and {other_name},right={not right}"
        )

    def test_in_bounds(self, builder, name, right):
        """Verify part fits inside bound box volume."""
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
            + [clamp_pos[0] for clamp_pos in builder.config.clamp_positions[name][1:-1] if clamp_pos is not None]
            + [(length - builder.config.clamp_lengths[-1]) / length]
        )
        expected = np.array(builder.config.clamp_diameters) / 2
        """Test if manifold clamps satisfy fitment requirements."""
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
        """Verify rebuilt part geometry matches manifold volume."""
        if name != "driver" and name != "passenger":
            raise ValueError(f"Invalid name: {name}")
        manifold = builder.build_tube(name, right=right, half_tube=True)
        part = builder.build_part(name, right=right)
        manifold_vol, manifold_from_parts_vol = (
            manifold.val().Volume(),
            part.intersect(manifold).val().Volume(),
        )
        error_pct = abs(manifold_vol - manifold_from_parts_vol) / (manifold_vol + manifold_from_parts_vol) / 2 * 100
        # less than 0.5% error for each rebuilt part.
        assert error_pct < 0.5

    def test_prepared_part(self, name, right, builder):
        """Verify the prepared part is printable and stable."""
        orig_part = builder.build_part(name, right=right)
        part = builder.build_prepared_part(name, right=right)

        # Ensure the part is a watertight solid
        assert part.val().isValid()
        assert part.val().Volume() > 0

        # Ensure the part is touching the print bed
        bottom_faces = cast(list[cq.Face], part.faces("<Z").vals())
        face_area = sum(f.Area() for f in bottom_faces)
        assert face_area > 0

        # Run a few more checks to see if the part was mutated during preparation
        error_pct = (
            abs(orig_part.val().Volume() - part.val().Volume())
            / (orig_part.val().Volume() + part.val().Volume())
            / 2
            * 100
        )
        assert error_pct < 1e-2, "Volume changed"

        error_pct = (
            abs(orig_part.val().Area() - part.val().Area()) / (orig_part.val().Area() + part.val().Area()) / 2 * 100
        )
        assert error_pct < 1e-3, "Surface area changed"

    def test_generate_all(self, builder, tmp_path):
        """Test generate_all exports expected build artifacts."""
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
        """Verify inlet and outlet angles for each part."""

        def get_angle(key):
            """Compute the vertical angle of an exhaust end vector."""
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
        """Verify assembly bounding box dimensions."""
        part = builder.build_part(name).union(builder.build_part(name, right=True))
        bbox = part.val().BoundingBox()

        if name == "driver":
            xmin, xlen = 150, 227
            ymin, ylen = -32, 324
            zmin, zlen = 319, 203
        elif name == "passenger":
            xmin, xlen = 558, 387
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
