"""build123d custom context manager for declarative PCB part modeling with integrated stackup and metadata."""

from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from build123d import BuildPart
from build123d.build_common import operations_apply_to

from model.pcb import (
    AssemblyTestModel,
    AssemblyTestStepModel,
    BoardType,
    CapacitiveElectrodeModel,
    CopperRegionModel,
    FlexType,
    FlexZoneModel,
    MountingHoleModel,
    NetClassModel,
    PCBConfig,
    PCBDesignRulesModel,
    PCBObstacleModel,
    SchematicSheetModel,
    SheetSize,
    SilkscreenTextModel,
    SilkscreenGraphicModel,
    StackupModel,
    SymbolTableEntry,
    TestPointModel,
    TraceSegmentModel,
    ViaModel,
)
from provider.pcb.stackup import BuildStackup

_current_build_pcb: ContextVar[Optional["BuildPcb"]] = ContextVar("_current_build_pcb", default=None)

# Register custom PCB builders with build123d operation validator
for builders in operations_apply_to.values():
    if "BuildPart" in builders:
        if "BuildPcb" not in builders:
            builders.append("BuildPcb")
        if "BuildFlexPCB" not in builders:
            builders.append("BuildFlexPCB")


class BuildPcb(BuildPart):
    """Context manager for declarative PCB 3D part construction with attached stackup and layout metadata.

    Subclasses build123d's BuildPart so that standard 3D CAD modeling operations (Box, Cylinder,
    fillet, subtract, add) execute seamlessly while simultaneously encapsulating physical stackup,
    drill holes, traces, and fabrication rules for individual PCB subassemblies.
    """

    def __init__(
        self,
        name: str = "board",
        board_type: Union[BoardType, str] = BoardType.RIGID,
        shape_ref: Optional[str] = None,
        revision: str = "1.0",
        coverlay_color: Optional[str] = None,
        mode: Any = None,
    ) -> None:
        """Initialize PCB part builder context.

        Args:
            name: PCB identifier or subassembly name.
            board_type: Substrate construction ('rigid', 'flex', or 'rigid-flex').
            shape_ref: Optional target geometry shape reference (defaults to name).
            revision: Board revision identifier.
            coverlay_color: Optional protective coverlay film color (e.g. 'black').
            mode: Optional BuildMode for build123d part builder.
        """
        super().__init__(mode=mode)
        self.name = name
        self.shape_ref = shape_ref or name
        self.board_type: BoardType = BoardType(board_type) if isinstance(board_type, str) else board_type
        self.revision = revision
        self.coverlay_color = coverlay_color
        self.sheet_size: SheetSize = SheetSize.A4
        self.omitted_silkscreen_designators: List[str] = []
        self.design_rules: Optional[PCBDesignRulesModel] = None
        self.net_classes: List[NetClassModel] = []
        self.flex_zones: List[FlexZoneModel] = []
        self.obstacles: List[PCBObstacleModel] = []
        self.schematic_sheets: List[SchematicSheetModel] = []
        self.assembly_test: Optional[AssemblyTestModel] = None
        self.stackup_model: Optional[StackupModel] = None
        self.mounting_holes: List[MountingHoleModel] = []
        self.silkscreen_texts: List[SilkscreenTextModel] = []
        self.silkscreen_graphics: List[SilkscreenGraphicModel] = []
        self.traces: List[TraceSegmentModel] = []
        self.vias: List[ViaModel] = []
        self.copper_regions: List[CopperRegionModel] = []
        self.test_points: List[TestPointModel] = []
        self.capacitive_sensors: List[CapacitiveElectrodeModel] = []
        self.outline_polygon: Optional[List[Tuple[float, float]]] = None
        self.footprints: List[Any] = []
        self.nets: List[Any] = []
        self.symbol_table: Dict[str, SymbolTableEntry] = {}
        self.test_steps: List[AssemblyTestStepModel] = []
        self.wiring: Optional[Any] = None
        self._token: Optional[Token] = None

    @property
    def thickness_mm(self) -> float:
        """Return total substrate thickness derived from stackup or default 1.6 mm."""
        if self.stackup_model:
            return self.stackup_model.total_thickness_mm
        return 1.60

    def __enter__(self) -> "BuildPcb":
        """Enter context and set ambient BuildPcb context var."""
        super().__enter__()
        self._token = _current_build_pcb.set(self)
        from provider.pcb.metadata import PcbMetadata

        ambient_meta = PcbMetadata.current()
        if ambient_meta is not None:
            self.metadata = ambient_meta
            if ambient_meta.obstacles:
                self.obstacles.extend(ambient_meta.obstacles)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and attach metadata to the constructed CAD shape."""
        if self._token:
            try:
                _current_build_pcb.reset(self._token)
            except ValueError:
                _current_build_pcb.set(None)
            self._token = None
        super().__exit__(exc_type, exc_val, exc_tb)

        # Workaround folding: automatically set label and urdf_label
        lbl = self.shape_ref or self.name
        if self.part is not None:
            self.part.label = lbl
            self.part.urdf_label = lbl
        self.label = lbl
        self.urdf_label = lbl

        # Synthesize in-memory Wiring container if footprints or nets were registered
        from model.wiring import Wiring

        if self.wiring is None and (self.footprints or self.nets):
            self.wiring = Wiring.from_models(
                footprints=self.footprints,
                nets=self.nets,
            )

        # Attach metadata to the built part object and self for runtime discovery
        meta = self.to_pcb_config()
        self.pcb_metadata = meta
        if self.part is not None:
            setattr(self.part, "pcb_metadata", meta)
            if self.wiring is not None:
                setattr(self.part, "wiring", self.wiring)

    def to_pcb_config(self) -> PCBConfig:
        """Construct strongly-typed PCBConfig from context metadata."""
        dims = None
        if self.part is not None:
            bb = getattr(self.part, "bounding_box", None)
            if callable(bb):
                bbox = bb()
                dims = (round(bbox.size.X, 4), round(bbox.size.Y, 4), round(self.thickness_mm, 4))

        assembly_test = None
        if self.test_steps:
            assembly_test = AssemblyTestModel(
                instructions=list(self.test_steps),
                test_fixture="flying_probe",
                pass_criteria="all_steps_within_tolerance",
            )

        meta = getattr(self, "metadata", None)
        sheet_size = (meta.sheet_size if meta and meta.sheet_size else None) or self.sheet_size or SheetSize.A4
        omitted = list(self.omitted_silkscreen_designators)
        if meta and meta.omitted_silkscreen_designators:
            for des in meta.omitted_silkscreen_designators:
                if des not in omitted:
                    omitted.append(des)
        # Derive omitted silkscreen designators from footprints flagged with omit_silkscreen
        for fp in self.footprints:
            is_omitted = getattr(fp, "omit_silkscreen", False)
            if not is_omitted and hasattr(fp, "footprint"):
                is_omitted = getattr(fp.footprint, "omit_silkscreen", False)
            if is_omitted:
                fp_name = getattr(fp, "name", None) or getattr(getattr(fp, "footprint", None), "name", None)
                if fp_name and fp_name not in omitted:
                    omitted.append(fp_name)

        design_rules = (
            (meta.design_rules if meta and meta.design_rules else None) or self.design_rules or PCBDesignRulesModel()
        )
        b_type = (meta.board_type if meta and meta.board_type else None) or self.board_type
        rev = (meta.revision if meta and meta.revision else None) or self.revision
        f_type = meta.flex_type if meta and meta.flex_type else None
        net_classes = list(self.net_classes)
        if meta and meta.net_classes:
            for nc in meta.net_classes:
                if nc not in net_classes:
                    net_classes.append(nc)
        flex_zones = list(self.flex_zones)
        if meta and meta.flex_zones:
            for fz in meta.flex_zones:
                if fz not in flex_zones:
                    flex_zones.append(fz)
        cap_sensors = list(self.capacitive_sensors)
        if meta and meta.capacitive_sensors:
            for cs in meta.capacitive_sensors:
                if cs not in cap_sensors:
                    cap_sensors.append(cs)
        schematic_sheets = list(self.schematic_sheets)
        if meta and meta.schematic_sheets:
            for ss in meta.schematic_sheets:
                if ss not in schematic_sheets:
                    schematic_sheets.append(ss)
        obstacles = list(self.obstacles)
        if meta and meta.obstacles:
            for obs in meta.obstacles:
                if obs not in obstacles:
                    obstacles.append(obs)
        assembly_test = getattr(self, "assembly_test", None) or (
            meta.assembly_test if meta and meta.assembly_test else None
        )
        if assembly_test is None and self.test_steps:
            assembly_test = AssemblyTestModel(
                instructions=list(self.test_steps),
                test_fixture="flying_probe",
                pass_criteria="all_steps_within_tolerance",
            )

        return PCBConfig(
            name=self.name,
            board_type=b_type,
            flex_type=f_type,
            revision=rev,
            coverlay_color=self.coverlay_color,
            dimensions_mm=dims,
            shape_ref=meta.shape_ref if meta and getattr(meta, "shape_ref", None) else self.shape_ref,
            sheet_size=sheet_size,
            omitted_silkscreen_designators=omitted,
            design_rules=design_rules,
            net_classes=net_classes,
            flex_zones=flex_zones,
            capacitive_sensors=cap_sensors,
            schematic_sheets=schematic_sheets,
            stackup=self.stackup_model,
            mounting_holes=list(self.mounting_holes),
            silkscreen_texts=list(self.silkscreen_texts),
            silkscreen_graphics=list(self.silkscreen_graphics),
            traces=list(self.traces),
            vias=list(self.vias),
            copper_regions=list(self.copper_regions),
            outline_polygon=list(self.outline_polygon) if self.outline_polygon else None,
            test_points=list(self.test_points),
            obstacles=obstacles,
            symbol_table=dict(self.symbol_table),
            test_steps=list(self.test_steps),
            assembly_test=assembly_test,
        )

    def to_cad_assembly(self) -> Any:
        """Synthesize a complete 3D CAD Compound assembly containing all active PCB layers."""
        from provider.pcb.cad_assembler import PCB3DAssembler

        assembler = PCB3DAssembler.from_build_pcb(self)
        return assembler.to_cad_assembly()

    def populate_room(self, room: Any, prefix: Optional[str] = None) -> None:
        """Populate distinct CAD layers directly into a Room object for interactive CAD viewing."""
        from provider.pcb.cad_assembler import PCB3DAssembler

        assembler = PCB3DAssembler.from_build_pcb(self)
        assembler.populate_room(room, prefix=prefix or self.name)

    @classmethod
    def current(cls) -> Optional["BuildPcb"]:
        """Return the active ambient BuildPcb context if set."""
        return _current_build_pcb.get()


class BuildFlexPCB(BuildPcb):
    """Context manager for flexible polyimide PCB subassemblies.

    Supports different flexible PCB types: 'connector', 'component', and 'capacitive'.
    """

    def __init__(
        self,
        name: str = "flex_pcb",
        flex_type: Union[FlexType, str] = FlexType.CAPACITIVE,
        shape_ref: Optional[str] = None,
        revision: str = "1.0",
        coverlay_color: Optional[str] = "black",
        mode: Any = None,
    ) -> None:
        """Initialize flexible PCB context with typed flex_type."""
        super().__init__(
            name=name,
            board_type=BoardType.FLEX,
            shape_ref=shape_ref,
            revision=revision,
            coverlay_color=coverlay_color,
            mode=mode,
        )
        self.flex_type: FlexType = FlexType(flex_type) if isinstance(flex_type, str) else flex_type

    def to_pcb_config(self) -> PCBConfig:
        """Construct strongly-typed PCBConfig including flex_type metadata."""
        cfg = super().to_pcb_config()
        return cfg.model_copy(update={"flex_type": self.flex_type, "coverlay_color": self.coverlay_color})
