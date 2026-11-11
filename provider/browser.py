"""Shared workstation browser launcher for standalone webview, eel, app mode, and browser fallback."""

from pathlib import Path
from typing import Callable, Optional
import webbrowser


def get_default_icon_path(repo_root: Optional[Path] = None) -> Optional[Path]:
    """Find default application icon for standalone window frames."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent
    for candidate in [
        repo_root / "provider" / "code_review" / "static" / "scope-favicon.ico",
        repo_root / "provider" / "code_review" / "static" / "scope-icon.png",
    ]:
        if candidate.is_file():
            return candidate
    return None


def launch_browser(
    url: str,
    browser: str = "webview",
    on_close: Optional[Callable[[], None]] = None,
    title: Optional[str] = None,
    bg_color: Optional[str] = None,
    icon_path: Optional[Path] = None,
) -> bool:
    """Open workstation dashboard in a standalone desktop window or default browser.

    Args:
        url: Web URL to open.
        browser: Target display environment ('webview', 'eel', or browser fallback).
        on_close: Callback invoked when standalone window is closed.
        title: Window title for standalone frames.
        bg_color: Background color for initial window creation.
        icon_path: Window icon path.

    Returns:
        True if successfully launched, False otherwise.
    """
    if browser == "eel":
        try:
            from provider.eel.launcher import launch_eel

            if on_close is not None:
                return launch_eel(url, on_close=on_close)
            return launch_eel(url)
        except Exception:
            pass

    if browser == "webview":
        try:
            from provider.webview.launcher import launch_webview

            kwargs = {}
            if title is not None:
                kwargs["title"] = title
            if bg_color is not None:
                kwargs["bg_color"] = bg_color
            if icon_path is not None:
                kwargs["icon_path"] = icon_path
            if on_close is not None:
                kwargs["on_close"] = on_close

            if kwargs:
                return launch_webview(url, **kwargs)
            return launch_webview(url)
        except Exception:
            pass

    return webbrowser.open(url)
