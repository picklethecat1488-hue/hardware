"""Contains Pathfinder unit tests."""

import argparse
import json
import subprocess
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathfinder import Pathfinder, get_args, main


class TestPathfinder:
    """Pathfinder unit tests."""

    @pytest.fixture(scope="class")
    def mock_logger(self):
        """Return a mock Logger."""
        return MagicMock()

    @pytest.fixture(scope="class")
    def mock_config(self):
        """Return a mock AppConfig."""
        config = MagicMock()
        config.names = ["driver", "passenger"]
        config.attractors = {}
        return config

    @pytest.fixture(scope="class")
    def mock_builder(self):
        """Return a mock Builder."""
        return MagicMock()

    @pytest.fixture(scope="class")
    def mock_configurator(self):
        """Return a mock Configurator."""
        return MagicMock()

    def test_pathfinder_init(self, mock_logger, mock_config, mock_builder, mock_configurator):
        """Test Pathfinder initialization."""
        with (
            patch("pathfinder.AppConfig", return_value=mock_config),
            patch("pathfinder.Builder", return_value=mock_builder),
            patch("pathfinder.Configurator", return_value=mock_configurator),
        ):
            pathfinder = Pathfinder(logger=mock_logger)

            assert pathfinder.logger == mock_logger
            assert pathfinder.config == mock_config
            assert pathfinder.builder == mock_builder
            assert pathfinder.configurator == mock_configurator

    def test_invoke_pytest_success(self, mock_logger):
        """Test invoke_pytest when pytest succeeds."""
        pathfinder = Pathfinder(logger=mock_logger)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            pathfinder.invoke_pytest()
            mock_run.assert_called_once_with(["pytest", "-qq", "-n", "auto", "-x", "--maxfail=1", "tests/"])
            mock_logger.print.assert_called_once()

    def test_invoke_pytest_failure(self, mock_logger):
        """Test invoke_pytest when pytest fails."""
        pathfinder = Pathfinder(logger=mock_logger)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            with pytest.raises(RuntimeError, match="Test suite failed with pytest exit code 1"):
                pathfinder.invoke_pytest()

    def test_get_point(self, mock_logger):
        """Test get_point returns a random point within bounds."""
        pathfinder = Pathfinder(logger=mock_logger)
        mock_bbox = MagicMock()
        mock_bbox.xmin = 0
        mock_bbox.xmax = 100
        mock_bbox.ymin = 0
        mock_bbox.ymax = 100
        mock_bbox.zmin = 0
        mock_bbox.zmax = 100

        with (
            patch.object(pathfinder.builder, "build_bound_box") as mock_build_box,
            patch("random.uniform") as mock_uniform,
        ):
            mock_build_box.return_value.val.return_value.BoundingBox.return_value = mock_bbox
            mock_uniform.side_effect = [10, 20, 30]  # x, y, z
            point = pathfinder.get_point()
            assert point == (10, 20, 30)
            assert mock_uniform.call_count == 3

    def test_try_point_success(self, mock_logger, mock_config, mock_builder, mock_configurator, tmp_path):
        """Test try_point when configuration and build succeed."""
        pathfinder = Pathfinder(logger=mock_logger)
        pathfinder.config = mock_config
        pathfinder.builder = mock_builder
        pathfinder.configurator = mock_configurator

        with patch.object(pathfinder, "invoke_pytest") as mock_pytest:
            path = Path(tmp_path)
            path_str = str(path)
            result = pathfinder.try_point("driver", (1, 2, 3), path)
            assert result is True
            assert mock_config.attractors["driver"] == (1, 2, 3)
            mock_configurator.configure_all.assert_called_once()
            mock_builder.generate_all.assert_called_once_with(out_dir=path_str)
            mock_pytest.assert_called_once()

    def test_try_point_failure(self, mock_logger, mock_config, mock_builder, mock_configurator, tmp_path):
        """Test try_point when configuration fails."""
        pathfinder = Pathfinder(logger=mock_logger)
        pathfinder.config = mock_config
        pathfinder.builder = mock_builder
        pathfinder.configurator = mock_configurator

        mock_configurator.configure_all.side_effect = Exception("Config error")
        result = pathfinder.try_point("driver", (1, 2, 3), Path(tmp_path))
        assert result is False
        mock_logger.print.assert_called_twice_with("Path failed: Config error", symbol="❌")

    def test_get_args_parsing(self, mocker):
        """Test argument parsing."""
        mocker.patch("sys.argv", ["script.py", "-out", "custom_out", "-n", "5", "-s", "passenger"])
        args = get_args()
        assert args.outdir == "custom_out"
        assert args.num_iterations == 5
        assert args.name == "passenger"
        assert args.num_points == 2

    def test_main_creates_output_directory_and_logs(self, mock_logger, tmp_path):
        """Test main creates output directory and logs successful paths."""
        args = argparse.Namespace(outdir=str(tmp_path), num_iterations=1, num_points=2, name="driver")
        log_file = tmp_path / "pathfinder_output.txt"

        with patch("pathfinder.Pathfinder") as mock_pathfinder_class:
            mock_pathfinder = MagicMock()
            mock_pathfinder.get_point.return_value = (10, 20, 30)
            mock_pathfinder.try_points.return_value = True
            mock_pathfinder.config = MagicMock(
                names=["driver", "passenger"],
                model_dump=MagicMock(
                    return_value={
                        "names": ["driver", "passenger"],
                        "attractors": {"driver": [[10, 20, 30], [10, 20, 30]]},
                    }
                ),
            )
            mock_pathfinder.builder.create_wire.return_value.val.return_value.Length.return_value = 100.0
            mock_pathfinder_class.return_value = mock_pathfinder

            main(mock_logger, args)

            mock_pathfinder_class.assert_called_once()
            mock_pathfinder.try_points.assert_called_once_with("driver", [(10, 20, 30), (10, 20, 30)], tmp_path)
            assert log_file.exists()
            content = log_file.read_text(encoding="utf-8").strip()
            assert content.startswith("{")
            data = json.loads(content)
            assert data["names"] == ["driver", "passenger"]
            assert data["attractors"]["driver"] == [[10, 20, 30], [10, 20, 30]]
            mock_logger.done.assert_called_once()
