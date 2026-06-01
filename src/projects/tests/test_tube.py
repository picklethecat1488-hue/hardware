"""Unit tests for the TubeProvider class."""

import math
import pytest
import numpy as np
from unittest.mock import patch
from build123d import *
from model import AppConfig
from projects_config import TubeConfig
from projects import TubeProvider
from provider import Action, Mode, Subassembly, TargetList, ProviderManager


class TestTubeProvider:
    """Tests for TubeProvider implementation."""

    @pytest.fixture
    def provider(self):
        """Fixture for TubeProvider.

        Note: We patch load_manifest to avoid file IO and ensure the manifest
        is aligned with our testing expectations for the skeleton.
        """
        mock_manifest = {
            "driver": {
                Action.CONFIG: {"modes": [Mode.DEFAULT, Mode.MOUNT, Mode.TEXT, Mode.BARE]},
                Action.PART: {
                    "modes": [Mode.DEFAULT, Mode.BARE, Mode.PRINT],
                    "subassemblies": [Subassembly.LEFT, Subassembly.RIGHT],
                },
                Action.SKETCH: {"modes": [Mode.DEFAULT], "subassemblies": [Subassembly.LEFT, Subassembly.RIGHT]},
                Action.WIRE: {"modes": [Mode.DEFAULT]},
                Action.DIAGRAM: {"modes": [Mode.DEFAULT]},
            },
            "part_positions": {Action.VIEW: {"modes": [Mode.DEFAULT]}},
            "overlay": {Action.VIEW: {"modes": [Mode.DEFAULT]}},
        }
        with patch("provider.provider.load_manifest", return_value=mock_manifest):
            yield TubeProvider()

    def test_identity(self, provider):
        """Verify provider name and configuration type."""
        assert provider.name == "tube"
        assert isinstance(provider.default_config, TubeConfig)

    def test_settings_resolution(self, provider):
        """Verify settings property correctly retrieves TubeConfig from app_config."""
        assert isinstance(provider.settings, TubeConfig)
        # Ensure it reflects the defaults from TubeConfig
        assert provider.settings.wall_thickness == provider.default_config.wall_thickness

    def test_measurements_path_override(self, provider):
        """Verify that ProviderManager syncs the provider's specific measurements path."""
        config = AppConfig()
        # Before manager: uses AppConfig default
        assert "measurements.yml" in config.tube.measurements_path  # type: ignore

        mgr = ProviderManager(config, providers=[provider], bootstrap=False)
        mgr.load_configs()
        # After manager: uses TubeProvider's specific path
        assert "tube_measurements.yaml" in config.tube.measurements_path  # type: ignore

    def test_action_registrations(self, provider):
        """Verify that build, config, and view actions are correctly registered."""
        # Build actions
        assert Action.PART in provider.build
        assert Action.WIRE in provider.build
        assert Action.SKETCH in provider.build
        assert Action.DIAGRAM in provider.build

        # Config modes
        assert Mode.DEFAULT in provider.config
        assert Mode.MOUNT in provider.config
        assert Mode.TEXT in provider.config

        # View rooms
        assert "part_positions" in provider.view
        assert "overlay" in provider.view

    def test_run_part_default(self, provider):
        """Verify executing a PART action in DEFAULT mode calls create_part."""
        with patch.object(provider.builder, "create_part", return_value="part_obj") as mock:
            targets = provider.targets.supporting(Action.PART).for_subassemblies([Subassembly.LEFT])
            results = provider.run(targets)
            assert results == [("driver", "part_obj")]
            mock.assert_called_once_with("driver", right=False, tube_only=False)

    def test_run_part_bare(self, provider):
        """Verify executing a PART action in BARE mode calls create_part with tube_only=True."""
        with patch.object(provider.builder, "create_part", return_value="bare_obj") as mock:
            targets = (
                provider.targets.supporting(Action.PART).for_modes([Mode.BARE]).for_subassemblies([Subassembly.LEFT])
            )
            results = provider.run(targets)
            assert results == [("driver", "bare_obj")]
            mock.assert_called_with("driver", right=False, tube_only=True)

    def test_run_part_print(self, provider):
        """Verify executing a PART action in PRINT mode calls create_prepared_part."""
        with patch.object(provider.builder, "create_prepared_part", return_value="print_obj") as mock:
            targets = (
                provider.targets.supporting(Action.PART).for_modes([Mode.PRINT]).for_subassemblies([Subassembly.LEFT])
            )
            results = provider.run(targets)
            assert results == [("driver", "print_obj")]
            mock.assert_called_with("driver", right=False)

    def test_run_part_no_subassembly(self, provider):
        """Verify executing a PART action without a subassembly calls create_tube."""
        with patch.object(provider.builder, "create_tube", return_value="tube_obj") as mock:
            # Manually construct TargetList without subassemblies
            targets = TargetList(provider, ["driver"], action=Action.PART)
            results = provider.run(targets)
            assert results == [("driver", "tube_obj")]
            mock.assert_called_once_with("driver")

    def test_run_wire(self, provider):
        """Verify executing a WIRE action calls create_wire."""
        with patch.object(provider.builder, "create_wire", return_value="wire_obj") as mock:
            targets = provider.targets.supporting(Action.WIRE)
            results = provider.run(targets)
            assert results == [("driver", "wire_obj")]
            mock.assert_called_once_with("driver")

    def test_run_diagram(self, provider):
        """Verify executing a DIAGRAM action calls create_diagram."""
        with patch.object(provider.builder, "create_diagram", return_value="diag_obj") as mock:
            targets = provider.targets.supporting(Action.DIAGRAM)
            result = provider.run(targets)
            assert result == "diag_obj"
            # build_diagram casts the list of targets to names
            mock.assert_called_once_with(names=["driver"])

    def test_run_view_placeholder(self, provider):
        """Verify executing a VIEW action returns the skeleton room data."""
        targets = TargetList(provider, ["part_positions"], action=Action.VIEW)
        results = provider.run(targets)
        assert results == [("part_positions", [])]

    def test_run_config_execution(self, provider):
        """Verify executing a CONFIG action returns None."""
        targets = provider.targets.supporting(Action.CONFIG).for_modes([Mode.DEFAULT])
        result = provider.run(targets)
        assert result is None

    def test_run_sketch(self, provider):
        """Verify executing a SKETCH action calls create_profile."""
        with patch.object(provider.builder, "create_profile", return_value="sketch_obj") as mock:
            targets = provider.targets.supporting(Action.SKETCH).for_subassemblies([Subassembly.RIGHT])
            results = provider.run(targets)
            assert results == [("driver", "sketch_obj")]
            mock.assert_called_once_with(center_deg=90, angle_deg=180)

    def test_unsupported_config_mode_error(self, provider):
        """Verify that requesting an unregistered config mode raises a ValueError."""
        # Mode.BARE is in manifest but not in TubeProvider.config registry skeleton
        targets = TargetList(provider, ["driver"], action=Action.CONFIG, modes=[Mode.BARE])
        with pytest.raises(ValueError, match="No config handler registered for mode 'bare' in tube"):
            provider.run(targets)


class TestTubeBuilder:
    """Manifold builder unit tests."""

    @pytest.fixture
    def builder(self):
        """Return the tube builder fixture."""
        config = AppConfig()
        provider = TubeProvider(config=config)
        return provider.builder

    @pytest.fixture(scope="class", params=["driver", "passenger"])
    def name(self, request):
        """Return a test part name."""
        return request.param

    @pytest.fixture(scope="class", params=[False, True])
    def right(self, request):
        """Return a side selection fixture."""
        return request.param

    def test_wire(self, name, builder):
        """Verify wire path and clamp endpoints."""

        def calc_point_err(v, p):
            return abs((v - Vector(p)).length)

        wire = builder.create_wire(name)
        length = wire.length
        inlet_clamp_start = wire.position_at(0.0)
        inlet_clamp_end = wire.position_at(builder.config.tube.clamp_lengths[0] / length)
        outlet_clamp_start = wire.position_at((length - builder.config.tube.clamp_lengths[-1]) / length)
        outlet_clamp_end = wire.position_at(1.0)
        inlet_key, outlet_key = f"{name}_inlet", f"{name}_outlet"

        # Make sure the clamp starts are correct
        assert calc_point_err(inlet_clamp_start, builder.config.tube.P[inlet_key]) == pytest.approx(0)
        assert calc_point_err(outlet_clamp_start, builder.config.tube.P[outlet_key]) == pytest.approx(0)

        # Check clamp direction and length
        assert calc_point_err(
            (inlet_clamp_end - inlet_clamp_start).normalized(), builder.config.tube.V[inlet_key]
        ) == pytest.approx(0)
        assert calc_point_err(
            (outlet_clamp_end - outlet_clamp_start).normalized(), builder.config.tube.V[outlet_key]
        ) == pytest.approx(0)
        assert (inlet_clamp_end - inlet_clamp_start).length == pytest.approx(builder.config.tube.clamp_lengths[0])
        assert (outlet_clamp_end - outlet_clamp_start).length == pytest.approx(builder.config.tube.clamp_lengths[-1])

    def test_create_profile(self, builder):
        """Test profile sketch generation for a valid center/angle profile."""
        sketch = builder.create_profile(45, 90, outer_radius=10, inner_radius=5, joint_space=0)
        # Area of a quarter annulus: (90/360) * pi * (R^2 - r^2)
        expected_area = math.pi * (10**2 - 5**2) / 4
        assert sketch.area == pytest.approx(expected_area)

    def test_create_profile_invalid_inner_radius(self, builder):
        """Ensure invalid profile radii raise ValueError."""
        with pytest.raises(ValueError):
            builder.create_profile(45, 90, outer_radius=10, inner_radius=10)

    def test_build_clean_tool(self, name, builder):
        """Test clean tool creation for a given part name."""
        clean_tool = builder.create_clean_tool(name)
        assert clean_tool is not None
        assert clean_tool.volume > 0

    def test_part_fits_together(self, builder, name, right):
        """Test that mirrored parts do not intersect."""
        # Make sure parts do not self intersect
        part = builder.create_part(name, right=right)
        other_part = builder.create_part(name, right=(not right))
        intersection = part.intersect(other_part)
        assert (intersection.volume if intersection else 0) == pytest.approx(0), (
            f"intersection detected between {name} parts"
        )

    def test_part_doesnt_overlap(self, builder, name, right):
        """Ensure parts from different assemblies do not intersect."""
        part = builder.create_part(name, right=right)
        other_name = next(x for x in builder.tube_config.names if x != name)
        other_part = builder.create_part(other_name, right=not right)
        intersection = part.intersect(other_part)
        assert (intersection.volume if intersection else 0) == pytest.approx(0), (
            f"intersection detected between {name},right={right} and {other_name},right={not right}"
        )

    def test_in_bounds(self, builder, name, right):
        """Verify part fits inside bound box volume."""
        part = builder.create_part(name, right=right)
        proj_bounds = builder.config.bound_box
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
            + [clamp_pos[0] for clamp_pos in builder.tube_config.clamp_positions[name][1:-1] if clamp_pos is not None]
            + [(length - builder.tube_config.clamp_lengths[-1]) / length]
        )
        expected = np.array(builder.tube_config.clamp_diameters) / 2
        """Test if manifold clamps satisfy fitment requirements."""
        part = builder.create_part(name, right=right)
        pos, len, expected = (
            offsets[clamp_idx],
            builder.tube_config.clamp_lengths[clamp_idx],
            expected[clamp_idx],
        )

        # Check if we can move clamp over section
        clamp_off = builder.create_ring(
            name, pos, len, outer_radius=expected + builder.config.tube.wall_thickness, inner_radius=expected
        )
        intersection_off = part.intersect(clamp_off)
        assert (intersection_off.volume if intersection_off else 0) == pytest.approx(0)

        # Check if we can push clamp onto section
        clamp_on = builder.create_ring(
            name, pos, len, outer_radius=expected + builder.config.tube.wall_thickness, inner_radius=expected - 0.01
        )
        intersection_on = part.intersect(clamp_on)
        assert intersection_on is not None and intersection_on.volume > 0

    def test_part(self, name, right, builder):
        """Verify rebuilt part geometry matches manifold volume."""
        if name != "driver" and name != "passenger":
            raise ValueError(f"Invalid name: {name}")
        manifold = builder.create_tube(name, right=right, half_tube=True)
        part = builder.create_part(name, right=right)
        manifold_vol = manifold.volume
        intersection = part.intersect(manifold)
        manifold_from_parts_vol = intersection.volume if intersection else 0

        error_pct = abs(manifold_vol - manifold_from_parts_vol) / (manifold_vol + manifold_from_parts_vol) / 2 * 100
        # less than 0.5% error for each rebuilt part.
        assert error_pct < 0.5

    def test_prepared_part(self, name, right, builder):
        """Verify the prepared part is printable and stable."""
        orig_part = builder.create_part(name, right=right)
        part = builder.create_prepared_part(name, right=right)

        # Ensure the part is a watertight solid
        assert part.is_valid
        assert part.volume > 0

        # Ensure the part is touching the print bed
        bottom_faces = part.faces().sort_by(Axis.Z)[:1]
        face_area = sum(f.area for f in bottom_faces)
        assert face_area > 0

        # Run a few more checks to see if the part was mutated during preparation
        error_pct = abs(orig_part.volume - part.volume) / (orig_part.volume + part.volume) / 2 * 100
        assert error_pct < 1e-2, "Volume changed"

        error_pct = abs(orig_part.area - part.area) / (orig_part.area + part.area) / 2 * 100
        assert error_pct < 1e-3, "Surface area changed"

    def test_end_angle(self, builder, name):
        """Verify inlet and outlet angles for each part."""

        def get_angle(key):
            """Compute the vertical angle of an exhaust end vector."""
            z_axis = Vector(0, 0, 1)
            v_test = Vector(builder.tube_config.V[key])
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
        part = Compound(builder.create_part(name).fuse(builder.create_part(name, right=True)))
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


class TestTubeConfigurator:
    """Manifold configurator unit tests."""

    @pytest.fixture
    def configurator(self):
        """Return the tube configurator fixture."""
        config = AppConfig()
        provider = TubeProvider(config=config)
        return provider.configurator

    def test_get_orientation_normal(self, configurator):
        """Verify orientation detection logic identifies the peak correctly."""
        # Setup a tube centered at Z=2. Path is at Z=0.
        with BuildPart() as tube:
            Box(10, 10, 10)
        tube_obj = tube.part.moved(Location(Vector(0, 0, 2)))  # type: ignore
        path = configurator.builder.create_wire("driver")

        # Manually populate caches since methods use id(obj)
        configurator._tube_cache[id(tube_obj)] = tube_obj
        configurator._path_cache[id(path)] = path

        # Orientation should be "normal" (up) because tube center (Z=2) is
        # closer to midpoint_up (Z=1) than midpoint_down (Z=-1) relative to path.
        assert configurator.get_orientation_normal(id(tube_obj), id(path)) is True

    def test_get_part_position(self, configurator):
        """Verify get_part_position calculates the correct attachment vector."""
        with BuildPart() as tube:
            Box(10, 10, 10)
        tube_obj = tube.part.moved(Location(Vector(0, 0, 2)))  # type: ignore
        path = configurator.builder.create_wire("driver")

        radius = min(configurator.tube_config.clamp_diameters) / 2
        result = configurator.get_part_position(tube_obj, path, 0.5)

        expected = path.position_at(0.5) + Vector(0, 0, radius)
        assert result == expected

    def test_config_clamp_updates_config(self, configurator, monkeypatch):
        """Verify that config_clamp updates the underlying TubeConfig."""
        name = "driver"
        # Mock find_best_angle to avoid expensive CAD collision scanning
        monkeypatch.setattr(configurator, "find_best_angle", lambda *args, **kwargs: 45.0)

        configurator.config_clamp(name)

        # Verify that the angle for the middle clamp (index 1) was updated
        _, angle = configurator.tube_config.clamp_positions[name][1]
        assert angle == 45.0

    def test_config_text_logo_updates_config(self, configurator, monkeypatch):
        """Verify that config_text_logo updates the underlying TubeConfig."""
        name = "passenger"
        monkeypatch.setattr(configurator, "find_best_angle", lambda *args, **kwargs: 180.0)

        configurator.config_text_logo(name)

        _, angle = configurator.tube_config.logo_text_positions[name]
        assert angle == 180.0

    def test_config_routing(self, configurator):
        """Verify that routing methods call the correct underlying config methods."""
        with (
            patch.object(configurator, "config_clamp") as mock_clamp,
            patch.object(configurator, "config_text_logo") as mock_text,
        ):
            configurator.config_default("driver", None)
            assert mock_clamp.call_count == 1
            assert mock_text.call_count == 1

            mock_clamp.reset_mock()
            mock_text.reset_mock()
            configurator.config_mount("driver", None)
            assert mock_clamp.call_count == 1

            mock_clamp.reset_mock()
            configurator.config_text("driver", None)
            assert mock_text.call_count == 1
