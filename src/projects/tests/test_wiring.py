"""Unit tests for the Wiring model, layouts registration, and namespaces."""

import pytest
import math
from pathlib import Path
from pydantic import ValidationError
from model.wiring import Wiring, register_layout, PIN_LAYOUT_REGISTRY


def test_register_layout_success():
    """Verify that register_layout registers layouts globally and namespaced successfully."""

    # Register a new unique mock layout globally
    @register_layout("my_global_pkg")
    def my_global_layout(pins, w, l, slots=None):
        pass

    assert "my_global_pkg" in PIN_LAYOUT_REGISTRY
    assert PIN_LAYOUT_REGISTRY["my_global_pkg"] == my_global_layout

    # Register a new unique mock layout explicitly namespaced
    @register_layout("my_ns_pkg", namespace="my_custom_namespace")
    def my_ns_layout(pins, w, l, slots=None):
        pass

    assert "my_custom_namespace:my_ns_pkg" in PIN_LAYOUT_REGISTRY
    assert PIN_LAYOUT_REGISTRY["my_custom_namespace:my_ns_pkg"] == my_ns_layout


def test_wiring_class():
    """Verify that the Wiring class correctly loads and resolves footprints and nets."""
    # Ensure layouts are registered
    import projects.cat_fountain.layouts  # type: ignore

    yaml_path = Path(__file__).parent.parent / "cat_fountain" / "wiring.yaml"
    wiring = Wiring(yaml_path)

    # Test footprints loading
    footprints = wiring.footprints
    assert len(footprints) > 0
    pico = next(f for f in footprints if f.name == "pico")
    assert pico.dimensions == (17.0, 52.0, 1.6)
    assert len(pico.pins) > 0
    assert pico.namespace == "cat_fountain"
    assert pico.package == "board"

    # Test pins layout calculation
    # GP2 (Pin 4) -> slot 3 on DIP grid.
    # X coordinate should be -8.5 (left side of width 17)
    # Y coordinate should be 26.0 - 2.0 - 3 * (48.0 / 19) = 16.421
    gp2_pin = next(p for p in pico.pins if p.name == "GP2")
    assert math.isclose(gp2_pin.position[0], -8.5, abs_tol=1e-3)
    assert math.isclose(gp2_pin.position[1], 16.421, abs_tol=1e-2)

    # Test nets loading
    nets = wiring.nets
    assert len(nets) > 0
    gnd_net = next(n for n in nets if n.name == "gnd")
    assert gnd_net.color == "black"


def test_register_layout_overlap():
    """Verify that registering duplicate layouts raises a ValueError."""
    # Ensure layouts are registered
    import projects.cat_fountain.layouts  # type: ignore

    # Try to register a mock layout for a key that is already registered
    # 'cat_fountain:board' is already registered
    with pytest.raises(ValueError, match="already registered"):

        @register_layout("board", namespace="cat_fountain")
        def duplicate_layout(pins, w, l, slots=None):
            pass


def test_validate_call_wiring():
    """Verify that Pydantic validate_call raises ValidationError on bad inputs."""
    # Passing an invalid type (e.g. list instead of Path) to Wiring ctor
    with pytest.raises(ValidationError):
        Wiring([1, 2, 3])  # type: ignore

    # Passing invalid type to register_layout
    with pytest.raises(ValidationError):
        register_layout(123)  # type: ignore


def test_automatic_namespace_inference():
    """Verify that register_layout infers namespace from caller's module."""

    def dummy_layout(pins, w, l, slots=None):
        pass

    # Mock the function's module path to simulate being inside projects package
    dummy_layout.__module__ = "projects.my_cool_project.layouts"

    # Manually invoke the decorator
    decorator = register_layout("dummy_pkg")
    decorator(dummy_layout)

    assert "my_cool_project:dummy_pkg" in PIN_LAYOUT_REGISTRY


def test_pico_gpio_labels_simplified():
    """Verify that Pico GPIO pins have simplified GPx labels without net name collisions (BUG-FOSSORIAL-BRISTLE-291)."""
    yaml_path = Path(__file__).parent.parent / "cat_fountain" / "wiring.yaml"
    wiring = Wiring(yaml_path)

    pico = next(f for f in wiring.footprints if f.name == "pico")
    power_gnd_labels = {"3 (GND)", "39 (VSYS)", "38 (GND)", "36 (3V3)"}

    gpio_pins = [p for p in pico.pins if p.name.startswith("GP")]
    assert len(gpio_pins) >= 16

    for pin in gpio_pins:
        # GPIO labels must be strictly their GPIO pin number, no parenthesized net names
        assert pin.label == pin.name
        assert "(" not in pin.label
        assert ")" not in pin.label

    # Power and GND pins should stay intact
    non_gpio = [p for p in pico.pins if not p.name.startswith("GP")]
    actual_labels = {p.label for p in non_gpio}
    assert power_gnd_labels.issubset(actual_labels)
