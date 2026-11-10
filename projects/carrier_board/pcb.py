"""Combined PCB definitions for Carrier Board and Flex Tail."""

from typing import Optional, Any
from model.pcb import PCBConfig
from model import Wiring
from .carrier_board import (
    CarrierBoardPCBListing,
    build_carrier_board_wiring,
    build_carrier_board_system_wiring,
    build_carrier_board_pcb_config,
)
from .flex_tail import (
    FlexTailPCBListing,
    get_flex_tail_traces,
    get_flex_tail_vias,
)


class CarrierBoardPCB(CarrierBoardPCBListing, FlexTailPCBListing):
    """Unified PCB mixin for carrier board and flex tail substrates."""


__all__ = [
    "CarrierBoardPCB",
    "CarrierBoardPCBListing",
    "FlexTailPCBListing",
    "build_carrier_board_wiring",
    "build_carrier_board_system_wiring",
    "build_carrier_board_pcb_config",
    "get_flex_tail_traces",
    "get_flex_tail_vias",
]
