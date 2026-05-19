"""Contains Build main unit tests."""

import argparse
from build import Builder, main, get_args
from pathlib import Path
import pytest
from unittest.mock import MagicMock


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
        mocker.patch("sys.argv", ["script.py", "-e", "foo.env", "-out", "tmp", "-d", "my_diag", "-l"])
        args = get_args()
        assert args.env == "foo.env"
        assert args.outdir == "tmp"
        assert args.diagram == "my_diag"
        assert args.output is None
        assert args.left is True

    def test_main_diagram_path(self, mock_logger, mock_builder, tmp_path):
        """Check if generate_diagram was called with correct unpacked gen_args."""
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram="schema", output=None, left=False, right=False)
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(out_dir=tmp_path, names=["schema"])

        assert Path(tmp_path).exists()
        mock_logger.done.assert_called_once()

        mock_builder.return_value.generate_diagram.reset_mock()
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram="schema", output=None, left=True, right=False)
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(
            out_dir=tmp_path, names=["schema"], right_vals=[False]
        )

        mock_builder.return_value.generate_diagram.reset_mock()
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram="schema", output=None, left=False, right=True)
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(
            out_dir=tmp_path, names=["schema"], right_vals=[True]
        )

    def test_main_output_path(self, mock_logger, mock_builder, tmp_path):
        """Test -o flag with name."""
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram=None, output="part1", left=True, right=False)
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(
            out_dir=tmp_path, names=["part1"], right_vals=[False]
        )

        mock_logger.done.assert_called_once()

        mock_builder.return_value.generate_parts.reset_mock()
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram=None, output="part1", left=False, right=True)
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(
            out_dir=tmp_path, names=["part1"], right_vals=[True]
        )

        mock_builder.return_value.generate_parts.reset_mock()
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram=None, output="part1", left=False, right=False)
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(out_dir=tmp_path, names=["part1"])

    def test_main_output_env_path(self, mock_logger, mock_builder, tmp_path):
        """Check if generate_diagram was called with correct unpacked gen_args."""
        args = argparse.Namespace(
            outdir=tmp_path, env=f"{tmp_path}.env", diagram=None, output=None, left=False, right=False
        )
        main(mock_logger, args)
        mock_builder.return_value.generate_all.assert_called_once_with(out_dir=tmp_path)

        assert Path(f"{tmp_path}.env").exists()
        mock_logger.done.assert_called_once()

    def test_main_generate_all_fallback(self, mock_logger, mock_builder, tmp_path):
        """Test the else block when no flags are provided."""
        args = argparse.Namespace(outdir=tmp_path, env=None, diagram=None, output=None, left=False, right=False)

        main(mock_logger, args)

        mock_builder.return_value.generate_all.assert_called_once_with(out_dir=tmp_path)

        mock_logger.done.assert_called_once()

    def test_mutually_exclusive_error(self, mocker):
        """Verify that providing both -d and -o raises a SystemExit (argparse behavior)."""
        mocker.patch("sys.argv", ["script.py", "-d", "-o", "name"])
        with pytest.raises(SystemExit):
            get_args()

        mocker.patch("sys.argv", ["script.py", "-l", "-r"])
        with pytest.raises(SystemExit):
            get_args()
