"""Native webview desktop application launcher package.

Provides cross-platform native OS webview window integration (Cocoa WKWebView
on macOS, WebKitGTK on Linux, WebView2 on Windows) for the Quake workstation.
"""

from .launcher import (
    DEFAULT_BG_COLOR,
    DEFAULT_WINDOW_SIZE,
    get_app_icon_path,
    get_webview_storage_path,
    launch_webview,
    run_webview_window,
)

__all__ = [
    "DEFAULT_BG_COLOR",
    "DEFAULT_WINDOW_SIZE",
    "get_app_icon_path",
    "get_webview_storage_path",
    "launch_webview",
    "run_webview_window",
]
