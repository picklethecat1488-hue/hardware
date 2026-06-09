"""Logger and shell utilities for console output."""

import threading
from typing import Any, cast
from halo import Halo


class Logger:
    """Logger wrapper for console output."""

    def __init__(self, text="Building...", enabled=True):
        """Create a logger instance."""
        self.text = text
        self.backend: Any = None
        self.enabled = enabled
        self.running = False
        self.lock = threading.Lock()

        if self.enabled:
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
        if not self.enabled:
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
                if restart:
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
