"""Declarative context manager for PCB fabrication rules, documentation, and manufacturing metadata."""

from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional, Sequence, Union

from model.pcb import (
    AssemblyTestModel,
    BoardType,
    CapacitiveElectrodeModel,
    FlexType,
    FlexZoneModel,
    NetClassModel,
    PCBDesignRulesModel,
    PCBObstacleModel,
    SchematicSheetModel,
    SheetSize,
)

_current_pcb_metadata: ContextVar[Optional["PcbMetadata"]] = ContextVar("_current_pcb_metadata", default=None)


class PcbMetadata:
    """Context manager and container for board fabrication, layout rules, and manufacturing metadata."""

    def __init__(
        self,
        sheet_size: Union[SheetSize, str] = SheetSize.A4,
        omitted_silkscreen_designators: Optional[Sequence[str]] = None,
        obstacles: Optional[Sequence[Union[PCBObstacleModel, Dict[str, Any]]]] = None,
        design_rules: Optional[Union[PCBDesignRulesModel, Dict[str, Any]]] = None,
        net_classes: Optional[Sequence[Union[NetClassModel, Dict[str, Any]]]] = None,
        flex_zones: Optional[Sequence[Union[FlexZoneModel, Dict[str, Any]]]] = None,
        capacitive_sensors: Optional[Sequence[Union[CapacitiveElectrodeModel, Dict[str, Any]]]] = None,
        schematic_sheets: Optional[Sequence[Union[SchematicSheetModel, Dict[str, Any]]]] = None,
        assembly_test: Optional[Union[AssemblyTestModel, Dict[str, Any]]] = None,
        revision: Optional[str] = None,
        board_type: Optional[Union[BoardType, str]] = None,
        flex_type: Optional[Union[FlexType, str]] = None,
        shape_ref: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize PCB metadata container."""
        self.sheet_size = SheetSize(sheet_size) if isinstance(sheet_size, str) else sheet_size
        self.omitted_silkscreen_designators = list(omitted_silkscreen_designators or [])
        self.revision = revision
        self.board_type = BoardType(board_type) if isinstance(board_type, str) else board_type
        self.flex_type = FlexType(flex_type) if isinstance(flex_type, str) else flex_type
        self.shape_ref = shape_ref

        # Parse obstacles
        self.obstacles: List[PCBObstacleModel] = []
        for obs in obstacles or []:
            if isinstance(obs, PCBObstacleModel):
                self.obstacles.append(obs)
            elif isinstance(obs, dict):
                self.obstacles.append(PCBObstacleModel(**obs))

        # Parse design rules
        if isinstance(design_rules, PCBDesignRulesModel):
            self.design_rules: Optional[PCBDesignRulesModel] = design_rules
        elif isinstance(design_rules, dict):
            self.design_rules = PCBDesignRulesModel(**design_rules)
        else:
            self.design_rules = None

        # Parse net classes
        self.net_classes: List[NetClassModel] = []
        for nc in net_classes or []:
            if isinstance(nc, NetClassModel):
                self.net_classes.append(nc)
            elif isinstance(nc, dict):
                self.net_classes.append(NetClassModel(**nc))

        # Parse flex zones
        self.flex_zones: List[FlexZoneModel] = []
        for fz in flex_zones or []:
            if isinstance(fz, FlexZoneModel):
                self.flex_zones.append(fz)
            elif isinstance(fz, dict):
                self.flex_zones.append(FlexZoneModel(**fz))

        # Parse capacitive sensors
        self.capacitive_sensors: List[CapacitiveElectrodeModel] = []
        for cs in capacitive_sensors or []:
            if isinstance(cs, CapacitiveElectrodeModel):
                self.capacitive_sensors.append(cs)
            elif isinstance(cs, dict):
                self.capacitive_sensors.append(CapacitiveElectrodeModel(**cs))

        # Parse schematic sheets
        self.schematic_sheets: List[SchematicSheetModel] = []
        for ss in schematic_sheets or []:
            if isinstance(ss, SchematicSheetModel):
                self.schematic_sheets.append(ss)
            elif isinstance(ss, dict):
                self.schematic_sheets.append(SchematicSheetModel(**ss))

        # Parse assembly test
        if isinstance(assembly_test, AssemblyTestModel):
            self.assembly_test: Optional[AssemblyTestModel] = assembly_test
        elif isinstance(assembly_test, dict):
            self.assembly_test = AssemblyTestModel(**assembly_test)
        else:
            self.assembly_test = None

        self.extra = dict(kwargs)
        self._token: Optional[Token] = None

    def __enter__(self) -> "PcbMetadata":
        """Enter context and attach to ambient BuildPcb if present."""
        self._token = _current_pcb_metadata.set(self)
        from provider.pcb.board import BuildPcb

        current_pcb = BuildPcb.current()
        if current_pcb is not None:
            setattr(current_pcb, "metadata", self)
            if self.obstacles:
                current_pcb.obstacles.extend(self.obstacles)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and reset token."""
        if self._token:
            _current_pcb_metadata.reset(self._token)
            self._token = None

    @classmethod
    def current(cls) -> Optional["PcbMetadata"]:
        """Return the active ambient PcbMetadata context if set."""
        return _current_pcb_metadata.get()
