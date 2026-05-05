"""Contains Main unit tests."""

import argparse
from build import main, get_args
from pathlib import Path
import pytest
from unittest.mock import MagicMock


class TestMain:
    """Main unit tests.

    :return _type_: A Main test harness.
    """

    @pytest.fixture
    def mock_logger(self):
        """Return a mock Logger.

        :return _type_: A mock Logger.
        """
        return MagicMock()

    @pytest.fixture
    def mock_builder(self, mocker):
        """Return a mock Builder.

        :param _type_ mocker: The Mocker.
        :return _type_: A Builder class patched into the build module.
        """
        return mocker.patch("build.Builder")

    def test_get_args_parsing(self, mocker):
        """Test the argparse configuration directly.

        :param _type_ mocker: The Mocker.
        """
        mocker.patch("sys.argv", ["script.py", "-out", "tmp", "-d", "my_diag", "-l"])
        args = get_args()
        assert args.outdir == "tmp"
        assert args.diagram == "my_diag"
        assert args.output is None
        assert args.left is True

    def test_main_diagram_path(self, mock_logger, mock_builder, tmp_path):
        """Check if generate_diagram was called with correct unpacked gen_args.

        :param _type_ mock_logger: The Logger.
        :param _type_ mock_builder: The Builder.
        :param _type_ tmp_path: The temporary path.
        """
        args = argparse.Namespace(outdir=tmp_path, diagram="schema", output=None, left=False, right=False)
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(out_dir=tmp_path, names=["schema"])

        assert Path(tmp_path).exists()
        mock_logger.done.assert_called_once()

        mock_builder.return_value.generate_diagram.reset_mock()
        args = argparse.Namespace(outdir=tmp_path, diagram="schema", output=None, left=True, right=False)
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(
            out_dir=tmp_path, names=["schema"], right_vals=[False]
        )

        mock_builder.return_value.generate_diagram.reset_mock()
        args = argparse.Namespace(outdir=tmp_path, diagram="schema", output=None, left=False, right=True)
        main(mock_logger, args)
        mock_builder.return_value.generate_diagram.assert_called_once_with(
            out_dir=tmp_path, names=["schema"], right_vals=[True]
        )

    def test_main_output_path(self, mock_logger, mock_builder, tmp_path):
        """Test -o flag with name.

        :param _type_ mock_logger: The Logger.
        :param _type_ mock_builder: The Builder.
        :param _type_ tmp_path: The temporary path.
        """
        args = argparse.Namespace(outdir=tmp_path, diagram=None, output=["part1"], left=True, right=False)
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(
            out_dir=tmp_path, names=["part1"], right_vals=[False]
        )

        mock_logger.done.assert_called_once()

        mock_builder.return_value.generate_parts.reset_mock()
        args = argparse.Namespace(outdir=tmp_path, diagram=None, output=["part1"], left=False, right=True)
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(
            out_dir=tmp_path, names=["part1"], right_vals=[True]
        )

        mock_builder.return_value.generate_parts.reset_mock()
        args = argparse.Namespace(outdir=tmp_path, diagram=None, output=["part1"], left=False, right=False)
        main(mock_logger, args)
        mock_builder.return_value.generate_parts.assert_called_once_with(out_dir=tmp_path, names=["part1"])

    def test_main_generate_all_fallback(self, mock_logger, mock_builder, tmp_path):
        """Test the else block when no flags are provided.

        :param _type_ mock_logger: The Logger.
        :param _type_ mock_builder: The Builder.
        :param _type_ tmp_path: The temporary path to use.
        """
        args = argparse.Namespace(outdir=tmp_path, diagram=None, output=None, left=False, right=False)

        main(mock_logger, args)

        mock_builder.return_value.generate_all.assert_called_once_with(out_dir=tmp_path)

        mock_logger.done.assert_called_once()

    def test_mutually_exclusive_error(self, mocker):
        """Verify that providing both -d and -o raises a SystemExit (argparse behavior).

        :param _type_ mock_logger: The Logger.
        :param _type_ mock_builder: The Builder.
        """
        mocker.patch("sys.argv", ["script.py", "-d", "-o", "name"])
        with pytest.raises(SystemExit):
            get_args()

        mocker.patch("sys.argv", ["script.py", "-l", "-r"])
        with pytest.raises(SystemExit):
            get_args()
