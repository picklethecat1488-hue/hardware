"""Contains List main unit tests."""

import argparse
from list import Lister, main, get_args
from unittest.mock import MagicMock, patch
import pytest


class TestListMain:
    """List main unit tests."""

    @pytest.fixture
    def mock_logger(self):
        """Return a mock logger fixture."""
        return MagicMock()

    @pytest.fixture
    def mock_lister(self, mocker):
        """Patch Lister in the list module."""
        return mocker.patch("list.Lister")

    def test_get_args_parsing_targets(self, mocker):
        """Test the argparse configuration for targets."""
        mocker.patch("sys.argv", ["script.py", "targets"])
        args = get_args()
        assert args.command == "targets"

    def test_get_args_parsing_outputs(self, mocker):
        """Test the argparse configuration for outputs."""
        mocker.patch("sys.argv", ["script.py", "outputs"])
        args = get_args()
        assert args.command == "outputs"

    def test_main_targets(self, mock_logger, mock_lister):
        """Verify that targets command triggers list_targets."""
        args = argparse.Namespace(command="targets")
        with patch("list.get_args", return_value=args):
            main()
        mock_lister.return_value.list_targets.assert_called_once()

    def test_main_outputs(self, mock_logger, mock_lister):
        """Verify that outputs command triggers list_outputs."""
        args = argparse.Namespace(command="outputs")
        with patch("list.get_args", return_value=args):
            main()
        mock_lister.return_value.list_outputs.assert_called_once()


class TestListerLogic:
    """Unit tests for Lister internal logic."""

    @pytest.fixture
    def lister(self):
        """Return a lister instance with a mocked manager."""
        manager = MagicMock()
        manager.config = MagicMock()
        return Lister(manager, logger=MagicMock())

    def test_list_targets(self, lister):
        """Verify list_targets calls get_names properly."""
        lister.target_parser.get_names = MagicMock(return_value=["target1", "target2"])
        lister.list_targets()
        lister.target_parser.get_names.assert_called_once()
        assert lister.logger.print.call_count == 3  # Header + 2 targets

    def test_list_outputs_empty(self, lister):
        """Verify list_outputs works with empty targets."""
        lister.manager.router.targets.supporting().for_modes.return_value = []
        lister.list_outputs()
        assert lister.logger.print.call_count == 1  # Header

    def test_get_part_outputs(self, lister):
        """Test computing outputs for a part."""
        lister.manager.router.get_export_types.return_value = ["obj", "stl"]

        # Test with no subassembly
        outputs = lister.get_part_outputs("proj/part", None)
        assert outputs == ["obj/proj/part.obj", "stl/proj/part.stl"]

        # Test with subassembly
        outputs = lister.get_part_outputs("proj/part", "sub")
        assert outputs == ["obj/proj/part_sub.obj", "stl/proj/part_sub.stl"]

        # Test without proj slash
        outputs = lister.get_part_outputs("part", None)
        assert outputs == ["obj/default/part.obj", "stl/default/part.stl"]

    def test_get_diagram_output(self, lister):
        """Test computing output for a diagram."""
        assert lister.get_diagram_output("proj/part") == "svg/proj/proj_diagram.svg"
        assert lister.get_diagram_output("part") == "svg/default/default_diagram.svg"

    def test_get_urdf_output(self, lister):
        """Test computing output for a URDF."""
        assert lister.get_urdf_output("proj/part") == "urdf/proj/part.urdf"
        assert lister.get_urdf_output("part") == "urdf/default/part.urdf"
