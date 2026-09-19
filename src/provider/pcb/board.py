"""build123d custom context manager for declarative PCB part modeling with integrated stackup and metadata."""

from contextvars import ContextVar, Token
from typing import Any, List, Optional, Union

from build123d import BuildPart
from build123d.build_common import operations_apply_to

from model.pcb import (
    BoardType,
    CopperRegionModel,
    MountingHoleModel,
    PCBConfig,
    SilkscreenTextModel,
    StackupModel,
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
        if "BuildFlexTail" not in builders:
            builders.append("BuildFlexTail")


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
        revision: str = "1.0",
        stackup: Optional[Union[BuildStackup, StackupModel]] = None,
        mode: Any = None,
    ) -> None:
        """Initialize PCB part builder context.

        Args:
            name: PCB identifier or subassembly name.
            board_type: Substrate construction ('rigid', 'flex', or 'rigid-flex').
            revision: Board revision identifier.
            stackup: Multi-layer stackup model or BuildStackup context.
            mode: Optional BuildMode for build123d part builder.
        """
        super().__init__(mode=mode)
        self.name = name
        self.board_type: BoardType = BoardType(board_type) if isinstance(board_type, str) else board_type
        self.revision = revision

        if isinstance(stackup, BuildStackup):
            self.stackup_model: Optional[StackupModel] = stackup.to_model()
        else:
            self.stackup_model = stackup

        self.mounting_holes: List[MountingHoleModel] = []
        self.silkscreen_texts: List[SilkscreenTextModel] = []
        self.traces: List[TraceSegmentModel] = []
        self.vias: List[ViaModel] = []
        self.copper_regions: List[CopperRegionModel] = []
        self.test_points: List[TestPointModel] = []
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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and attach metadata to the constructed CAD shape."""
        if self._token:
            _current_build_pcb.reset(self._token)
            self._token = None
        super().__exit__(exc_type, exc_val, exc_tb)

        # Attach metadata to the built part object and self for runtime discovery
        meta = self.to_pcb_config()
        self.pcb_metadata = meta
        if self.part is not None:
            setattr(self.part, "pcb_metadata", meta)

    def to_pcb_config(self) -> PCBConfig:
        """Construct strongly-typed PCBConfig from context metadata."""
        dims = None
        if self.part is not None:
            bb = getattr(self.part, "bounding_box", None)
            if callable(bb):
                bbox = bb()
                dims = (round(bbox.size.X, 4), round(bbox.size.Y, 4), round(self.thickness_mm, 4))

        return PCBConfig(
            name=self.name,
            board_type=self.board_type,
            revision=self.revision,
            dimensions_mm=dims,
            shape_ref=self.name,
            stackup=self.stackup_model,
            mounting_holes=list(self.mounting_holes),
            silkscreen_texts=list(self.silkscreen_texts),
            traces=list(self.traces),
            vias=list(self.vias),
            copper_regions=list(self.copper_regions),
            test_points=list(self.test_points),
        )

    @classmethod
    def current(cls) -> Optional["BuildPcb"]:
        """Return the active ambient BuildPcb context if set."""
        return _current_build_pcb.get()


class BuildFlexTail(BuildPcb):
    """Convenience context manager for flexible polyimide tail PCB subassemblies."""

    def __init__(
        self,
        name: str = "flex_tail",
        revision: str = "1.0",
        stackup: Optional[Union[BuildStackup, StackupModel]] = None,
        mode: Any = None,
    ) -> None:
        """Initialize flexible tail context."""
        super().__init__(name=name, board_type=BoardType.FLEX, revision=revision, stackup=stackup, mode=mode)
