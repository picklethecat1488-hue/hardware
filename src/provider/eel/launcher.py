"""Eel standalone application launcher for Xerxes VCS Dashboard.

Provides browser discovery for Chromium/Chrome/Edge app-mode windows,
initializes the Eel bridge, and spawns the dashboard in a dedicated
desktop window frame without browser tabs or URL address bars.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional, Tuple
import urllib.parse

import eel
import eel.browsers as eel_browsers

_EEL_INITIALIZED = False


def find_eel_app_browser() -> Optional[str]:
    """Locate a browser binary capable of running in standalone desktop app mode.

    Scans system and user paths across macOS, Linux, and Windows for Chromium-based
    browsers (Google Chrome, Chromium, Microsoft Edge, Brave Browser, Arc).

    Returns:
        Absolute filesystem path to the browser binary, or None if not found.
    """
    # 1. Check if an app browser path is already registered with Eel
    registered_path = eel_browsers._browser_paths.get("chrome")
    if registered_path and Path(registered_path).is_file():
        return registered_path

    # 2. Check candidate locations by operating system directly
    candidates = []
    if sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            "/Applications/Arc.app/Contents/MacOS/Arc",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            os.path.expanduser("~/Applications/Chromium.app/Contents/MacOS/Chromium"),
            os.path.expanduser("~/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        ]
    elif sys.platform.startswith("linux"):
        for name in [
            "google-chrome",
            "google-chrome-stable",
            "chromium",
            "chromium-browser",
            "microsoft-edge",
            "microsoft-edge-stable",
            "brave-browser",
        ]:
            found = shutil.which(name)
            if found:
                return found
    elif sys.platform in ("win32", "win64"):
        edge_mod = eel_browsers._browser_modules.get("edge")
        if edge_mod is not None:
            try:
                edge_found = edge_mod.find_path()
                if edge_found and Path(edge_found).is_file():
                    return edge_found
            except (OSError, subprocess.SubprocessError):
                pass
        for name in ["chrome.exe", "msedge.exe", "brave.exe"]:
            found = shutil.which(name)
            if found:
                return found

    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate

    # 3. Fall back to Eel's built-in browser module discovery
    chrome_mod = eel_browsers._browser_modules.get("chrome")
    if chrome_mod is not None:
        try:
            detected = chrome_mod.find_path()
            if detected and Path(detected).is_file():
                return detected
        except (OSError, subprocess.SubprocessError):
            pass

    return None


def init_eel_bridge(static_dir: Optional[Path] = None) -> None:
    """Initialize the Eel static asset bridge and expose Python remote calls.

    Args:
        static_dir: Optional root directory containing static assets.
    """
    global _EEL_INITIALIZED
    if _EEL_INITIALIZED:
        return

    if static_dir is None:
        static_dir = Path(__file__).resolve().parent.parent / "code_review" / "static"

    if static_dir.exists():
        eel.init(str(static_dir))

    # Expose helper methods to frontend JavaScript
    @eel.expose
    def ping() -> str:
        """Health-check response for Eel bridge."""
        return "pong"

    @eel.expose
    def get_version() -> str:
        """Return application version string."""
        return "1.0.0"

    _EEL_INITIALIZED = True


def launch_eel(url: str, size: Tuple[int, int] = (1400, 900)) -> bool:
    """Launch the dashboard workstation in a standalone Eel application window.

    Locates an app-mode Chromium-based browser binary and launches in standalone window mode.

    Args:
        url: Full HTTP URL of the running dashboard server.
        size: Width and height of the standalone application window in pixels.

    Returns:
        True if successfully launched in standalone app mode, False otherwise.
    """
    init_eel_bridge()

    browser_path = find_eel_app_browser()
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    page = parsed.path.lstrip("/")
    if parsed.query:
        page = f"{page}?{parsed.query}"

    if browser_path:
        eel_browsers.set_path("chrome", browser_path)
        options = {
            "mode": "chrome",
            "host": host,
            "port": port,
            "app_mode": True,
            "cmdline_args": [
                f"--window-size={size[0]},{size[1]}",
                "--force-dark-mode",
                "--enable-features=OverlayScrollbar",
                "--disable-http-cache",
            ],
            "size": size,
            "block": False,
        }
        try:
            eel_browsers.open([page], options)
            return True
        except (OSError, subprocess.SubprocessError) as err:
            print(f"[EEL] Standalone window launch failed: {err}", file=sys.stderr)
            return False

    print("[EEL] No supported Chromium-based browser found for Eel standalone app mode.", file=sys.stderr)
    return False
