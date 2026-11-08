"""build123d context manager and primitives for declarative schematic sheets and metadata."""

from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional, Sequence, Union

from model.pcb import SchematicLayoutModel, SchematicSheetModel, SheetSize

_current_schematic_metadata: ContextVar[Optional["SchematicMetadata"]] = ContextVar(
    "_current_schematic_metadata", default=None
)


class SchematicMetadata:
    """Context manager for declarative schematic sheet organization nested inside BuildPcb."""

    def __init__(self, sheet_size: Union[SheetSize, str] = SheetSize.A4) -> None:
        """Initialize schematic metadata context."""
        self.sheet_size = SheetSize(sheet_size) if isinstance(sheet_size, str) else sheet_size
        self.sheets: List[SchematicSheetModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "SchematicMetadata":
        """Enter schematic metadata context."""
        self._token = _current_schematic_metadata.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit schematic metadata context and register sheets to active BuildPcb."""
        if self._token is not None:
            _current_schematic_metadata.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        pcb = BuildPcb.current()
        if pcb is not None:
            pcb.schematic_sheets.extend(self.sheets)
            pcb.sheet_size = self.sheet_size

    @classmethod
    def current(cls) -> Optional["SchematicMetadata"]:
        """Return active SchematicMetadata context if set."""
        return _current_schematic_metadata.get()

    def add(self, sheet: Union[SchematicSheetModel, Sequence[SchematicSheetModel]]) -> None:
        """Add one or more schematic sheet models."""
        if isinstance(sheet, SchematicSheetModel):
            self.sheets.append(sheet)
        else:
            self.sheets.extend(sheet)


class SchematicSheet:
    """Declarative schematic sheet primitive evaluated inside a SchematicMetadata context."""

    def __init__(
        self,
        title: str,
        description: str = "",
        components: Optional[Sequence[Union[str, Any]]] = None,
        pin_breakouts: Optional[Dict[Any, Sequence[str]]] = None,
        pin_sides: Optional[Dict[Any, Dict[str, str]]] = None,
        layout: Optional[Union[SchematicLayoutModel, Dict[str, Any]]] = None,
    ) -> None:
        """Define an individual schematic sheet with strongly typed properties.

        Args:
            title: Sheet title displayed in engineering title block.
            description: Functional description of circuitry on this sheet.
            components: List of component designators or ComponentInstance handles.
            pin_breakouts: Component -> subset of pin names to display on this sheet.
            pin_sides: Component -> {pin_name: 'left' | 'right'} pin placement overrides.
            layout: Layout grid dimensions and position overrides.
        """
        parsed_comps: List[str] = []
        for c in components or []:
            if hasattr(c, "name"):
                parsed_comps.append(str(c.name))
            else:
                parsed_comps.append(str(c))

        parsed_breakouts: Dict[str, List[str]] = {}
        for k, v in (pin_breakouts or {}).items():
            k_name = k.name if hasattr(k, "name") else str(k)
            parsed_breakouts[k_name] = [str(x) for x in v]

        parsed_sides: Dict[str, Dict[str, str]] = {}
        for k, v in (pin_sides or {}).items():
            k_name = k.name if hasattr(k, "name") else str(k)
            parsed_sides[k_name] = {str(pk): str(pv) for pk, pv in v.items()}

        if isinstance(layout, SchematicLayoutModel):
            parsed_layout = layout
        elif isinstance(layout, dict):
            parsed_layout = SchematicLayoutModel(**layout)
        else:
            parsed_layout = SchematicLayoutModel()

        self.model = SchematicSheetModel(
            title=title,
            description=description,
            components=parsed_comps,
            pin_breakouts=parsed_breakouts,
            pin_sides=parsed_sides,
            layout=parsed_layout,
        )

        ctx = SchematicMetadata.current()
        if ctx is not None:
            ctx.add(self.model)
