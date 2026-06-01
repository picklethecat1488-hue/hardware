"""Contains Logger system unit tests."""

from shell import Logger
import pytest


class TestLogger:
    """Logger tests."""

    @pytest.fixture
    def mock_dependencies(self, mocker):
        """Mock external UI dependencies."""
        return {
            "halo": mocker.patch("shell.Halo"),
        }

    def test_init_terminal_mode(self, mocker, mock_dependencies):
        """Verify terminal logger initializes Halo spinner."""
        logger = Logger(text="Testing Terminal", enabled=True)

        mock_dependencies["halo"].assert_called_once_with(text="Testing Terminal", spinner="dots", interval=33)
        assert logger.backend.start.called
        assert logger.running is True

    def test_disabled_logger_prints_directly(self, mocker, capsys):
        """Verify disabled logger prints directly."""
        logger = Logger(enabled=False)
        logger.print("Direct message")

        captured = capsys.readouterr()
        assert "Direct message" in captured.out

    def test_terminal_print_persists_message(self, mocker):
        """Verify print persists messages and restarts the spinner."""
        mock_halo_class = mocker.patch("shell.Halo")
        logger = Logger(enabled=True)
        mock_halo = mock_halo_class.return_value

        logger.print("Step 1", symbol="✔")

        # Halo should stop/persist the message and restart
        mock_halo.stop_and_persist.assert_called_with("✔ Step 1")
        assert mock_halo.start.call_count == 2  # Once in init, once in print

    def test_done_terminal(self, mocker, mock_dependencies):
        """Verify done() stops the logger."""
        logger = Logger(text="Build", enabled=True)
        logger.done()

        assert logger.running is False
