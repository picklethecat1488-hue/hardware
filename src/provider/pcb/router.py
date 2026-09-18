"""PCB auto-router engine computing Manhattan and multi-layer routes for component netlists."""

from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

from model.pcb import PCBConfig, TraceSegmentModel, ViaModel
from model.wiring import Wiring


class PCBAutoRouter:
    """Automated routing engine generating copper traces and interlayer vias for board nets."""

    def __init__(self, pcb_config: Union[PCBConfig, Dict], wiring: Wiring) -> None:
        """Initialize router with board configuration and electrical netlist."""
        if isinstance(pcb_config, dict):
            self.config = PCBConfig(**pcb_config)
        else:
            self.config = pcb_config
        self.wiring = wiring

    def get_net_trace_width(self, net_name: str) -> float:
        """Resolve trace width for a given net based on net classes and interfaces."""
        net_upper = net_name.upper()

        # Check differential pairs in net classes
        for nc in self.config.net_classes:
            for dp in nc.diff_pairs:
                if net_name in (dp.pos_net, dp.neg_net):
                    return nc.trace_width_mm
            if nc.name.upper() in net_upper:
                return nc.trace_width_mm

        # Check standard interface patterns
        if "PCIE" in net_upper:
            return 0.14
        if "MIPI" in net_upper or "DISP" in net_upper:
            return 0.12
        if "RF" in net_upper or "CPWG" in net_upper:
            return 0.22
        if any(pwr in net_upper for pwr in ("GND", "3V3", "5V", "VCC", "VDD", "VLOAD")):
            return 0.30

        return 0.20

    def route_all_nets(self, exclude_nets: Optional[Set[str]] = None) -> Tuple[List[TraceSegmentModel], List[ViaModel]]:
        """Route all electrical nets in the netlist, connecting pin pairs with traces and vias.

        Args:
            exclude_nets: Set of net names to skip (e.g. manually routed flex tail nets).

        Returns:
            Tuple of (generated_trace_segments, generated_interlayer_vias).
        """
        skip_nets = exclude_nets or set()
        traces: List[TraceSegmentModel] = []
        vias: List[ViaModel] = []

        # Index components and pin absolute locations
        comp_map = {fp.name: fp for fp in self.wiring.footprints}

        for net in self.wiring.nets:
            if net.name in skip_nets or len(net.pins) < 2:
                continue

            width = self.get_net_trace_width(net.name)

            # Resolve absolute pin coordinates
            pin_locs: List[Tuple[float, float, str]] = []  # (x, y, layer)
            for comp_name, pin_name in net.pins:
                fp = comp_map.get(comp_name)
                if not fp:
                    continue
                pin = next((p for p in fp.pins if p.name == pin_name), None)
                if not pin:
                    continue

                px = fp.position[0] + pin.position[0]
                py = fp.position[1] + pin.position[1]
                layer = getattr(fp, "layer", None) or ("B.Cu" if fp.position[2] < 0 else "F.Cu")
                pin_locs.append((round(px, 4), round(py, 4), layer))

            if len(pin_locs) < 2:
                continue

            # Route sequentially connecting consecutive pins in net (spanning tree / daisy chain)
            for i in range(len(pin_locs) - 1):
                x1, y1, l1 = pin_locs[i]
                x2, y2, l2 = pin_locs[i + 1]

                if l1 == l2:
                    # Same-layer Manhattan routing
                    if abs(x1 - x2) > 0.01 and abs(y1 - y2) > 0.01:
                        # Dogleg corner at (x2, y1)
                        traces.append(
                            TraceSegmentModel(
                                start_mm=(x1, y1),
                                end_mm=(x2, y1),
                                width_mm=width,
                                layer=l1,
                                net=net.name,
                            )
                        )
                        traces.append(
                            TraceSegmentModel(
                                start_mm=(x2, y1),
                                end_mm=(x2, y2),
                                width_mm=width,
                                layer=l1,
                                net=net.name,
                            )
                        )
                    else:
                        # Straight segment
                        traces.append(
                            TraceSegmentModel(
                                start_mm=(x1, y1),
                                end_mm=(x2, y2),
                                width_mm=width,
                                layer=l1,
                                net=net.name,
                            )
                        )
                else:
                    # Multi-layer routing: Route on l1, drop via, route on l2
                    # Place via offset near pin 2
                    via_offset = 1.2
                    vx = x2 - via_offset if x2 >= x1 else x2 + via_offset
                    vy = y2

                    # Via connecting l1 and l2
                    vias.append(
                        ViaModel(
                            position_mm=(round(vx, 4), round(vy, 4)),
                            drill_diameter_mm=0.20,
                            pad_diameter_mm=0.45,
                            layer_start="F.Cu",
                            layer_end="B.Cu",
                            net=net.name,
                        )
                    )

                    # Trace on l1 from pin 1 to via
                    traces.append(
                        TraceSegmentModel(
                            start_mm=(x1, y1),
                            end_mm=(round(vx, 4), y1),
                            width_mm=width,
                            layer=l1,
                            net=net.name,
                        )
                    )
                    if abs(y1 - vy) > 0.01:
                        traces.append(
                            TraceSegmentModel(
                                start_mm=(round(vx, 4), y1),
                                end_mm=(round(vx, 4), round(vy, 4)),
                                width_mm=width,
                                layer=l1,
                                net=net.name,
                            )
                        )

                    # Trace on l2 from via to pin 2
                    traces.append(
                        TraceSegmentModel(
                            start_mm=(round(vx, 4), round(vy, 4)),
                            end_mm=(x2, y2),
                            width_mm=width,
                            layer=l2,
                            net=net.name,
                        )
                    )

        return traces, vias
