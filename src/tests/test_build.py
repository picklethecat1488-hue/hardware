"""Contains Build main unit tests."""

import argparse
from build import Builder, main, get_args, str2bool
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from provider import Action, Mode, TargetList


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
        mocker.patch("sys.argv", ["script.py", "-e", "foo.env", "-out", "tmp", "-d", "-s", "left", "part1"])
        args = get_args()
        assert args.env == "foo.env"
        assert args.outdir == "tmp"
        assert args.diagram is True
        assert args.targets == ["part1"]
        assert args.subassembly == "left"

    def test_main_diagram_path(self, mock_logger, mock_builder, tmp_path):
        """Check if generate_diagram was called with correct unpacked gen_args."""
        args = argparse.Namespace(
            outdir=tmp_path, env=None, diagram=True, parts=False, targets=["schema"], subassembly=None
        )
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(out_dir=tmp_path, names=["schema"])

        assert Path(tmp_path).exists()
        mock_logger.done.assert_called_once()

        mock_builder.return_value.generate_diagram.reset_mock()
        args = argparse.Namespace(
            outdir=tmp_path, env=None, diagram=True, parts=False, targets=["schema"], subassembly="left"
        )
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(out_dir=tmp_path, names=["schema"])

        mock_builder.return_value.generate_diagram.reset_mock()
        args = argparse.Namespace(
            outdir=tmp_path, env=None, diagram=True, parts=False, targets=["schema"], subassembly="right"
        )
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(out_dir=tmp_path, names=["schema"])

    def test_main_output_path(self, mock_logger, mock_builder, tmp_path):
        """Test positional targets."""
        args = argparse.Namespace(
            outdir=tmp_path, env=None, diagram=False, parts=True, targets=["part1"], subassembly="left", mode=None
        )
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(
            out_dir=tmp_path, names=["part1"], subassembly="left", mode=None
        )

        mock_logger.done.assert_called_once()

        mock_builder.return_value.generate_parts.reset_mock()
        args = argparse.Namespace(
            outdir=tmp_path, env=None, diagram=False, parts=True, targets=["part1"], subassembly="right", mode=None
        )
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(
            out_dir=tmp_path, names=["part1"], subassembly="right", mode=None
        )

        mock_builder.return_value.generate_parts.reset_mock()
        args = argparse.Namespace(
            outdir=tmp_path, env=None, diagram=False, parts=True, targets=["part1"], subassembly=None, mode=None
        )
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(
            out_dir=tmp_path, names=["part1"], subassembly=None, mode=None
        )

    def test_main_output_env_path(self, mock_logger, mock_builder, tmp_path):
        """Check if generate_diagram was called with correct unpacked gen_args."""
        args = argparse.Namespace(
            outdir=tmp_path, env=f"{tmp_path}.env", diagram=True, parts=True, targets=[], subassembly=None
        )
        main(mock_logger, args)
        mock_builder.return_value.config.dump_env.assert_called_once_with(f"{tmp_path}.env")
        mock_logger.done.assert_called_once()

    def test_main_generate_all_fallback(self, mock_logger, mock_builder, tmp_path):
        """Test the else block when no flags are provided."""
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram=True, parts=True, targets=[], subassembly=None)

        main(mock_logger, args)

        mock_builder.return_value.generate_all.assert_called_once_with(out_dir=tmp_path, subassembly=None)

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

    def test_resolve_mode_fallback(self, builder):
        """Verify mode fallback logic when PRINT is unsupported."""
        # Setup manifest once for all cases to prevent subsequent overwrites
        builder.manager.router.manifest = {
            "t1": {Action.PART: {"modes": [Mode.PRINT, Mode.DEFAULT]}},
            "t2": {Action.PART: {"modes": [Mode.DEFAULT]}},
        }

        # Case 1: Target supports PRINT
        assert builder._resolve_modes("t1") == ["print"]

        # Case 2: Target does NOT support PRINT, fallback to DEFAULT
        assert builder._resolve_modes("t2") == ["default"]

        # Case 3: Specific override provided
        assert builder._resolve_modes("t1", mode_override="custom") == ["custom"]

        # Case 4: Wildcard mode override
        assert builder._resolve_modes("t1", mode_override="p*") == ["print"]

    def test_resolve_subassemblies(self, builder):
        """Verify subassembly resolution from manifest or override."""
        builder.manager.router.manifest = {
            "t1": {Action.PART: {"subassemblies": ["left", "right"]}},
            "t2": {Action.PART: {}},
        }
        # Case 1: Manifest defines subassemblies
        assert list(builder._resolve_subassemblies("t1")) == ["left", "right"]

        # Case 2: Manifest has no subassemblies, defaults to [None] (whole part)
        assert builder._resolve_subassemblies("t2") == [None]

        # Case 3: Override provided
        assert builder._resolve_subassemblies("t1", subassembly_override="left") == ["left"]

        # Case 4: Wildcard subassembly override
        assert builder._resolve_subassemblies("t1", subassembly_override="r*") == ["right"]

    def test_generate_parts_wildcard_error(self, builder):
        """Verify that an empty wildcard match for parts results in an error."""
        # Mock supporting to return a TargetList-like object (mock) that is empty
        mock_targets = MagicMock(spec=TargetList)
        mock_targets.__len__.return_value = 0
        mock_targets.for_targets.return_value = mock_targets
        builder.manager.router.targets.supporting.return_value = mock_targets

        # This should raise a ValueError because names contains a wildcard
        with pytest.raises(ValueError, match="No part targets matched wildcard pattern"):
            builder.generate_parts("out", names=["tube/*"])
