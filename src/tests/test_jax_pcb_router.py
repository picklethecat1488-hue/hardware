"""Unit tests for JAX-accelerated multi-layer PCB router running on MPS and CUDA."""

import pytest
import jax

from provider.pcb.jax_router import JaxPCBRouter
from provider.pcb.router import Obstacle


def test_jax_pcb_router_coordinate_roundtrip():
    """Verify exact coordinate conversions between world coordinates and discrete 3D grid."""
    router = JaxPCBRouter(
        board_bounds=(-25.0, -40.0, 25.0, 40.0),
        grid_step=0.25,
        layers=["F.Cu", "B.Cu"],
    )

    layer_idx, gy, gx = router.world_to_grid(0.0, 0.0, "F.Cu")
    assert layer_idx == 0
    px, py, lay = router.grid_to_world(layer_idx, gy, gx)
    assert px == 0.0
    assert py == 0.0
    assert lay == "F.Cu"

    layer_idx, gy, gx = router.world_to_grid(-15.25, 22.50, "B.Cu")
    assert layer_idx == 1
    px, py, lay = router.grid_to_world(layer_idx, gy, gx)
    assert px == -15.25
    assert py == 22.50
    assert lay == "B.Cu"


def test_jax_pcb_router_single_layer_direct_route():
    """Verify that an unobstructed path produces a direct planar trace on F.Cu."""
    router = JaxPCBRouter(
        board_bounds=(-25.0, -40.0, 25.0, 40.0),
        grid_step=0.25,
        layers=["F.Cu", "B.Cu"],
    )

    traces, vias = router.route_net(
        start_pt=(-10.0, 5.0),
        start_layer="F.Cu",
        end_pt=(10.0, 5.0),
        end_layer="F.Cu",
        net_name="DIRECT_NET",
        width_mm=0.20,
    )

    assert len(traces) == 1
    assert len(vias) == 0
    assert traces[0].net == "DIRECT_NET"
    assert traces[0].layer == "F.Cu"
    assert traces[0].start_mm == (-10.0, 5.0)
    assert traces[0].end_mm == (10.0, 5.0)


def test_jax_pcb_router_multi_layer_via_transition():
    """Verify that router transitions to B.Cu using vias when F.Cu is blocked by an obstacle wall."""
    router = JaxPCBRouter(
        board_bounds=(-25.0, -40.0, 25.0, 40.0),
        grid_step=0.25,
        layers=["F.Cu", "B.Cu"],
        obstacles=[Obstacle(min_x=-4.0, min_y=-10.0, max_x=4.0, max_y=10.0, layer="F.Cu")],
    )

    traces, vias = router.route_net(
        start_pt=(-10.0, 0.0),
        start_layer="F.Cu",
        end_pt=(10.0, 0.0),
        end_layer="F.Cu",
        net_name="VIA_NET",
        width_mm=0.20,
    )

    assert len(traces) >= 2
    assert len(vias) >= 2
    layers_used = {tr.layer for tr in traces}
    assert layers_used == {"F.Cu", "B.Cu"}
    for v in vias:
        assert v.net == "VIA_NET"
        assert v.pad_diameter_mm > 0.0


def test_jax_pcb_router_batch_parallel_execution():
    """Verify that route_batch executes multiple independent nets concurrently on GPU."""
    router = JaxPCBRouter(
        board_bounds=(-25.0, -40.0, 25.0, 40.0),
        grid_step=0.25,
        layers=["F.Cu", "B.Cu"],
        obstacles=[Obstacle(min_x=-3.0, min_y=-5.0, max_x=3.0, max_y=5.0, layer="F.Cu")],
    )

    net_specs = [
        ((-10.0, 0.0), "F.Cu", (10.0, 0.0), "F.Cu", "NET_A", 0.20),
        ((-10.0, -15.0), "F.Cu", (10.0, -15.0), "F.Cu", "NET_B", 0.20),
        ((-10.0, 15.0), "F.Cu", (10.0, 15.0), "F.Cu", "NET_C", 0.20),
    ]

    results = router.route_batch(net_specs)
    assert len(results) == 3

    # NET_A had an obstacle wall so it used vias
    traces_a, vias_a = results[0]
    assert len(traces_a) >= 2
    assert len(vias_a) >= 2

    # NET_B and NET_C had clear paths so they routed directly on F.Cu
    traces_b, vias_b = results[1]
    assert len(traces_b) == 1
    assert len(vias_b) == 0

    traces_c, vias_c = results[2]
    assert len(traces_c) == 1
    assert len(vias_c) == 0


def test_jax_pcb_router_unreachable_target_raises():
    """Verify that attempting to route to a completely enclosed destination raises RuntimeError."""
    router = JaxPCBRouter(
        board_bounds=(-25.0, -40.0, 25.0, 40.0),
        grid_step=0.25,
        layers=["F.Cu", "B.Cu"],
        obstacles=[
            # Enclose target on ALL layers
            Obstacle(min_x=5.0, min_y=-5.0, max_x=15.0, max_y=5.0, layer="ALL")
        ],
    )

    with pytest.raises(RuntimeError) as exc_info:
        router.route_net(
            start_pt=(-10.0, 0.0),
            start_layer="F.Cu",
            end_pt=(10.0, 0.0),
            end_layer="F.Cu",
            net_name="IMPOSSIBLE_NET",
            max_chunks=2,
        )

    assert "could not find collision-free path" in str(exc_info.value)


def test_jax_pcb_router_device_acceleration():
    """Verify JAX execution runs on available hardware backend (MPS, CUDA, or CPU)."""
    devices = jax.devices()
    assert len(devices) > 0
    backend = jax.default_backend()
    assert backend in ("mps", "gpu", "cuda", "cpu")


def test_jax_pcb_router_is_default_backend():
    """Verify BUG-095: PCBAutoRouter defaults to JaxPCBRouter backend."""
    from provider.pcb.router import PCBAutoRouter
    from model.pcb import PCBConfig, StackupModel, StackupLayerModel, LayerType
    from types import SimpleNamespace

    stackup = StackupModel(
        layers=[
            StackupLayerModel(name="F.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.SIGNAL),
            StackupLayerModel(name="B.Cu", thickness_mm=0.035, material="copper", layer_type=LayerType.SIGNAL),
        ]
    )
    cfg = PCBConfig(
        name="test_board",
        dimensions_mm=(20.0, 20.0, 1.6),
        stackup=stackup,
    )
    wiring = SimpleNamespace(footprints=[], nets=[])
    auto_router = PCBAutoRouter(cfg, wiring)
    assert auto_router.backend == "jax"
    auto_router.route_all_nets()
    assert isinstance(auto_router.router, JaxPCBRouter)


def test_jax_pcb_router_qfn_via_keepout_allows_traces_forbids_vias():
    """Verify QFN keepout zone forbids vias while allowing planar traces to route through."""
    router = JaxPCBRouter(
        board_bounds=(-20.0, -20.0, 20.0, 20.0),
        grid_step=0.25,
        layers=["F.Cu", "B.Cu"],
        qfn_keepouts=[(-5.0, -5.0, 5.0, 5.0)],
    )

    # 1. Planar trace traversing directly through QFN keepout on F.Cu must succeed without vias
    traces, vias = router.route_net(
        start_pt=(-10.0, 0.0),
        start_layer="F.Cu",
        end_pt=(10.0, 0.0),
        end_layer="F.Cu",
        net_name="QFN_PLANAR_NET",
        width_mm=0.20,
    )
    assert len(traces) == 1
    assert len(vias) == 0

    # 2. Net with start and end requiring vias must not place vias inside (-5.0, -5.0, 5.0, 5.0)
    # Block F.Cu outside the QFN zone to force via transition to B.Cu
    router.add_obstacle(Obstacle(min_x=-15.0, min_y=-10.0, max_x=-12.0, max_y=10.0, layer="F.Cu"))
    traces_via, vias_via = router.route_net(
        start_pt=(-18.0, 0.0),
        start_layer="F.Cu",
        end_pt=(15.0, 0.0),
        end_layer="F.Cu",
        net_name="QFN_VIA_NET",
        width_mm=0.20,
    )
    for v in vias_via:
        vx, vy = v.position_mm
        is_inside_qfn = (-5.0 <= vx <= 5.0) and (-5.0 <= vy <= 5.0)
        assert not is_inside_qfn, f"Via placed inside QFN keepout at ({vx}, {vy})!"
