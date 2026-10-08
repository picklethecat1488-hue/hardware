"""Regression unit test for WORM-022: Themed PWA and Dock/Taskbar application icon.

Verifies:
1. PWA manifest.json exists with theme_color, background_color, and icons.
2. Themed app.icns exists in static asset directory for macOS Dock/taskbar.
3. ensure_macos_app_bundle generates a valid .app bundle with Info.plist, app.icns, and app_mode_loader.
4. Info.plist contains CFBundleIconFile ('app.icns') and NSRequiresAquaSystemAppearance (False) for themed title bar.
5. launch_eel utilizes the themed app bundle on macOS.
"""

import json
from pathlib import Path
import plistlib
import sys
from unittest.mock import patch

import pytest

from provider.eel.launcher import ensure_macos_app_bundle, launch_eel


def test_manifest_theme_and_icons() -> None:
    """Verify manifest.json defines theme_color, display standalone, and icons."""
    manifest_path = Path(__file__).resolve().parent.parent / "provider" / "code_review" / "static" / "manifest.json"
    assert manifest_path.exists(), f"manifest.json not found at {manifest_path}"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "theme_color" in data
    assert "background_color" in data
    assert data.get("display") == "standalone"
    assert "icons" in data and len(data["icons"]) > 0


def test_static_app_icns_exists() -> None:
    """Verify pregenerated app.icns exists in static directory."""
    icns_path = Path(__file__).resolve().parent.parent / "provider" / "code_review" / "static" / "app.icns"
    assert icns_path.exists(), f"app.icns not found at {icns_path}"
    assert icns_path.stat().st_size > 1000, "app.icns must not be empty"


def test_ensure_macos_app_bundle_structure(tmp_path: Path) -> None:
    """Verify ensure_macos_app_bundle generates valid bundle structure."""
    if sys.platform != "darwin":
        pytest.skip("macOS app bundle test only runs on darwin platform")

    chrome_app = Path("/Applications/Google Chrome.app")
    if not chrome_app.exists():
        pytest.skip("Google Chrome.app not installed on test host")

    chrome_bin = chrome_app / "Contents" / "MacOS" / "Google Chrome"
    bundle = ensure_macos_app_bundle(
        "http://127.0.0.1:8877/",
        browser_path=str(chrome_bin),
        app_name="Quake",
        target_dir=tmp_path,
    )
    assert bundle is not None
    assert bundle.exists()
    launcher_exe = bundle / "Contents" / "MacOS" / "Quake"
    assert launcher_exe.exists()
    assert "--app=" in launcher_exe.read_text()
    assert "--user-data-dir=" in launcher_exe.read_text()
    assert (bundle / "Contents" / "Resources" / "app.icns").exists()

    plist_path = bundle / "Contents" / "Info.plist"
    assert plist_path.exists()
    plist = plistlib.loads(plist_path.read_bytes())
    assert plist.get("CFBundleIconFile") == "app.icns"
    assert plist.get("CFBundleName") == "Quake"
    assert plist.get("CFBundleExecutable") == "Quake"
    assert plist.get("NSRequiresAquaSystemAppearance") is False


def test_launch_eel_uses_app_bundle() -> None:
    """Verify launch_eel attempts to launch via macOS app bundle when on darwin."""
    with (
        patch("sys.platform", "darwin"),
        patch(
            "provider.eel.launcher.find_eel_app_browser",
            return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
        patch("provider.eel.launcher.ensure_macos_app_bundle") as mock_ensure,
        patch("subprocess.Popen") as mock_popen,
    ):
        mock_ensure.return_value = Path("/tmp/Quake.app")
        with patch.object(Path, "exists", return_value=True):
            res = launch_eel("http://127.0.0.1:8877/")
            assert res is True
            assert mock_popen.called
            args, _ = mock_popen.call_args
            assert args[0] == ["open", "-n", "/tmp/Quake.app"]
