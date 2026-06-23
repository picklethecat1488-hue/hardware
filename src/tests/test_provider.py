"""Unit tests for geometry and data provider."""

import os
import pytest
import yaml
from unittest.mock import MagicMock, patch, PropertyMock
from pydantic import BaseModel
from provider.provider import Provider
from provider.target_list import TargetList
from provider.utils import load_manifest, ColorType
from model.utils import method_cache
from provider.types import Section, Mode, MODES, SUBASSEMBLIES, COLOR, MATERIAL, EXPORT, Simulate
from provider.room import Room


class MockConfig(BaseModel):
    """Stub config for testing."""

    ver: str = "1.0"


class MockProvider(Provider):
    """Concrete implementation of Provider for testing."""

    @property
    def default_config(self) -> MockConfig:
        """Return a mock config."""
        return MockConfig()

    @property
    def manifest(self) -> dict:
        """Return a mock manifest."""
        return {
            "part_a": {
                Section.PART: {
                    MODES: [Mode.DEFAULT, Mode.PRINT],
                    SUBASSEMBLIES: ["left"],
                },
                Section.CONFIG: {MODES: ["text", "mount"]},
                Section.VIEW: {MODES: [Mode.DEFAULT], SUBASSEMBLIES: ["left"]},
                COLOR: (0.8, 0.8, 0.8, 1.0),
                MATERIAL: "pla",
                EXPORT: ["stl", "obj"],
            },
            "part_b": {
                Section.PART: {MODES: [Mode.DEFAULT], SUBASSEMBLIES: ["right"]},
                Section.DIAGRAM: {
                    MODES: [Mode.DEFAULT],
                    SUBASSEMBLIES: ["right"],
                },
                COLOR: {"right": (0.9, 0.9, 0.9, 1.0)},
                MATERIAL: {"right": "petg"},
                EXPORT: {"right": "obj"},
            },
        }

    @property
    def part(self) -> dict:
        """Return a mock part registry."""
        if not hasattr(self, "_mock_part"):
            self._mock_part = {
                "part_a": MagicMock(return_value="part_obj"),
                "part_b": MagicMock(return_value="part_obj"),
            }
        return self._mock_part

    @property
    def diagram(self) -> dict:
        """Return a mock diagram registry."""
        if not hasattr(self, "_mock_diagram"):
            self._mock_diagram = {
                "part_b": MagicMock(side_effect=lambda room, targets, mode: room.add("diag", "diag_obj")),
            }
        return self._mock_diagram

    @property
    def config(self) -> dict:
        """Return a mock config registry."""
        if not hasattr(self, "_mock_config"):
            self._mock_config = {
                "text": MagicMock(return_value=None),
                "mount": MagicMock(return_value=None),
            }
        return self._mock_config

    @property
    def view(self) -> dict:
        """Return a mock view registry."""
        if not hasattr(self, "_mock_view"):
            self._mock_view = {
                "part_a": MagicMock(side_effect=lambda room: room.add("item", "shape", color="grey")),
            }
        return self._mock_view


@pytest.fixture
def provider():
    """Provide a fresh mock provider instance for each test to ensure isolation."""
    return MockProvider()


class TestTargetList:
    """TargetList unit tests."""

    def test_supporting_filter(self, provider):
        """Verify supporting() filters targets correctly."""
        targets = provider.targets.supporting(Section.PART)
        assert list(targets) == ["part_a", "part_b"]
        assert isinstance(targets, TargetList)
        assert targets.provider == provider

    def test_for_subassemblies_filter(self, provider):
        """Verify for_subassemblies() filters targets correctly."""
        targets = provider.targets.for_subassemblies(["left"])
        assert list(targets) == ["part_a"]

        targets = provider.targets.for_subassemblies(["right"])
        assert list(targets) == ["part_b"]

    def test_for_modes_filter(self, provider):
        """Verify for_modes() filters targets correctly."""
        targets = provider.targets.for_modes([Mode.PRINT])
        assert list(targets) == ["part_a"]


class TestProviderMetadata:
    """Tests for provider metadata and color resolution."""

    def test_get_color_single(self, provider):
        """Verify get_color returns a single defined color."""
        assert provider.get_color("part_a") == (0.8, 0.8, 0.8, 1.0)

    def test_get_color_dict_specific(self, provider):
        """Verify get_color returns the specific subassembly color from a dict."""
        assert provider.get_color("part_b", "right") == (0.9, 0.9, 0.9, 1.0)

    def test_get_color_dict_fallback_first(self, provider):
        """Verify get_color returns the first dict color when no subassembly is specified."""
        assert provider.get_color("part_b") == (0.9, 0.9, 0.9, 1.0)

    def test_get_color_fallback_config(self, provider):
        """Verify get_color falls back to config color when missing."""
        assert provider.get_color("part_b", "left") == provider.app_config.color

    def test_get_material_single(self, provider):
        """Verify get_material returns a single defined material."""
        assert provider.get_material("part_a") == "pla"

    def test_get_material_dict_specific(self, provider):
        """Verify get_material returns the specific subassembly material from a dict."""
        assert provider.get_material("part_b", "right") == "petg"

    def test_get_material_dict_fallback_first(self, provider):
        """Verify get_material returns the first dict material when no subassembly is specified."""
        assert provider.get_material("part_b") == "petg"

    def test_get_material_fallback_config(self, provider):
        """Verify get_material returns None when missing and no default exists."""
        # 'left' is not in the material dict, so it should fall back to None
        assert provider.get_material("part_b", "left") is None

    def test_get_export_types_single(self, provider):
        """Verify get_export_types returns resolved export formats as a list of strings."""
        assert provider.get_export_types("part_a") == ["stl", "obj"]

    def test_get_export_types_dict_specific(self, provider):
        """Verify get_export_types resolves subassembly-specific format from dict."""
        assert provider.get_export_types("part_b", "right") == ["obj"]

    def test_get_export_types_dict_fallback(self, provider):
        """Verify get_export_types falls back to first format if no subassembly specified."""
        assert provider.get_export_types("part_b") == ["obj"]

    def test_get_export_types_missing_fallback(self, provider):
        """Verify get_export_types returns default ['stl'] when export is missing or None."""
        assert provider.get_export_types("part_b", "left") == ["stl"]

    def test_provider_default_manifest_path(self, monkeypatch):
        """Verify that Provider.manifest defaults to loading a YAML file."""
        import provider.provider

        mock_load = MagicMock(return_value={"test": "data"})
        monkeypatch.setattr(provider.provider, "load_manifest", mock_load)
        # Mock os.path.exists to return True so the provider attempts to load the manifest
        monkeypatch.setattr(os.path, "exists", lambda x: True)

        class MinimalProvider(Provider):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def default_config(self):
                return None

        p = MinimalProvider()
        assert p.manifest == {"test": "data"}
        assert mock_load.call_count == 1
        assert mock_load.call_args[0][0].endswith("manifest.yaml")

    def test_load_manifest(self, tmp_path, provider):
        """Verify that load_manifest correctly parses Enum keys and values."""
        manifest_path = tmp_path / "manifest.yml"
        yaml_content = {
            "part_c": {
                "part": {"modes": ["default"], "subassemblies": ["left"]},
                "color": "grey",
                "material": "abs",
            }
        }
        manifest_path.write_text(yaml.dump(yaml_content))

        loaded = load_manifest(str(manifest_path))
        assert "part_c" in loaded
        assert Section.PART in loaded["part_c"]
        assert loaded["part_c"][Section.PART][MODES] == [Mode.DEFAULT]
        assert loaded["part_c"][COLOR] == ColorType.GREY
        assert loaded["part_c"][MATERIAL] == "abs"

    def test_load_manifest_recursive_imports(self, tmp_path):
        """Verify that load_manifest correctly handles recursive imports and merges material definitions."""
        parent_path = tmp_path / "parent.yml"
        parent_content = {"material": {"pla": {"density": 1.24}, "petg": {"density": 1.27}}}
        parent_path.write_text(yaml.dump(parent_content))

        child_path = tmp_path / "child.yml"
        child_content = {"imports": ["parent.yml"], "part_d": {"part": {"modes": ["default"]}, "material": "pla"}}
        child_path.write_text(yaml.dump(child_content))

        loaded = load_manifest(str(child_path))
        assert "part_d" in loaded
        assert Section.PART in loaded["part_d"]
        assert loaded["part_d"][MATERIAL] == "pla"
        assert MATERIAL in loaded
        assert loaded[MATERIAL]["pla"]["density"] == 1.24
        assert loaded[MATERIAL]["petg"]["density"] == 1.27


class TestProviderOrchestration:
    """Provider base class orchestration tests."""

    def test_build_success(self, provider):
        """Verify successful build orchestration and validation."""
        results = provider.run(provider.targets.supporting(Section.PART))
        assert results == [("part_a", "part_obj"), ("part_b", "part_obj")]
        provider.part["part_a"].assert_called_once_with("part_a", None, Mode.DEFAULT)
        provider.part["part_b"].assert_called_once_with("part_b", None, Mode.DEFAULT)

    def test_configure_success(self, provider):
        """Verify successful configuration orchestration."""
        provider.run(provider.targets.supporting(Section.CONFIG).for_modes(["text"]))
        provider.config["text"].assert_called_once_with("part_a", None)

        provider.config["text"].reset_mock()
        provider.run(provider.targets.supporting(Section.CONFIG).for_modes(["mount"]))
        provider.config["mount"].assert_called_once_with("part_a", None)

    def test_build_multiple_modes(self, provider):
        """Verify that multiple build modes result in multiple handler calls and results."""
        targets = provider.targets.supporting(Section.PART).for_modes([Mode.DEFAULT, Mode.PRINT])
        results = provider.run(targets)
        assert results == [("part_a", ["part_obj", "part_obj"])]
        assert provider.part["part_a"].call_count == 2

    def test_view_success(self, provider):
        """Verify successful view orchestration."""
        results = provider.run(provider.targets.supporting(Section.VIEW))
        assert len(results) == 1
        assert isinstance(results[0][1], Room)
        provider.view["part_a"].assert_called_once()

    def test_view_unregistered_room(self, provider):
        """Verify error when a target supports VIEW in manifest but lacks a function in view registry."""
        m = provider.manifest
        m["part_b"][Section.VIEW] = {MODES: [Mode.DEFAULT]}
        with patch.object(MockProvider, "manifest", new_callable=PropertyMock) as mock_manifest:
            mock_manifest.return_value = m
            with pytest.raises(ValueError, match="No view function registered for room 'part_b'"):
                provider.run(TargetList(provider, ["part_b"], action=Section.VIEW))

    def test_build_action_unsupported(self, provider):
        """Verify ValueError when a target does not support an action."""
        with pytest.raises(ValueError, match="Action 'config' is not supported for part 'part_b'"):
            provider.run(TargetList(provider, ["part_b"], action=Section.CONFIG))

    def test_build_diagram_special_case(self, provider):
        """Verify diagram build returns a single object and validates differently."""
        room = provider.run(TargetList(provider, ["part_b"], action=Section.DIAGRAM))
        assert isinstance(room, Room)
        assert "diag" in room
        assert room["diag"][0] == "diag_obj"

    def test_pre_build_validation_failures(self, provider):
        """Verify various validation failures in _pre_build."""
        with pytest.raises(ValueError, match="Mode 'print' is not supported.*part_b"):
            targets = TargetList(provider, ["part_b"], modes=[Mode.PRINT], action=Section.PART)
            provider.run(targets)

    def test_post_build_length_validation(self, provider):
        """Verify build result length validation."""
        # This test is less relevant now as _run guarantees length by construction,
        # but we keep it to ensure _post_build still executes correctly.
        results = provider.run(TargetList(provider, ["part_a", "part_b"], action=Section.PART))
        assert results == [("part_a", "part_obj"), ("part_b", "part_obj")]
        assert provider.part["part_a"].call_count == 1
        assert provider.part["part_b"].call_count == 1


def test_method_cache_unhashable_args():
    """Verify that method_cache can handle unhashable arguments like lists."""

    class TestClass:
        @method_cache
        def run(self, data: list[int]) -> int:
            return sum(data)

    obj = TestClass()
    assert obj.run([1, 2, 3]) == 6
    assert obj.run([1, 2, 3]) == 6


def test_provider_get_simulate_hooks_default(provider):
    """Verify that provider.get_simulate_hooks returns an empty dict by default."""
    assert provider.get_simulate_hooks("default") == {}


def test_provider_simulate_validation(provider):
    """Verify that simulate hooks validation checks hooks configuration and signatures."""
    # 1. Invalid keys type
    provider.get_simulate_hooks_impl = MagicMock(return_value={"setup": lambda: None})
    with pytest.raises(TypeError, match="Simulation hook key must be a Simulate enum"):
        _ = provider.get_simulate_hooks("default")

    # 2. Non-callable value
    provider.get_simulate_hooks_impl = MagicMock(return_value={Simulate.SETUP: "not_a_callable"})
    with pytest.raises(TypeError, match="Simulation hook value must be callable"):
        _ = provider.get_simulate_hooks("default")

    # 3. Invalid signature for SETUP (must accept at least 4 arguments)
    provider.get_simulate_hooks_impl = MagicMock(return_value={Simulate.SETUP: lambda a, b, c: None})
    with pytest.raises(ValueError, match="must accept at least 4 parameters"):
        _ = provider.get_simulate_hooks("default")

    # 4. Invalid signature for STEP (must accept at least 4 arguments)
    provider.get_simulate_hooks_impl = MagicMock(return_value={Simulate.STEP: lambda a, b, c: None})
    with pytest.raises(ValueError, match="must accept at least 4 parameters"):
        _ = provider.get_simulate_hooks("default")

    # 5. Invalid signature for SETUP with too many required arguments
    provider.get_simulate_hooks_impl = MagicMock(return_value={Simulate.SETUP: lambda a, b, c, d, e: None})
    with pytest.raises(ValueError, match="requires 5 parameters, but only 4 will be provided"):
        _ = provider.get_simulate_hooks("default")

    # 6. Valid setup with *args
    provider.get_simulate_hooks_impl = MagicMock(return_value={Simulate.SETUP: lambda *args: None})
    assert provider.get_simulate_hooks("default") == {
        Simulate.SETUP: provider.get_simulate_hooks_impl.return_value[Simulate.SETUP]
    }
