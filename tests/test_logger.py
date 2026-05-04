"""Contains Logger system unit tests."""

from build import Logger
import pytest


class TestLogger:
    """Logger tests.

    :return _type_: A TestLogger object.
    """

    @pytest.fixture
    def mock_dependencies(self, mocker):
        """Mock all external UI/Notebook dependencies.

        :param _type_ mocker: The Mocker object.
        """
        return {
            "widgets": mocker.patch("ipywidgets.HTML", autospec=True),
            "display": mocker.patch("IPython.display.display"),
            "sanitizer": mocker.patch("html_sanitizer.Sanitizer"),
            "halo": mocker.patch("halo.Halo"),
        }

    def test_init_terminal_mode(self, mocker, mock_dependencies):
        """Verify Halo spinner starts when in a terminal.

        :param _type_ mocker: The Mocker object.
        :param _type_ mock_dependencies: The mock dependencies.
        """
        mocker.patch("build.Logger.in_notebook", return_value=False)
        logger = Logger(text="Testing Terminal", enabled=True)

        mock_dependencies["halo"].assert_called_once_with(text="Testing Terminal", spinner="dots", interval=33)
        assert logger.backend.start.called
        assert logger.running is True

    def test_init_notebook_mode(self, mocker, mock_dependencies):
        """Verify HTML widgets are used when in a notebook.

        :param _type_ mocker: The Mocker object.
        :param _type_ mock_dependencies: The mock dependencies.
        """
        # Setup sanitizer mock to return a string
        mocker.patch("build.Logger.in_notebook", return_value=True)
        mock_dependencies["sanitizer"].return_value.sanitize.return_value = "Sanitized"

        logger = Logger(text="Testing Notebook", enabled=True)
        assert not logger.backend is None
        assert logger.enabled is True

        mock_dependencies["widgets"].assert_called_once()
        mock_dependencies["display"].assert_called_once()
        assert "Sanitized" in mock_dependencies["widgets"].call_args[1]["value"]

    def test_disabled_logger_prints_directly(self, mocker, capsys):
        """Verify that when disabled, it uses standard print.

        :param _type_ mocker: The Mocker object.
        :param _type_ mock_dependencies: The mock dependencies.
        """
        with mocker.patch("build.Logger.in_notebook", return_value=False):
            logger = Logger(enabled=False)
            logger.print("Direct message")

            captured = capsys.readouterr()
            assert "Direct message" in captured.out

    def test_terminal_print_persists_message(self, mocker):
        """Verify print stops the spinner to persist text, then restarts.

        :param _type_ mocker: The Mocker object.
        :param _type_ mock_dependencies: The mock dependencies.
        """
        mocker.patch("build.Logger.in_notebook", return_value=False)
        mock_halo_class = mocker.patch("halo.Halo")
        logger = Logger(enabled=True)
        mock_halo = mock_halo_class.return_value

        logger.print("Step 1", symbol="✔")

        # Halo should stop/persist the message and restart
        mock_halo.stop_and_persist.assert_called_with("✔ Step 1")
        assert mock_halo.start.call_count == 2  # Once in init, once in print

    def test_done_terminal(self, mocker):
        """Verify done() calls succeed and stops the runner.

        :param _type_ mocker: The Mocker object.
        :param _type_ mock_dependencies: The mock dependencies.
        """
        mocker.patch("build.Logger.in_notebook", return_value=False)
        logger = Logger(text="Build", enabled=True)
        logger.done()

        assert logger.running is False
