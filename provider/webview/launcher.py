"""Cross-platform native OS webview launcher for Quake VCS Dashboard.

Provides native desktop application window integration using pywebview (Cocoa WKWebView
on macOS, WebKitGTK on Linux, and WebView2 on Windows), applying system theme colors,
custom application icons, and full standalone desktop window presentation without
browser URL address bars or tabs.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any, Callable, Optional, Tuple

APP_NAME: str = "Quake"
DEFAULT_WINDOW_TITLE: str = "Quake Workstation"
DEFAULT_WINDOW_SIZE: Tuple[int, int] = (1400, 900)
MIN_WINDOW_SIZE: Tuple[int, int] = (800, 600)
DEFAULT_BG_COLOR: str = "#291a10"


def apply_native_window_theme(window: Any, bg_color: str = DEFAULT_BG_COLOR) -> None:
    """Apply system theme, dark appearance, and titlebar styling to the native OS window.

    Args:
        window: The pywebview Window instance.
        bg_color: Hex color string for the theme background.
    """
    if sys.platform == "darwin":
        try:
            from PyObjCTools import AppHelper

            def _configure_cocoa() -> None:
                try:
                    import AppKit

                    native_window = getattr(window, "native", None)
                    if native_window is not None:
                        dark_app = AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameDarkAqua)
                        if dark_app and hasattr(native_window, "setAppearance_"):
                            native_window.setAppearance_(dark_app)
                        if (
                            bg_color
                            and bg_color.startswith("#")
                            and len(bg_color) == 7
                            and hasattr(native_window, "setBackgroundColor_")
                        ):
                            r = int(bg_color[1:3], 16) / 255.0
                            g = int(bg_color[3:5], 16) / 255.0
                            b = int(bg_color[5:7], 16) / 255.0
                            color = AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, 1.0)
                            native_window.setBackgroundColor_(color)
                        if hasattr(native_window, "setTitlebarAppearsTransparent_"):
                            native_window.setTitlebarAppearsTransparent_(True)
                except Exception:
                    pass

            AppHelper.callAfter(_configure_cocoa)
        except Exception:
            pass


def get_webview_storage_path(app_name: str = APP_NAME) -> Path:
    """Return the dedicated storage and cache directory for the native webview application.

    Args:
        app_name: Application name identifier for profile path construction.

    Returns:
        Path to the dedicated application storage directory.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / app_name
    elif sys.platform in ("win32", "win64"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / app_name if appdata else Path.home() / f".{app_name.lower()}"
    else:
        config_home = os.environ.get("XDG_CONFIG_HOME")
        base = Path(config_home) / app_name.lower() if config_home else Path.home() / ".config" / app_name.lower()

    storage_dir = base / "webview"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def get_app_icon_path(static_dir: Optional[Path] = None) -> Optional[Path]:
    """Return the platform-preferred application icon file path.

    Args:
        static_dir: Optional directory containing static assets.

    Returns:
        Path to the preferred icon file, or None if no icon is found.
    """
    if static_dir is None:
        static_dir = Path(__file__).resolve().parent.parent / "code_review" / "static"

    if not static_dir.exists():
        return None

    if sys.platform == "darwin":
        icns_path = static_dir / "app.icns"
        if icns_path.exists():
            return icns_path

    if sys.platform in ("win32", "win64"):
        ico_path = static_dir / "favicon.ico"
        if ico_path.exists():
            return ico_path

    png_path = static_dir / "icon-512.png"
    if png_path.exists():
        return png_path

    fallback_ico = static_dir / "favicon.ico"
    if fallback_ico.exists():
        return fallback_ico

    return None


def run_webview_window(
    url: str,
    title: str = DEFAULT_WINDOW_TITLE,
    width: int = DEFAULT_WINDOW_SIZE[0],
    height: int = DEFAULT_WINDOW_SIZE[1],
    bg_color: str = DEFAULT_BG_COLOR,
    icon_path: Optional[str] = None,
    storage_path: Optional[str] = None,
    exit_on_close: bool = False,
) -> None:
    """Run the native OS webview GUI event loop in the current process.

    Args:
        url: Web URL to display in the native webview.
        title: Window title text displayed in the system title bar.
        width: Initial window width in pixels.
        height: Initial window height in pixels.
        bg_color: Hex color string for native window background and title bar tint.
        icon_path: Optional filesystem path to application icon.
        storage_path: Optional filesystem path for webview data storage.
        exit_on_close: Whether to terminate the process immediately via os._exit on close.
    """
    import webview

    window = webview.create_window(
        title=title,
        url=url,
        width=width,
        height=height,
        min_size=MIN_WINDOW_SIZE,
        background_color=bg_color,
        text_select=True,
        zoomable=True,
    )

    if window is not None and hasattr(window, "events") and hasattr(window.events, "shown"):

        def _on_shown() -> None:
            apply_native_window_theme(window, bg_color)

        window.events.shown += _on_shown

    if exit_on_close and window is not None and hasattr(window, "events") and hasattr(window.events, "closed"):

        def _on_closed() -> None:
            os._exit(0)

        window.events.closed += _on_closed

    start_kwargs = {
        "private_mode": False,
    }
    if icon_path and Path(icon_path).exists():
        start_kwargs["icon"] = str(icon_path)
    if storage_path:
        start_kwargs["storage_path"] = str(storage_path)

    webview.start(**start_kwargs)
    if exit_on_close:
        os._exit(0)


def launch_webview(
    url: str,
    title: str = DEFAULT_WINDOW_TITLE,
    size: Tuple[int, int] = DEFAULT_WINDOW_SIZE,
    bg_color: str = DEFAULT_BG_COLOR,
    icon_path: Optional[Path] = None,
    storage_path: Optional[Path] = None,
    on_close: Optional[Callable[[], None]] = None,
) -> bool:
    """Spawn a detached native webview standalone window process.

    Spawns an independent process running the native webview GUI event loop,
    ensuring the caller process (e.g. background HTTP server) does not block.

    Args:
        url: Web URL to display in the standalone webview window.
        title: Window title bar text.
        size: Width and height of the window in pixels.
        bg_color: Hex color string for native window background tint.
        icon_path: Optional filesystem path to application icon.
        storage_path: Optional filesystem path for webview persistent cache.
        on_close: Optional callback invoked when the standalone webview process terminates.

    Returns:
        True if the webview process was spawned successfully, False otherwise.
    """
    if icon_path is None:
        icon_path = get_app_icon_path()

    if storage_path is None:
        storage_path = get_webview_storage_path()

    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--url",
        url,
        "--title",
        title,
        "--width",
        str(size[0]),
        "--height",
        str(size[1]),
        "--bg",
        bg_color,
    ]
    if icon_path and Path(icon_path).exists():
        cmd.extend(["--icon", str(icon_path)])
    if storage_path:
        cmd.extend(["--storage-path", str(storage_path)])

    popen_kwargs = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
    elif sys.platform in ("win32", "win64"):
        detached_flag = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        popen_kwargs["creationflags"] = detached_flag

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
        if on_close is not None:

            def _wait_and_close() -> None:
                proc.wait()
                try:
                    on_close()
                except Exception:
                    pass

            threading.Thread(target=_wait_and_close, daemon=True).start()
        return True
    except (OSError, subprocess.SubprocessError) as err:
        print(f"[WEBVIEW] Failed to launch native webview process: {err}", file=sys.stderr)
        return False


def _parse_cli_arguments() -> argparse.Namespace:
    """Parse command line arguments when invoked as a standalone script."""
    parser = argparse.ArgumentParser(description="Standalone native webview window process")
    parser.add_argument("--url", type=str, required=True, help="Target URL to load")
    parser.add_argument("--title", type=str, default=DEFAULT_WINDOW_TITLE, help="Window title text")
    parser.add_argument("--width", type=int, default=DEFAULT_WINDOW_SIZE[0], help="Window width in pixels")
    parser.add_argument("--height", type=int, default=DEFAULT_WINDOW_SIZE[1], help="Window height in pixels")
    parser.add_argument("--bg", type=str, default=DEFAULT_BG_COLOR, help="Hex window background color")
    parser.add_argument("--icon", type=str, default=None, help="Path to window icon")
    parser.add_argument("--storage-path", type=str, default=None, help="Path to storage cache directory")
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = _parse_cli_arguments()
    run_webview_window(
        url=cli_args.url,
        title=cli_args.title,
        width=cli_args.width,
        height=cli_args.height,
        bg_color=cli_args.bg,
        icon_path=cli_args.icon,
        storage_path=cli_args.storage_path,
        exit_on_close=True,
    )
