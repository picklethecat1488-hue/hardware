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
        sheet_size: Union[SheetSize, str] = SheetSize.A4,
        omitted_silkscreen_designators: Optional[Sequence[str]] = None,
        design_rules: Optional[Union[PCBDesignRulesModel, Dict[str, Any]]] = None,
        net_classes: Optional[Sequence[Union[NetClassModel, Dict[str, Any]]]] = None,
        flex_zones: Optional[Sequence[Union[FlexZoneModel, Dict[str, Any]]]] = None,
        obstacles: Optional[Sequence[Union[PCBObstacleModel, Dict[str, Any]]]] = None,
        schematic_sheets: Optional[Sequence[Union[SchematicSheetModel, Dict[str, Any]]]] = None,
        assembly_test: Optional[Union[AssemblyTestModel, Dict[str, Any]]] = None,
        stackup: Optional[Union[BuildStackup, StackupModel]] = None,
        capacitive_sensors: Optional[Sequence[CapacitiveElectrodeModel]] = None,
        outline_polygon: Optional[Sequence[Tuple[float, float]]] = None,
        coverlay_color: Optional[str] = None,
        mode: Any = None,
    ) -> None:
        """Initialize PCB part builder context.

        Args:
            name: PCB identifier or subassembly name.
            board_type: Substrate construction ('rigid', 'flex', or 'rigid-flex').
            shape_ref: Optional target geometry shape reference (defaults to name).
            revision: Board revision identifier.
            sheet_size: Schematic sheet size standard (A4, A3, etc.).
            omitted_silkscreen_designators: Optional sequence of designators to omit from silkscreen.
            design_rules: Fabrication clearance and DRC constraints.
            net_classes: High-speed and differential net classes.
            flex_zones: Rigid-flex flexible substrate zones.
            obstacles: 3D clearance keepouts and component bounding obstacles.
            schematic_sheets: Schematic drawing sheet definitions.
            assembly_test: Factory automated test instructions.
            stackup: Multi-layer stackup model or BuildStackup context.
            capacitive_sensors: Optional sequence of capacitive electrode models.
            outline_polygon: Board contour polygon vertices.
            coverlay_color: Optional protective coverlay film color (e.g. 'black').
            mode: Optional BuildMode for build123d part builder.
        """
        super().__init__(mode=mode)
        self.name = name
        self.shape_ref = shape_ref or name
        self.board_type: BoardType = BoardType(board_type) if isinstance(board_type, str) else board_type
        self.revision = revision
        self.sheet_size = SheetSize(sheet_size) if isinstance(sheet_size, str) else sheet_size
        self.coverlay_color = coverlay_color
        self.omitted_silkscreen_designators: List[str] = list(omitted_silkscreen_designators or [])

        if isinstance(design_rules, PCBDesignRulesModel):
            self.design_rules: Optional[PCBDesignRulesModel] = design_rules
        elif isinstance(design_rules, dict):
            self.design_rules = PCBDesignRulesModel(**design_rules)
        else:
            self.design_rules = None

        self.net_classes: List[NetClassModel] = []
        for nc in net_classes or []:
            self.net_classes.append(nc if isinstance(nc, NetClassModel) else NetClassModel(**nc))

        self.flex_zones: List[FlexZoneModel] = []
        for fz in flex_zones or []:
            self.flex_zones.append(fz if isinstance(fz, FlexZoneModel) else FlexZoneModel(**fz))

        self.obstacles: List[PCBObstacleModel] = []
        for obs in obstacles or []:
            self.obstacles.append(obs if isinstance(obs, PCBObstacleModel) else PCBObstacleModel(**obs))

        self.schematic_sheets: List[SchematicSheetModel] = []
        for ss in schematic_sheets or []:
            self.schematic_sheets.append(ss if isinstance(ss, SchematicSheetModel) else SchematicSheetModel(**ss))

        if isinstance(assembly_test, AssemblyTestModel):
            self.assembly_test: Optional[AssemblyTestModel] = assembly_test
        elif isinstance(assembly_test, dict):
            self.assembly_test = AssemblyTestModel(**assembly_test)
        else:
            self.assembly_test = None

        if isinstance(stackup, BuildStackup):
            self.stackup_model: Optional[StackupModel] = stackup.to_model()
        else:
            self.stackup_model = stackup

        self.mounting_holes: List[MountingHoleModel] = []
        self.silkscreen_texts: List[SilkscreenTextModel] = []
        self.silkscreen_graphics: List[SilkscreenGraphicModel] = []
        self.traces: List[TraceSegmentModel] = []
        self.vias: List[ViaModel] = []
        self.copper_regions: List[CopperRegionModel] = []
        self.test_points: List[TestPointModel] = []
        self.capacitive_sensors: List[CapacitiveElectrodeModel] = list(capacitive_sensors or [])
        self.outline_polygon: Optional[List[Tuple[float, float]]] = (
            [tuple(p) for p in outline_polygon] if outline_polygon else None
        )
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
            _current_build_pcb.reset(self._token)
            self._token = None
        super().__exit__(exc_type, exc_val, exc_tb)

        # Workaround folding: automatically set label and urdf_label
        if self.part is not None:
            self.part.label = self.name
            self.part.urdf_label = self.name
        self.label = self.name
        self.urdf_label = self.name

        # Synthesize in-memory Wiring container if footprints or nets were registered
        from model.wiring import Wiring

        if self.wiring is None and (self.footprints or self.nets):
            self.wiring = Wiring.from_models(
                footprints=self.footprints,
                nets=self.nets,
                symbol_table=self.symbol_table,
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
        sheet_size: Union[SheetSize, str] = SheetSize.A4,
        omitted_silkscreen_designators: Optional[Sequence[str]] = None,
        design_rules: Optional[Union[PCBDesignRulesModel, Dict[str, Any]]] = None,
        net_classes: Optional[Sequence[Union[NetClassModel, Dict[str, Any]]]] = None,
        flex_zones: Optional[Sequence[Union[FlexZoneModel, Dict[str, Any]]]] = None,
        obstacles: Optional[Sequence[Union[PCBObstacleModel, Dict[str, Any]]]] = None,
        schematic_sheets: Optional[Sequence[Union[SchematicSheetModel, Dict[str, Any]]]] = None,
        assembly_test: Optional[Union[AssemblyTestModel, Dict[str, Any]]] = None,
        stackup: Optional[Union[BuildStackup, StackupModel]] = None,
        capacitive_sensors: Optional[Sequence[CapacitiveElectrodeModel]] = None,
        outline_polygon: Optional[Sequence[Tuple[float, float]]] = None,
        coverlay_color: Optional[str] = "black",
        mode: Any = None,
    ) -> None:
        """Initialize flexible PCB context with typed flex_type."""
        super().__init__(
            name=name,
            board_type=BoardType.FLEX,
            shape_ref=shape_ref,
            revision=revision,
            sheet_size=sheet_size,
            omitted_silkscreen_designators=omitted_silkscreen_designators,
            design_rules=design_rules,
            net_classes=net_classes,
            flex_zones=flex_zones,
            obstacles=obstacles,
            schematic_sheets=schematic_sheets,
            assembly_test=assembly_test,
            stackup=stackup,
            capacitive_sensors=capacitive_sensors,
            outline_polygon=outline_polygon,
            coverlay_color=coverlay_color,
            mode=mode,
        )
        self.flex_type: FlexType = FlexType(flex_type) if isinstance(flex_type, str) else flex_type

    def to_pcb_config(self) -> PCBConfig:
        """Construct strongly-typed PCBConfig including flex_type metadata."""
        cfg = super().to_pcb_config()
        return cfg.model_copy(update={"flex_type": self.flex_type, "coverlay_color": self.coverlay_color})
