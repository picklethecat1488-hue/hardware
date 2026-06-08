"""Unit tests for the ExhaustManifoldsProvider class."""

import math
import pytest
import numpy as np
from typing import cast
from unittest.mock import patch
from build123d import *
from model import AppConfig
from projects_config import ExhaustManifoldsConfig
from projects.exhaust_manifolds import ExhaustManifoldsProvider
from provider import Action, Mode, TargetList, ProviderManager, MODES


class TestExhaustManifoldsProvider:
    """Tests for ExhaustManifoldsProvider implementation."""

    @pytest.fixture
    def provider(self):
        """Fixture for ExhaustManifoldsProvider.

        Note: We patch load_manifest to avoid file IO and ensure the manifest
        is aligned with our testing expectations for the skeleton.
        """
        mock_manifest = {
            "driver": {
                Action.CONFIG: {MODES: ["mount", "text"]},
                Action.PART: {
                    "modes": [Mode.DEFAULT, Mode.PRINT],
                    "subassemblies": ["left", "right"],
                },
                Action.DIAGRAM: {"modes": [Mode.DEFAULT]},
            },
            "passenger": {
                Action.CONFIG: {MODES: ["mount", "text"]},
                Action.PART: {
                    "modes": [Mode.DEFAULT, Mode.PRINT],
                    "subassemblies": ["left", "right"],
                },
                Action.DIAGRAM: {"modes": [Mode.DEFAULT]},
            },
            "part_positions": {Action.VIEW: {"modes": [Mode.DEFAULT]}},
            "overlay": {Action.VIEW: {"modes": [Mode.DEFAULT]}},
            "wire": {Action.VIEW: {"modes": [Mode.DEFAULT]}},
            "sketch": {Action.VIEW: {"modes": [Mode.DEFAULT]}},
        }
        with patch("provider.provider.load_manifest", return_value=mock_manifest):
            yield ExhaustManifoldsProvider()

    def test_identity(self, provider):
        """Verify provider name and configuration type."""
        assert provider.name == "exhaust_manifolds"
        assert isinstance(provider.default_config, ExhaustManifoldsConfig)

    def test_settings_resolution(self, provider):
        """Verify settings property correctly retrieves ExhaustManifoldsConfig from app_config."""
        assert isinstance(provider.settings, ExhaustManifoldsConfig)
        # Ensure it reflects the defaults from ExhaustManifoldsConfig
        assert provider.settings.wall_thickness == provider.default_config.wall_thickness

    def test_measurements_path_override(self, provider):
        """Verify that ProviderManager syncs the provider's specific measurements path."""
        config = AppConfig()
        mgr = ProviderManager(config, providers=[provider], bootstrap=False)
        mgr.load_configs()
        # After manager: uses ExhaustManifoldsProvider's specific path
        assert "measurements.yaml" in provider.settings.measurements_path  # type: ignore

    def test_action_registrations(self, provider):
        """Verify that build, config, and view actions are correctly registered."""
        # Build registries are singular and target-aware
        assert "driver" in provider.part
        assert "passenger" in provider.part
        assert "driver" in provider.diagram
        assert "passenger" in provider.diagram

        # Config modes (dynamic string keys)
        assert "mount" in provider.config
        assert "text" in provider.config

        # View rooms
        assert "part_positions" in provider.view
        assert "overlay" in provider.view
        assert "wire" in provider.view
        assert "sketch" in provider.view

    def test_run_part_default(self, provider):
        """Verify executing a PART action in DEFAULT mode calls create_part."""
        with patch.object(provider.builder, "create_part", return_value="part_obj") as mock:
            targets = provider.targets.supporting(Action.PART).for_subassemblies(["left"])
            results = provider.run(targets)
            assert results == [("driver", "part_obj"), ("passenger", "part_obj")]
            assert mock.call_count == 2

    def test_run_part_print(self, provider):
        """Verify executing a PART action in PRINT mode calls create_prepared_part."""
        with patch.object(provider.builder, "create_prepared_part", return_value="print_obj") as mock:
            targets = provider.targets.supporting(Action.PART).for_modes([Mode.PRINT]).for_subassemblies(["left"])
            results = provider.run(targets)
            assert results == [("driver", "print_obj"), ("passenger", "print_obj")]
            assert mock.call_count == 2

    def test_run_part_no_subassembly(self, provider):
        """Verify executing a PART action without a subassembly calls create_manifold."""
        with patch.object(provider.builder, "create_manifold", return_value="manifold_obj") as mock:
            # Manually construct TargetList without subassemblies
            targets = TargetList(provider, ["driver"], action=Action.PART)
            results = provider.run(targets)
            assert results == [("driver", "manifold_obj")]
            mock.assert_called_once_with("driver")

    def test_run_diagram(self, provider):
        """Verify executing a DIAGRAM action calls create_diagram."""
        with patch.object(provider.builder, "create_diagram", return_value="diag_obj") as mock:
            targets = provider.targets.supporting(Action.DIAGRAM)
            result = provider.run(targets)
            assert result == "diag_obj"
            # build_diagram casts the list of targets to names
            mock.assert_called_once_with(names=("driver", "passenger"))

    def test_run_config_execution(self, provider):
        """Verify executing a CONFIG action returns None."""
        targets = provider.targets.supporting(Action.CONFIG).for_modes([Mode.DEFAULT])
        result = provider.run(targets)
        assert result is None

    def test_unsupported_config_mode_error(self, provider):
        """Verify that requesting an unregistered config mode raises a ValueError."""
        # 'bare' is no longer supported
        targets = TargetList(provider, ["driver"], action=Action.CONFIG, modes=["bare"])
        with pytest.raises(ValueError, match="No config handler registered for mode 'bare' in exhaust_manifolds"):
            provider.run(targets)


class TestExhaustManifoldsBuilder:
    """Manifold builder unit tests."""

    @pytest.fixture
    def builder(self):
        """Return the exhaust_manifolds builder fixture."""
        config = AppConfig()
        provider = ExhaustManifoldsProvider(config=config)
        # Bootstrap to load .env overrides and attach config.exhaust_manifolds
        ProviderManager(config, providers=[provider])
        return provider.builder

    @pytest.fixture(scope="class", params=["driver", "passenger"])
    def name(self, request):
        """Return a test part name."""
        return request.param

    @pytest.fixture(scope="class", params=[False, True])
    def right(self, request):
        """Return a side selection fixture."""
        return request.param

    def _calc_vol(self, shape) -> float:
        """Sum volumes of all solids in the shape to handle ShapeList."""
        return sum(s.volume for s in shape.solids()) if shape else 0.0

    def _calc_area(self, shape) -> float:
        """Sum areas of all faces in the shape to handle ShapeList."""
        return sum(f.area for f in shape.faces()) if shape else 0.0

    def test_wire(self, name, builder):
        """Verify wire path and clamp endpoints."""

        def calc_point_err(v, p):
            return abs((v - Vector(p)).length)

        wire = builder.create_wire(name)
        length = wire.length
        inlet_clamp_start = wire.position_at(0.0)
        inlet_clamp_end = wire.position_at(builder.exhaust_manifolds_config.clamp_lengths[0] / length)
        outlet_clamp_start = wire.position_at((length - builder.exhaust_manifolds_config.clamp_lengths[-1]) / length)
        outlet_clamp_end = wire.position_at(1.0)
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"

        # Make sure the clamp starts are correct
        assert calc_point_err(inlet_clamp_start, builder.exhaust_manifolds_config.P[inlet_key]) == pytest.approx(0)
        assert calc_point_err(outlet_clamp_start, builder.exhaust_manifolds_config.P[outlet_key]) == pytest.approx(0)

        # Check clamp direction and length
        assert calc_point_err(
            (inlet_clamp_end - inlet_clamp_start).normalized(), builder.exhaust_manifolds_config.V[inlet_key]
        ) == pytest.approx(0)
        assert calc_point_err(
            (outlet_clamp_end - outlet_clamp_start).normalized(), builder.exhaust_manifolds_config.V[outlet_key]
        ) == pytest.approx(0)
        assert (inlet_clamp_end - inlet_clamp_start).length == pytest.approx(
            builder.exhaust_manifolds_config.clamp_lengths[0]
        )
        assert (outlet_clamp_end - outlet_clamp_start).length == pytest.approx(
            builder.exhaust_manifolds_config.clamp_lengths[-1]
        )

    def test_create_profile(self, builder):
        """Test profile sketch generation for a valid center/angle profile."""
        sketch = builder.create_profile(45, 90, outer_radius=10, inner_radius=5, joint_space=0)
        # Area of a quarter annulus: (90/360) * pi * (R^2 - r^2)
        expected_area = math.pi * (10**2 - 5**2) / 4
        assert sketch.sketch.area == pytest.approx(expected_area)

    def test_create_profile_invalid_inner_radius(self, builder):
        """Ensure invalid profile radii raise ValueError."""
        with pytest.raises(ValueError):
            builder.create_profile(45, 90, outer_radius=10, inner_radius=10)

    def test_build_clean_tool(self, name, builder):
        """Test clean tool creation for a given part name."""
        clean_tool = builder.create_clean_tool(name)
        assert clean_tool.part is not None
        assert clean_tool.part.volume > 0

    def test_part_fits_together(self, builder, name, right):
        """Test that mirrored parts do not intersect."""
        # Make sure parts do not self intersect
        part = builder.create_part(name, right=right).part
        other_part = builder.create_part(name, right=(not right)).part
        intersection = part.intersect(other_part)

        vol = self._calc_vol(intersection)
        assert vol == pytest.approx(0, abs=1e-3), f"intersection detected between {name} parts"

    def test_part_doesnt_overlap(self, builder, name, right):
        """Ensure parts from different assemblies do not intersect."""
        part = builder.create_part(name, right=right).part
        other_name = next(x for x in builder.exhaust_manifolds_config.names if x != name)
        other_part = builder.create_part(other_name, right=not right).part
        intersection = part.intersect(other_part)

        vol = self._calc_vol(intersection)
        assert vol == pytest.approx(0, abs=1e-3), (
            f"intersection detected between {name},right={right} and {other_name},right={not right}"
        )

    def test_in_bounds(self, builder, name, right):
        """Verify part fits inside bound box volume."""
        part = builder.create_part(name, right=right).part
        # Reconstruct bound box logic since it moved to viewer
        x_len = max(builder.exhaust_manifolds_config.x_bounds) - min(builder.exhaust_manifolds_config.x_bounds)
        y_len = max(builder.exhaust_manifolds_config.y_bounds) - min(builder.exhaust_manifolds_config.y_bounds)
        z_len = max(builder.exhaust_manifolds_config.z_bounds) - min(builder.exhaust_manifolds_config.z_bounds)
        center = (
            min(builder.exhaust_manifolds_config.x_bounds) + x_len / 2,
            min(builder.exhaust_manifolds_config.y_bounds) + y_len / 2,
            min(builder.exhaust_manifolds_config.z_bounds) + z_len / 2,
        )
        with BuildPart() as bounds:
            Box(x_len, y_len, z_len)
            proj_bounds = cast(Part, bounds.part).move(Location(center))

        volume = part.cut(proj_bounds).volume

        assert volume == pytest.approx(0)

    def test_can_clamp(self, name, right, builder):
        """Test if a representative clamp bed satisfies the clamp property."""
        clamp_idx = 1
        path = builder.create_wire(name)
        length = path.length

        # Map clamp_idx to clamp parameters
        offsets = (
            [0]
            + [
                clamp_pos[0]
                for clamp_pos in builder.exhaust_manifolds_config.clamp_positions[name][1:-1]
                if clamp_pos is not None
            ]
            + [(length - builder.exhaust_manifolds_config.clamp_lengths[-1]) / length]
        )
        expected = np.array(builder.exhaust_manifolds_config.clamp_diameters) / 2
        """Test if manifold clamps satisfy fitment requirements."""
        part = builder.create_part(name, right=right).part
        pos, len, expected = (
            offsets[clamp_idx],
            builder.exhaust_manifolds_config.clamp_lengths[clamp_idx],
            expected[clamp_idx],
        )

        # Check if we can move clamp over section (clamp_off is BuildPart)
        clamp_off = builder.create_ring(
            name,
            pos,
            len,
            outer_radius=expected + builder.exhaust_manifolds_config.wall_thickness,
            inner_radius=expected,
        )
        intersection_off = part.intersect(clamp_off.part)  # part is Part, clamp_off.part is Part
        assert self._calc_vol(intersection_off) == pytest.approx(0, abs=1e-3)

        # Check if we can push clamp onto section (clamp_on is BuildPart)
        clamp_on = builder.create_ring(
            name,
            pos,
            len,
            outer_radius=expected + builder.exhaust_manifolds_config.wall_thickness,
            inner_radius=expected - 0.01,
        )
        intersection_on = part.intersect(clamp_on.part)  # part is Part, clamp_on.part is Part
        assert self._calc_vol(intersection_on) > 0

    def test_part(self, name, right, builder):
        """Verify rebuilt part geometry matches manifold volume."""
        if name != "driver" and name != "passenger":
            raise ValueError(f"Invalid name: {name}")
        manifold = builder.create_manifold(name, right=right, half_tube=True)
        part = builder.create_part(name, right=right).part
        manifold_vol = manifold.part.volume
        intersection = part.intersect(manifold.part)
        manifold_from_parts_vol = self._calc_vol(intersection)

        error_pct = abs(manifold_vol - manifold_from_parts_vol) / (manifold_vol + manifold_from_parts_vol) / 2 * 100
        # less than 0.5% error for each rebuilt part.
        assert error_pct < 0.5

    def test_prepared_part(self, name, right, builder):
        """Verify the prepared part is printable and stable."""
        orig_part = builder.create_part(name, right=right).part
        part = builder.create_prepared_part(name, right=right).part

        # Ensure the part is a watertight solid
        assert part.is_valid
        assert self._calc_vol(part) > 0

        # Ensure the part is touching the print bed
        bottom_faces = part.faces().sort_by(Axis.Z)[:1]
        face_area = self._calc_area(Compound(bottom_faces))
        assert face_area > 0

        # Run a few more checks to see if the part was mutated during preparation
        error_pct = (
            abs(self._calc_vol(orig_part) - self._calc_vol(part))
            / (self._calc_vol(orig_part) + self._calc_vol(part))
            / 2
            * 100
        )
        assert error_pct < 1e-2, "Volume changed"

        error_pct = (
            abs(self._calc_area(orig_part) - self._calc_area(part))
            / (self._calc_area(orig_part) + self._calc_area(part))
            / 2
            * 100
        )
        assert error_pct < 1e-3, "Surface area changed"

    def test_end_angle(self, builder, name):
        """Verify inlet and outlet angles for each part."""

        def get_angle(key):
            """Compute the vertical angle of an exhaust end vector."""
            z_axis = Vector(0, 0, 1)
            v_test = Vector(builder.exhaust_manifolds_config.V[key])
            angle = 90 - v_test.get_angle(z_axis)
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
        part = Compound(builder.create_part(name).part.fuse(builder.create_part(name, right=True).part).solids())
        bbox = part.bounding_box()

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
        assert round(bbox.min.X) == xmin
        assert round(bbox.size.X) == xlen

        assert round(bbox.min.Y) == ymin
        assert round(bbox.size.Y) == ylen

        assert round(bbox.min.Z) == zmin
        assert round(bbox.size.Z) == zlen


class TestExhaustManifoldsConfigurator:
    """Manifold configurator unit tests."""

    @pytest.fixture
    def configurator(self):
        """Return the exhaust_manifolds configurator fixture."""
        config = AppConfig()
        provider = ExhaustManifoldsProvider(config=config)
        # Bootstrap to load .env overrides and attach config.exhaust_manifolds
        ProviderManager(config, providers=[provider])
        return provider.configurator

    def test_get_orientation_normal(self, configurator):
        """Verify orientation detection logic identifies the peak correctly."""
        path = configurator.builder.create_wire("driver")
        pos = path.position_at(0.5)
        # Setup a tube centered above the actual path position.
        with BuildPart() as tube_builder:
            Box(10, 10, 10)
        tube_obj = cast(Part, tube_builder.part).moved(Location(pos + Vector(0, 0, 2)))

        # Manually populate caches since methods use id(obj)
        configurator._tube_cache[id(tube_obj)] = tube_obj
        configurator._path_cache[id(path)] = path

        # Orientation should be "normal" (up) because tube center (Z=2) is
        # closer to midpoint_up (Z=1) than midpoint_down (Z=-1) relative to path.
        assert configurator.get_orientation_normal(id(tube_obj), id(path)) is True

    def test_get_part_position(self, configurator):
        """Verify get_part_position calculates the correct attachment vector."""
        path = configurator.builder.create_wire("driver")
        pos = path.position_at(0.5)
        # Setup a tube centered above the actual path position.
        with BuildPart() as tube_builder:
            Box(10, 10, 10)
        tube_obj = cast(Part, tube_builder.part).moved(Location(pos + Vector(0, 0, 2)))

        radius = min(configurator.exhaust_manifolds_config.clamp_diameters) / 2
        result = configurator.get_part_position(tube_obj, path, 0.5)

        expected = path.position_at(0.5) + Vector(0, 0, radius)
        assert result == expected

    def test_config_clamp_updates_config(self, configurator, monkeypatch):
        """Verify that config_clamp updates the underlying ExhaustManifoldsConfig."""
        name = "driver"
        # Mock find_best_angle to avoid expensive CAD collision scanning
        monkeypatch.setattr(configurator, "find_best_angle", lambda *args, **kwargs: 45.0)

        configurator.config_clamp(name)

        # Verify that the angle for the middle clamp (index 1) was updated
        _, angle = configurator.exhaust_manifolds_config.clamp_positions[name][1]
        assert angle == 45.0

    def test_config_text_logo_updates_config(self, configurator, monkeypatch):
        """Verify that config_text_logo updates the underlying ExhaustManifoldsConfig."""
        name = "passenger"
        monkeypatch.setattr(configurator, "find_best_angle", lambda *args, **kwargs: 180.0)

        configurator.config_text_logo(name)

        _, angle = configurator.exhaust_manifolds_config.logo_text_positions[name]
        assert angle == 180.0

    def test_config_routing(self, configurator):
        """Verify that routing methods call the correct underlying config methods."""
        with (
            patch.object(configurator, "config_clamp") as mock_clamp,
            patch.object(configurator, "config_text_logo") as mock_text,
        ):
            mock_text.reset_mock()
            configurator.config_mount("driver", None)
            assert mock_clamp.call_count == 1

            mock_clamp.reset_mock()
            configurator.config_text("driver", None)
            assert mock_text.call_count == 1


class TestExhaustManifoldsViewer:
    """Manifold viewer unit tests."""

    @pytest.fixture
    def viewer(self):
        """Return the exhaust_manifolds viewer fixture."""
        config = AppConfig()
        provider = ExhaustManifoldsProvider(config=config)
        # Bootstrap to load .env overrides and attach config.exhaust_manifolds
        ProviderManager(config, providers=[provider])
        return provider.viewer

    def test_get_rgba(self, viewer):
        """Verify RGBA color conversion."""
        # Known color
        assert viewer._get_rgba("red", 0.5) == (1.0, 0.0, 0.0, 0.5)
        # Default fallback
        assert viewer._get_rgba("unknown", 1.0) == (1.0, 1.0, 1.0, 1.0)

    def test_build_markers(self, viewer):
        """Verify marker creation methods return valid geometry."""
        # Sphere marker
        assert viewer.create_part_position_point("driver", 0.5, right=False).volume > 0
        # Cone marker
        assert viewer.create_solid_center_point("passenger", right=True).volume > 0

    def test_room_logic(self, viewer):
        """Verify room dictionary generation logic."""
        for room_fn in [viewer.show_positions_room, viewer.show_overlay_room, viewer.show_profiles_room]:
            data = room_fn()
            assert isinstance(data, dict)
            assert len(data) > 0
            for val in data.values():
                assert len(val) == 3  # (obj, color_name, alpha)

    def test_view_interfaces(self, viewer):
        """Verify orchestrator-compatible view interfaces."""
        for view_fn in [viewer.view_part_positions, viewer.view_overlay, viewer.view_wire, viewer.view_sketch]:
            results = view_fn()
            assert isinstance(results, list)
            for _, rgba in results:
                assert len(rgba) == 4
