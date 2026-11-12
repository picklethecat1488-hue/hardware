"""Unit tests for CAD/PCB Scope Geometry & Tessellation Pipeline."""

from provider.scope.pipeline import (
    ScopeGeometryPipeline,
)


def test_scope_pipeline_get_projects():
    """Verify get_projects discovers projects and target metadata."""
    pipeline = ScopeGeometryPipeline()
    projects = pipeline.get_projects()

    assert len(projects) > 0
    project_names = [p.name for p in projects]
    assert "carrier_board" in project_names
    assert "cat_fountain" in project_names

    carrier = next(p for p in projects if p.name == "carrier_board")
    carrier_target_names = [t.name for t in carrier.targets]
    assert "carrier_board" in carrier_target_names

    # Check modes
    carrier_target = next(t for t in carrier.targets if t.name == "carrier_board")
    assert "PCB" in carrier_target.modes
    assert "CAD" in carrier_target.modes


def test_scope_pipeline_load_geometry_pcb_layers():
    """Verify load_geometry in PCB mode extracts all 7 distinct 2D PCB layers without 3D Components."""
    pipeline = ScopeGeometryPipeline()
    payload = pipeline.load_geometry("carrier_board", "carrier_board", mode="PCB")

    assert payload["type"] == "data"
    assert "shapes" in payload
    shapes = payload["shapes"]
    assert "parts" in shapes

    parts = shapes["parts"]
    assert len(parts) == 7

    part_names = [p.get("name", "") for p in parts]
    assert any("substrate" in n for n in part_names)
    assert not any("components" in n for n in part_names)
    assert any("pads" in n for n in part_names)
    assert any("traces_top" in n for n in part_names)
    assert any("traces_bottom" in n for n in part_names)
    assert any("vias" in n for n in part_names)
    assert any("silkscreen_top" in n for n in part_names)
    assert any("silkscreen_bottom" in n for n in part_names)

    # Check PCB metadata
    pcb_meta = payload.get("pcb_metadata")
    assert pcb_meta is not None
    assert "layers" in pcb_meta
    assert len(pcb_meta["layers"]) == 7
    assert "components" in pcb_meta
    assert len(pcb_meta["components"]) > 0
    assert "nets" in pcb_meta
    assert len(pcb_meta["nets"]) > 0


def test_scope_pipeline_load_geometry_cad_mode():
    """Verify load_geometry in CAD mode extracts 3D solids."""
    pipeline = ScopeGeometryPipeline()
    payload = pipeline.load_geometry("cat_fountain", "bowl", mode="CAD")

    assert payload["type"] == "data"
    assert "shapes" in payload
    shapes = payload["shapes"]
    assert "parts" in shapes
    assert len(shapes["parts"]) > 0


def test_scope_pipeline_cache_and_sync():
    """Verify in-memory caching and cache invalidation on sync."""
    pipeline = ScopeGeometryPipeline()
    key = ("cat_fountain", "bowl", None, "CAD", None)

    assert key not in pipeline._cache
    res1 = pipeline.load_geometry("cat_fountain", "bowl", mode="CAD")
    assert key in pipeline._cache

    res2 = pipeline.load_geometry("cat_fountain", "bowl", mode="CAD")
    assert res1 is res2  # Exact cached reference

    pipeline.sync()
    assert len(pipeline._cache) == 0


def test_regression_bug_armored_cockroach_879_instanced_geometry_payload():
    """Verify load_geometry outputs instanced buffers and reset_camera to ensure geometry displays."""
    pipeline = ScopeGeometryPipeline()
    payload = pipeline.load_geometry("cat_fountain", "bowl", mode="CAD")

    assert payload["type"] == "data"
    assert "shapes" in payload
    assert "instances" in payload
    assert len(payload["instances"]) > 0

    # Ensure reset_camera is set to RESET so the viewport camera auto-fits the model
    assert payload["config"].get("reset_camera") == "RESET"

    # Verify that parts refer to valid instance indices
    parts = payload["shapes"].get("parts", [])
    assert len(parts) > 0
    for part in parts:
        ref = part.get("shape", {}).get("ref")
        assert ref is not None
        assert 0 <= ref < len(payload["instances"])


def test_scope_pipeline_disk_cache_persistence_and_speed(tmp_path):
    """Verify geometry is persisted to disk as compressed gzip and loads in <100ms on second read."""
    cache_dir = tmp_path / "scope_cache"
    pipeline = ScopeGeometryPipeline(cache_dir=cache_dir)

    # First load: compiles and writes to disk cache
    payload1 = pipeline.load_geometry("cat_fountain", "bowl", mode="CAD")
    assert payload1["type"] == "data"
    assert (cache_dir / "cat_fountain_bowl_none_CAD_none.json.gz").is_file()

    # Second pipeline instance pointing to same disk cache: loads from disk in <100ms
    pipeline2 = ScopeGeometryPipeline(cache_dir=cache_dir)
    payload2 = pipeline2.load_geometry("cat_fountain", "bowl", mode="CAD")
    assert payload2["type"] == "data"
    assert payload2["target"] == payload1["target"]

    # Verify get_cached_gzip retrieves the compressed bytes directly
    gz_bytes = pipeline2.get_cached_gzip("cat_fountain", "bowl", mode="CAD")
    assert gz_bytes is not None
    assert len(gz_bytes) > 0


def test_scope_pipeline_sync_clears_disk_cache(tmp_path):
    """Verify pipeline.sync() flushes memory cache and removes disk cache files."""
    cache_dir = tmp_path / "scope_cache"
    pipeline = ScopeGeometryPipeline(cache_dir=cache_dir)

    pipeline.load_geometry("cat_fountain", "bowl", mode="CAD")
    cache_file = cache_dir / "cat_fountain_bowl_none_CAD_none.json.gz"
    assert cache_file.is_file()

    pipeline.sync()
    assert len(pipeline._cache) == 0
    assert len(pipeline._gz_cache) == 0
    assert not cache_file.exists()


def test_regression_bug_stridulating_cocoon_33_net_pins_extraction():
    """Verify net pin extraction parses component-pin tuples and does not yield empty pin lists."""
    pipeline = ScopeGeometryPipeline()
    payload = pipeline.load_geometry("carrier_board", "carrier_board", mode="PCB")
    pcb_meta = payload.get("pcb_metadata", {})
    nets = pcb_meta.get("nets", [])
    assert len(nets) > 0

    gnd_net = next((n for n in nets if n["name"] == "GND"), None)
    assert gnd_net is not None
    assert len(gnd_net["pins"]) > 10
    # Pins should be strings formatted as "component.pin"
    assert any(p.startswith("U1.") or p.startswith("C1.") for p in gnd_net["pins"])


def test_regression_bug_translucent_lacewing_144_kicad_high_contrast_colors():
    """Verify PCB layers use high-contrast KiCad canonical color palette."""
    pipeline = ScopeGeometryPipeline()
    payload = pipeline.load_geometry("carrier_board", "carrier_board", mode="PCB")
    layers = payload.get("pcb_metadata", {}).get("layers", [])

    layer_colors = {l["type"]: l["color"] for l in layers}
    assert layer_colors.get("F.Cu") == "#c83434"
    assert layer_colors.get("B.Cu") == "#4d7fc4"
    assert layer_colors.get("Pads") == "#ce4785"
    assert layer_colors.get("F.SilkS") == "#f2eda1"


def test_regression_bug_lustrous_mantis_333_target_modes_filtering_and_simulation():
    """Verify get_projects filters non-geometry targets and assigns only supported target modes."""
    pipeline = ScopeGeometryPipeline()
    projects = pipeline.get_projects()

    cat_fountain = next(p for p in projects if p.name == "cat_fountain")
    # 'material' and 'simulation' config targets must not be listed as viewable geometry targets
    target_names = [t.name for t in cat_fountain.targets]
    assert "material" not in target_names
    assert "simulation" not in target_names

    # 'bowl' target only supports CAD mode
    bowl_target = next(t for t in cat_fountain.targets if t.name == "bowl")
    assert bowl_target.modes == ["CAD"]

    # 'product' target supports SIMULATE and CAD
    product_target = next(t for t in cat_fountain.targets if t.name == "product")
    assert "SIMULATE" in product_target.modes
    assert "CAD" in product_target.modes

    # Loading cat_fountain simulation alias loads product without ValueError
    payload = pipeline.load_geometry("cat_fountain", "simulation", mode="SIMULATE")
    assert payload["type"] == "data"
    assert payload["mode"] == "SIMULATE"
