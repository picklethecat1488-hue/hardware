"""Unit tests for the TargetParser utility."""

import pytest
from unittest.mock import MagicMock
from target_parser import TargetParser
from provider import Section, Mode, SUBASSEMBLIES, MODES


class TestTargetParser:
    """Test suite for parsing and resolving target strings."""

    @pytest.fixture
    def mock_router(self):
        """Create a mock ProviderRouter with a sample manifest."""
        router = MagicMock()
        router.manifest = {
            "tube/driver": {
                Section.PART: {MODES: [Mode.DEFAULT, Mode.PRINT], SUBASSEMBLIES: ["left", "right"]},
                Section.VIEW: {MODES: [Mode.DEFAULT]},
            },
            "tube/wire": {
                Section.PART: {MODES: [Mode.DEFAULT]},
            },
            "electronics/case": {
                Section.PART: {MODES: [Mode.DEFAULT, Mode.PRINT]},
            },
        }
        # Mock router.targets to return a TargetList-like behavior
        router.targets.supporting.side_effect = lambda a: MagicMock()
        return router

    @pytest.fixture
    def parser(self, mock_router):
        """Initialize the TargetParser."""
        return TargetParser(mock_router)

    def test_parse_simple(self, parser):
        """Verify parsing of simple target strings."""
        info = parser.parse("tube/driver", Section.PART)
        assert info.target == "tube/driver"
        assert info.subassembly is None
        assert info.mode == Mode.DEFAULT

    def test_parse_complex(self, parser):
        """Verify parsing of target strings with subassemblies, modes, and actions."""
        # Format: target_subassembly:action/mode
        info = parser.parse("tube/driver_left:part/print", Section.PART)
        assert info.target == "tube/driver"
        assert info.subassembly == "left"
        assert info.action == Section.PART
        assert info.mode == Mode.PRINT

    def test_parse_action_mismatch(self, parser):
        """Verify that parse returns None if the explicit action doesn't match the default."""
        info = parser.parse("tube/driver:view", Section.PART)
        assert info is None

    def test_resolve_targets_wildcard(self, parser):
        """Verify wildcard matching for targets."""
        # Matches provider wildcard
        matches = parser.resolve_targets("tube/*", Section.PART, Mode.DEFAULT)
        assert set(matches) == {"tube/driver", "tube/wire"}

        # Matches specific target name wildcard
        matches = parser.resolve_targets("*/driver", Section.PART, Mode.DEFAULT)
        assert matches == ["tube/driver"]

    def test_resolve_targets_mode_filtering(self, parser):
        """Verify that resolved targets are filtered by mode support."""
        # 'tube/wire' does not support 'print' mode
        matches = parser.resolve_targets("tube/*", Section.PART, Mode.PRINT)
        assert matches == ["tube/driver"]

    def test_resolve_subassemblies_wildcard(self, parser):
        """Verify wildcard matching for subassemblies."""
        subs = parser.resolve_subassemblies("*", ["tube/driver"], Section.PART)
        assert set(subs) == {"left", "right"}

        subs = parser.resolve_subassemblies("l*", ["tube/driver"], Section.PART)
        assert subs == ["left"]

    def test_get_names_combinations(self, parser):
        """Verify the generation of all valid target argument combinations."""
        names = parser.get_names([Section.VIEW])

        # Should include base target
        assert "tube/driver" in names
        # Should include target with explicit action
        assert "tube/driver:view" in names
        # Should include subassemblies for supported actions
        # Note: In mock, VIEW doesn't explicitly list subassemblies,
        # so we check PART for that logic
        names_part = parser.get_names([Section.PART])
        assert "tube/driver_left" in names_part
        assert "tube/driver_left:part/print" in names_part

    def test_resolve_no_matches(self, parser):
        """Verify that resolve raises ValueError when no targets match."""
        with pytest.raises(ValueError, match="No matching part targets found"):
            parser.resolve("non_existent", Section.PART)

        with pytest.raises(ValueError, match="No part targets matched wildcard pattern"):
            parser.resolve("ghost/*", Section.PART)
