"""Contains Build main unit tests."""

import argparse
from build import Builder, main, get_args, str2bool
from pathlib import Path
from build123d import BuildPart
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from provider import Action, Mode, TargetList, Room, SUBASSEMBLIES


class TestBuildMain:
    """Build main unit tests."""

    @pytest.fixture
    def mock_logger(self):
        """Return a mock logger fixture."""
        return MagicMock()

    @pytest.fixture
    def mock_builder(self, mocker):
        """Patch Builder in the build module."""
        return mocker.patch("build.Builder")

    def test_get_args_parsing(self, mocker):
        """Test the argparse configuration directly."""
        mocker.patch("sys.argv", ["script.py", "-e", "foo.env", "-out", "tmp", "-d", "--", "part1/left"])
        args = get_args()
        assert args.env == "foo.env"
        assert args.outdir == "tmp"
        assert args.diagram is True
        assert args.targets == ["part1/left"]

    def test_main_diagram_path(self, mock_logger, mock_builder, tmp_path):
        """Check if generate_diagram was called with correct unpacked gen_args."""
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram=True, parts=False, targets=["schema"])
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(out_dir=tmp_path, names=["schema"])

        assert Path(tmp_path).exists()
        mock_logger.done.assert_called_once()

    def test_main_output_path(self, mock_logger, mock_builder, tmp_path):
        """Test positional targets."""
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram=False, parts=True, targets=["part1"])
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(out_dir=tmp_path, names=["part1"])

        mock_logger.done.assert_called_once()

    def test_main_output_env_path(self, mock_logger, mock_builder, tmp_path):
        """Check if generate_diagram was called with correct unpacked gen_args."""
        args = argparse.Namespace(outdir=tmp_path, env=f"{tmp_path}.env", diagram=True, parts=True, targets=[])
        main(mock_logger, args)
        mock_builder.return_value.config.dump_env.assert_called_once_with(f"{tmp_path}.env")
        mock_logger.done.assert_called_once()

    def test_main_generate_all_fallback(self, mock_logger, mock_builder, tmp_path):
        """Test the else block when no flags are provided."""
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram=True, parts=True, targets=[])

        main(mock_logger, args)

        mock_builder.return_value.generate_all.assert_called_once_with(out_dir=tmp_path)

        mock_logger.done.assert_called_once()

    def test_validation_error(self, mocker):
        """Verify that providing both flags as False raises a SystemExit (via parser.error)."""
        mocker.patch("sys.argv", ["script.py", "--diagram=false", "--parts=false"])
        with pytest.raises(SystemExit):
            get_args()


def test_str2bool():
    """Verify boolean string conversion."""
    assert str2bool("true") is True
    assert str2bool("yes") is True
    assert str2bool("1") is True
    assert str2bool("false") is False
    assert str2bool("no") is False
    assert str2bool("0") is False
    with pytest.raises(argparse.ArgumentTypeError):
        str2bool("invalid")


class TestBuilderLogic:
    """Unit tests for Builder internal logic."""

    @pytest.fixture
    def builder(self):
        """Return a builder instance with a mocked manager."""
        manager = MagicMock()
        manager.config = MagicMock()
        return Builder(manager, logger=MagicMock())

    def test_get_summary(self, builder):
        """Verify target list truncation in log summary."""
        assert builder._get_summary(["a", "b"]) == "a, b"
        long_list = [str(i) for i in range(10)]
        summary = builder._get_summary(long_list)
        assert "..." in summary
        assert "(10 items)" in summary

    def test_resolve_subassemblies(self, builder):
        """Verify subassembly resolution logic."""
        # Case 1: base_subs is provided explicitly
        assert builder.resolve_subassemblies(MagicMock(spec=TargetList), ["left"]) == ["left"]

        # Case 2: base_subs is empty, resolve from manifest for multiple targets
        mock_targets = MagicMock(spec=TargetList)
        mock_targets.__iter__.return_value = iter(["t1", "t2"])
        builder.manager.router.manifest = {
            "t1": {Action.PART: {SUBASSEMBLIES: ["a", "b"]}},
            "t2": {Action.PART: {SUBASSEMBLIES: ["b", "c"]}},
        }
        res = builder.resolve_subassemblies(mock_targets, [])
        assert res == ["a", "b", "c"]

        # Case 3: No subassemblies found in manifest
        mock_targets_empty = MagicMock(spec=TargetList)
        mock_targets_empty.__iter__.return_value = iter(["t1"])
        builder.manager.router.manifest = {"t1": {Action.PART: {}}}
        assert builder.resolve_subassemblies(mock_targets_empty, []) == [None]
