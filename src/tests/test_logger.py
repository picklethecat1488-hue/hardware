"""Contains Logger system unit tests."""

from shell import Logger
from unittest.mock import MagicMock
import pytest


class TestLogger:
    """Logger tests."""

    @pytest.fixture(autouse=True)
    def mock_isatty(self, mocker):
        """Force stdout to behave as a TTY for logger tests."""
        mocker.patch("sys.stdout.isatty", return_value=True)

    @pytest.fixture
    def mock_dependencies(self, mocker):
        """Mock external UI dependencies."""
        mock_halo = MagicMock()
        mocker.patch.dict(Logger.__init__.__globals__, {"Halo": mock_halo})
        return {
            "halo": mock_halo,
        }

    def test_init_terminal_mode(self, mocker, mock_dependencies):
        """Verify terminal logger initializes Halo spinner."""
        logger = Logger(text="Testing Terminal", enabled=True)

        mock_dependencies["halo"].assert_called_once_with(text="Testing Terminal", spinner="dots", interval=33)
        assert logger.backend.start.called
        assert logger.running is True

    def test_disabled_logger_is_silent(self, mocker, capsys):
        """Verify disabled logger does not print."""
        logger = Logger(enabled=False)
        logger.print("Direct message")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_terminal_print_persists_message(self, mock_dependencies):
        """Verify print persists messages and restarts the spinner."""
        mock_halo = mock_dependencies["halo"].return_value
        logger = Logger(enabled=True)

        logger.print("Step 1", symbol="✔")

        # Halo should stop/persist the message and restart
        mock_halo.stop_and_persist.assert_called_with("✔ Step 1")
        assert mock_halo.start.call_count == 2  # Once in init, once in print

    def test_print_without_restart(self, mock_dependencies):
        """Verify print with restart=False stops the spinner."""
        mock_halo = mock_dependencies["halo"].return_value
        logger = Logger(enabled=True)

        logger.print("No restart", restart=False)
        assert logger.running is False
        assert mock_halo.stop_and_persist.called
        assert mock_halo.start.call_count == 1  # Only from init

    def test_manual_start_stop(self, mock_dependencies):
        """Verify manual start and stop control."""
        mock_halo = mock_dependencies["halo"].return_value
        logger = Logger(enabled=True)

        logger.started = False
        assert logger.running is False
        logger.started = True
        assert logger.running is True
        assert mock_halo.start.call_count == 2

    def test_done_terminal(self, mocker, mock_dependencies):
        """Verify done() stops the logger."""
        logger = Logger(text="Build", enabled=True)
        logger.done()

        assert logger.running is False
