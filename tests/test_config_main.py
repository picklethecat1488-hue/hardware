"""Contains Config main unit tests."""

import argparse
from config import Configurator, main, get_args
import pytest
from unittest.mock import MagicMock


class TestConfigMain:
    """Config main unit tests."""

    @pytest.fixture
    def mock_logger(self):
        """Return a mock Logger.

        :return _type_: A mock Logger.
        """
        return MagicMock()

    def test_get_args_parsing(self, mocker):
        """Test argument parsing."""
        mocker.patch("sys.argv", ["script.py", "-e", "foo.env", "-c", "-n", "driver"])
        args = get_args()

        assert args.env == "foo.env"
        assert args.clamps is True
        assert args.name == "driver"

    def test_configurator_configure_all_uses_config_names(self):
        """Test configure_clamps is called."""
        config_mock = MagicMock(names=["driver", "passenger"])
        configurator = Configurator(builder=MagicMock(), config=config_mock, logger=MagicMock())
        configurator.configure_clamps = MagicMock()
        configurator.configure_text_logos = MagicMock()

        configurator.configure_all()

        configurator.configure_clamps.assert_called_once_with(["driver", "passenger"])
        configurator.configure_text_logos.assert_called_once_with(["driver", "passenger"])

    def test_configurator_configure_all_accepts_explicit_names(self):
        """Test configure_clamps with explicit names passed in."""
        config_mock = MagicMock(names=["driver", "passenger"])
        configurator = Configurator(builder=MagicMock(), config=config_mock, logger=MagicMock())
        configurator.configure_clamps = MagicMock()
        configurator.configure_text_logos = MagicMock()

        configurator.configure_all(names=["part1"])

        configurator.configure_clamps.assert_called_once_with(["part1"])

    def test_main_calls_configure_clamps_when_clamps_flag(self, mocker, mock_logger):
        """Test configure_clamps with explicit names passed in."""
        args = argparse.Namespace(logo_text=False, clamps=True, name="driver", env=None)
        app_config = MagicMock(model_dump=MagicMock(return_value={}))
        builder = MagicMock()
        configurator_mock = MagicMock()
        mocker.patch("config.AppConfig", return_value=app_config)
        mocker.patch("config.Builder", return_value=builder)
        mocker.patch("config.Configurator", return_value=configurator_mock)

        main(mock_logger, args)

        configurator_mock.configure_clamps.assert_called_once_with(names=["driver"])
        configurator_mock.configure_all.assert_not_called()
        mock_logger.done.assert_called_once()

    def test_main_calls_configure_text_when_text_flag(self, mocker, mock_logger):
        """Test configure_text_logos with explicit names passed in."""
        args = argparse.Namespace(logo_text=True, clamps=False, name="driver", env=None)
        app_config = MagicMock(model_dump=MagicMock(return_value={}))
        builder = MagicMock()
        configurator_mock = MagicMock()
        mocker.patch("config.AppConfig", return_value=app_config)
        mocker.patch("config.Builder", return_value=builder)
        mocker.patch("config.Configurator", return_value=configurator_mock)

        main(mock_logger, args)

        configurator_mock.configure_clamps.configure_text_logos(names=["driver"])
        configurator_mock.configure_all.assert_not_called()
        mock_logger.done.assert_called_once()

    def test_main_writes_env_file_when_env_argument_is_set(self, mocker, tmp_path):
        """Test that main can write to the .env file."""
        env_path = tmp_path / "out.env"
        args = argparse.Namespace(logo_text=False, clamps=False, name=None, env=env_path)
        app_config = MagicMock(model_dump=MagicMock(return_value={"APP_FOO": "bar"}))
        configurator_mock = MagicMock()
        logger = MagicMock()
        mocker.patch("config.AppConfig", return_value=app_config)
        mocker.patch("config.Builder", return_value=MagicMock())
        mocker.patch("config.Configurator", return_value=configurator_mock)

        main(logger, args)

        assert env_path.read_text() == "APP_FOO=bar\n"
        logger.print.assert_called_once()
        logger.done.assert_called_once()
