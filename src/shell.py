"""Logger and shell utilities for console output and daemon logging."""

import logging
from pathlib import Path
import sys
import threading
from typing import Any, Optional, cast
from halo import Halo


class StreamToLogger:
    """Redirects stream writes to a Python Logger as structured JSON entries."""

    def __init__(self, logger: logging.Logger, log_level: int = logging.INFO):
        """Initialize the logger."""
        self.logger = logger
        self.log_level = log_level

    def write(self, buf: str) -> int:
        """Write to the logger."""
        if buf and buf.strip():
            for line in buf.splitlines():
                if line.strip():
                    self.logger.log(self.log_level, line.strip())
        return len(buf)

    def flush(self):
        """Flush the logger."""
        pass

    def isatty(self) -> bool:
        """Return False as logger is not a TTY."""
        return False

    def close(self):
        """Close the stream."""
        pass


class Logger:
    """Logger wrapper for console output."""

    def __init__(self, text="Building...", enabled=True):
        """Create a logger instance."""
        self.text = text
        self.backend: Any = None
        self.enabled = enabled
        self.running = False
        self.lock = threading.Lock()
        self._daemon_logger: Optional[logging.Logger] = None

        # Only run Halo spinner if stdout is a TTY (terminal)
        isatty_func = getattr(sys.stdout, "isatty", None)
        self.has_tty = isatty_func() if isatty_func is not None else False
        if self.enabled and self.has_tty:
            self.backend = Halo(text=self.text, spinner="dots", interval=33)
            self.backend.start()
            self.running = True

    @property
    def started(self) -> bool:
        """Return True if the logger spinner is running."""
        return self.running

    @started.setter
    def started(self, value: bool):
        """Start or stop the logger spinner."""
        if not self.enabled or not self.backend:
            return

        with self.lock:
            if value and not self.running:
                cast(Any, self.backend).start()
                self.running = True
            elif not value and self.running:
                cast(Any, self.backend).stop()
                self.running = False

    def print(self, msg, symbol="▶", restart=True):
        """Print a formatted log message."""
        if not self.enabled:
            return

        with self.lock:
            formatted = f"{symbol} {msg}"
            if not self.running:
                # If the spinner isn't running, just do a normal print to avoid overhead
                print(formatted)
                if restart and self.backend:
                    cast(Any, self.backend).start()
                    self.running = True
                return

            # Display the message, along with a custom symbol, while keeping the spinner going.
            backend = cast(Any, self.backend)
            backend.text = ""
            backend.stop_and_persist(formatted)
            if restart:
                backend.start()
            else:
                self.running = False

    @property
    def daemon_logger(self) -> logging.Logger:
        """Get or initialize the daemon logger for structured logging."""
        if self._daemon_logger is None:
            self._daemon_logger = logging.getLogger("daemon")
            self._daemon_logger.setLevel(logging.INFO)
            if not self._daemon_logger.handlers:
                log_path = Path(__file__).parent.parent / "build" / "daemon.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(str(log_path), encoding="utf-8")
                from daemon import JSONFormatter

                formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
                handler.setFormatter(formatter)
                self._daemon_logger.addHandler(handler)
        return self._daemon_logger

    def log(self, msg: str, symbol: Optional[str] = "📄"):
        """Log a structured entry to build/daemon.log without printing to console."""
        formatted = f"{symbol} {msg}" if symbol else msg
        self.daemon_logger.info(formatted)

    def done(self):
        """Mark the operation as complete."""
        with self.lock:
            if self.backend:
                backend = cast(Any, self.backend)
                backend.text = f"Done {self.text}"
                backend.succeed()
                if self.running:
                    # Stop the spinner after the operation has completed.
                    backend.stop()
                    self.running = False
            else:
                if self.enabled:
                    print(f"Done {self.text}")
