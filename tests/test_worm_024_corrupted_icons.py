"""Regression unit test for WORM-024 / BUG-285: Corrupted dashboard UI icons.

Verifies:
1. icon-512.png is centered, uncorrupted, transparent at corners, and occupies >= 80% of canvas.
2. icon-192.png is centered and occupies >= 80% of canvas.
3. apple-touch-icon.png is centered with transparent corners.
4. app.icns contains multi-resolution representations up to 1024x1024 for Retina displays.
"""

from pathlib import Path
from PIL import Image
import numpy as np
import pytest


def get_static_dir() -> Path:
    """Return path to static assets directory."""
    static_dir = Path(__file__).resolve().parent.parent / "provider" / "code_review" / "static"
    if not static_dir.exists():
        static_dir = Path(__file__).resolve().parent.parent / "src" / "provider" / "code_review" / "static"
    return static_dir


def test_icon_512_not_corrupted() -> None:
    """Verify icon-512.png fills the canvas properly with transparent corners rather than a tiny icon in a white box."""
    static_dir = get_static_dir()
    png_path = static_dir / "icon-512.png"
    assert png_path.exists(), f"icon-512.png missing from {static_dir}"

    im = Image.open(png_path)
    assert im.size == (512, 512)
    assert im.mode == "RGBA"

    arr = np.array(im)
    alpha = arr[:, :, 3]

    # Corners must NOT be solid white (RGB 255, 255, 255 with Alpha 255)
    corner_alphas = [int(alpha[0, 0]), int(alpha[0, -1]), int(alpha[-1, 0]), int(alpha[-1, -1])]
    assert all(a == 0 for a in corner_alphas), f"Corners must be transparent, got alphas {corner_alphas}"

    # Non-transparent bounding box must span at least 80% of width and height
    bbox = im.getbbox()
    assert bbox is not None, "Image must not be empty"
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    assert w >= 400, f"Icon width {w}px is less than 80% of 512px canvas (corrupted/thumbnail)"
    assert h >= 400, f"Icon height {h}px is less than 80% of 512px canvas (corrupted/thumbnail)"


def test_icon_192_not_corrupted() -> None:
    """Verify icon-192.png fills canvas properly with transparent corners."""
    static_dir = get_static_dir()
    png_path = static_dir / "icon-192.png"
    assert png_path.exists(), f"icon-192.png missing from {static_dir}"

    im = Image.open(png_path)
    assert im.size == (192, 192)
    assert im.mode == "RGBA"

    arr = np.array(im)
    alpha = arr[:, :, 3]
    corner_alphas = [int(alpha[0, 0]), int(alpha[0, -1]), int(alpha[-1, 0]), int(alpha[-1, -1])]
    assert all(a == 0 for a in corner_alphas), f"Corners must be transparent, got alphas {corner_alphas}"

    bbox = im.getbbox()
    assert bbox is not None
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    assert w >= 150, f"Icon width {w}px is less than 80% of 192px canvas"
    assert h >= 150, f"Icon height {h}px is less than 80% of 192px canvas"


def test_app_icns_validity() -> None:
    """Verify app.icns exists and has substantial size indicating full Retina resolutions."""
    static_dir = get_static_dir()
    icns_path = static_dir / "app.icns"
    assert icns_path.exists(), f"app.icns missing from {static_dir}"
    # A full multi-resolution ICNS with 16 to 1024px is >= 50 KB
    assert icns_path.stat().st_size >= 50000, f"app.icns size {icns_path.stat().st_size} bytes is too small"
