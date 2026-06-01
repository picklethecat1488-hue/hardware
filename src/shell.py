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

    def print(self, msg, symbol="▶"):
        """Print a formatted log message."""
        if not self.enabled:
            print(msg)
        else:
            with self.lock:
                if not self.running:
                    # Start the spinner, if not already running.
                    cast(Any, self.backend).start()
                    self.running = True
                # Display the message, along with a custom symbol, while keeping the spinner going.
                backend = cast(Any, self.backend)
                backend.text = ""
                backend.stop_and_persist(f"{symbol} {msg}")
                backend.start()

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
