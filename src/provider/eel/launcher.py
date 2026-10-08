"""Eel standalone application launcher for Xerxes VCS Dashboard.

Provides browser discovery for Chromium/Chrome/Edge app-mode windows,
initializes the Eel bridge, and spawns the dashboard in a dedicated
desktop window frame without browser tabs or URL address bars.
"""

import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
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


def get_eel_profile_dir(app_name: str = "Quake") -> Path:
    """Return the dedicated application profile directory for standalone app mode."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / app_name
    elif sys.platform in ("win32", "win64"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / app_name if appdata else Path.home() / f".{app_name.lower()}"
    else:
        config_home = os.environ.get("XDG_CONFIG_HOME")
        base = Path(config_home) / app_name.lower() if config_home else Path.home() / ".config" / app_name.lower()
    profile = base / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    return profile


def ensure_macos_app_bundle(
    url: str,
    browser_path: Optional[str] = None,
    app_name: str = "Quake",
    size: Tuple[int, int] = (1400, 900),
    target_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Ensure a native macOS .app shim exists for launching with custom dock icon."""
    if sys.platform != "darwin":
        return None

    if not browser_path or not Path(browser_path).exists():
        return None

    # Determine bundle location
    if target_dir is not None:
        apps_dir = target_dir
    else:
        apps_dir = Path.home() / "Applications" / "Chrome Apps.localized"
        if not apps_dir.exists():
            try:
                apps_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                apps_dir = Path(tempfile.gettempdir())

    app_bundle = apps_dir / f"{app_name}.app"
    contents = app_bundle / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)

    # 1. Write executable launcher script
    profile_dir = get_eel_profile_dir(app_name)
    launcher_script = macos / app_name
    script_content = f"""#!/bin/bash
exec "{browser_path}" \\
  --app="{url}" \\
  --user-data-dir="{profile_dir}" \\
  --window-size={size[0]},{size[1]} \\
  --force-dark-mode \\
  --enable-features=OverlayScrollbar \\
  --disable-http-cache \\
  --no-first-run \\
  --no-default-browser-check \\
  "$@"
"""
    launcher_script.write_text(script_content)
    launcher_script.chmod(0o755)

    # 2. Icon: copy app.icns from static directory
    static_dir = Path(__file__).resolve().parent.parent / "code_review" / "static"
    icns_src = static_dir / "app.icns"
    if icns_src.exists():
        shutil.copy2(icns_src, resources / "app.icns")

    # 3. Write Info.plist
    plist_data = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleExecutable": app_name,
        "CFBundleIconFile": "app.icns",
        "CFBundleIdentifier": f"com.google.Chrome.app.{app_name.lower()}-workstation",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": app_name,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleSignature": "????",
        "CFBundleVersion": "1.0",
        "LSEnvironment": {"MallocNanoZone": "0"},
        "LSHasLocalizedDisplayName": True,
        "LSMinimumSystemVersion": "12.0",
        "NSAppleScriptEnabled": True,
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(plist_data))

    # 4. Ad-hoc codesign
    try:
        subprocess.run(["codesign", "--force", "--sign", "-", str(app_bundle)], check=True, capture_output=True)
    except (subprocess.SubprocessError, OSError):
        pass

    return app_bundle


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
    if not browser_path:
        print("[EEL] No supported Chromium-based browser found for Eel standalone app mode.", file=sys.stderr)
        return False

    # 1. On macOS, launch via dedicated .app bundle to display the themed Dock icon
    if sys.platform == "darwin":
        app_bundle = ensure_macos_app_bundle(
            url,
            browser_path=browser_path,
            app_name="Quake",
            size=size,
        )
        if app_bundle and app_bundle.exists():
            try:
                cmd = ["open", "-n", str(app_bundle)]
                subprocess.Popen(cmd)
                return True
            except (subprocess.SubprocessError, OSError):
                pass

    # 2. Standard Chromium browser launch fallback
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    page = parsed.path.lstrip("/")
    if parsed.query:
        page = f"{page}?{parsed.query}"

    profile_dir = get_eel_profile_dir("Quake")
    eel_browsers.set_path("chrome", browser_path)
    options = {
        "mode": "chrome",
        "host": host,
        "port": port,
        "app_mode": True,
        "cmdline_args": [
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={size[0]},{size[1]}",
            "--force-dark-mode",
            "--enable-features=OverlayScrollbar",
            "--disable-http-cache",
            "--class=Quake",
            "--app-id=Quake",
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
