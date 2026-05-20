"""Logger and shell utilities for console and notebook output."""

import threading
from typing import Any, cast
from IPython.core.getipython import get_ipython  # type: ignore


class Logger:
    """Logger wrapper for console and notebook output."""

    def __init__(self, text="Building...", enabled=True):
        """Create a logger instance."""
        self.text = text
        self.backend: Any = None
        self.in_notebook = self.get_in_notebook()
        self.enabled = enabled
        self.lock = threading.Lock()

        if self.enabled:
            if self.in_notebook:
                from html_sanitizer import Sanitizer
                import ipywidgets as widgets
                from IPython.display import display

                self.sanitizer = Sanitizer()
                sanitized_text = self.sanitizer.sanitize(self.text)
                self.backend = widgets.HTML(value=f"⏳ <b>{sanitized_text}</b>")
                display(self.backend)
            else:
                from halo import Halo

                self.backend = Halo(text=self.text, spinner="dots", interval=33)
                self.backend.start()
                self.running = True

    def get_in_notebook(self):
        """Return whether the code is running in a notebook."""
        try:
            shell = get_ipython().__class__.__name__
            return shell == "ZMQInteractiveShell"
        except NameError:
            return False

    def print(self, msg, symbol="▶"):
        """Print a formatted log message."""
        if not self.enabled:
            print(msg)
        else:
            with self.lock:
                if self.in_notebook:
                    import ipywidgets as widgets
                    from IPython.display import display

                    sanitized_symbol = self.sanitizer.sanitize(symbol)
                    sanitized_text = self.sanitizer.sanitize(msg)
                    self.backend = widgets.HTML(value=f"{sanitized_symbol} <pre>{sanitized_text}</pre>")
                    display(self.backend)
                else:
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
            if not self.in_notebook and self.backend:
                backend = cast(Any, self.backend)
                backend.text = f"Done {self.text}"
                backend.succeed()
                if self.running:
                    # Stop the spinner after the operation has completed.
                    backend.stop()
                    self.running = False
