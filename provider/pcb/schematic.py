"""build123d context manager and primitives for declarative schematic sheets and metadata."""

from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional, Sequence, Union

from model.pcb import PinSideDef, SchematicLayoutModel, SchematicSheetModel, SheetSize, SymbolTableEntry
from model.wiring import FootprintModel

_current_schematic_config: ContextVar[Optional["SchematicConfig"]] = ContextVar(
    "_current_schematic_config", default=None
)
_current_build_schematic: ContextVar[Optional["BuildSchematic"]] = ContextVar("_current_build_schematic", default=None)


class SchematicConfig:
    """Container and configuration for schematic drawing sheets and sheet size standards."""

    def __init__(self, sheet_size: Union[SheetSize, str] = SheetSize.A4) -> None:
        """Initialize schematic configuration container."""
        self.sheet_size = SheetSize(sheet_size) if isinstance(sheet_size, str) else sheet_size
        self.sheets: List[SchematicSheetModel] = []
        self.components: List[FootprintModel] = []
        self.symbol_table: Dict[str, SymbolTableEntry] = {}
        self._token: Optional[Token] = None

    def clear_components(self) -> None:
        """Clear dynamically tracked components, symbol tables, and sheet component mappings."""
        self.components.clear()
        self.symbol_table.clear()
        for s in self.sheets:
            s.components.clear()
            s.pin_sides.clear()
            s.pin_breakouts.clear()

    def __enter__(self) -> "SchematicConfig":
        """Enter schematic configuration context."""
        self.clear_components()
        token = _current_schematic_config.set(self)
        if not hasattr(self, "_tokens"):
            self._tokens = []
        self._tokens.append(token)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit schematic configuration context."""
        if hasattr(self, "_tokens") and self._tokens:
            token = self._tokens.pop()
            try:
                _current_schematic_config.reset(token)
            except ValueError:
                _current_schematic_config.set(None)
        elif self._token is not None:
            try:
                _current_schematic_config.reset(self._token)
            except ValueError:
                _current_schematic_config.set(None)
            self._token = None

    @classmethod
    def current(cls) -> Optional["SchematicConfig"]:
        """Return active SchematicConfig context if set."""
        return _current_schematic_config.get()

    def add(
        self,
        sheet: Union["SchematicSheet", SchematicSheetModel, Sequence[Union["SchematicSheet", SchematicSheetModel]]],
    ) -> Union[SchematicSheetModel, List[SchematicSheetModel]]:
        """Add one or more schematic sheets to this configuration."""
        if isinstance(sheet, (list, tuple)):
            res = []
            for s in sheet:
                res.append(self.add(s))
            return res

        model = sheet.model if hasattr(sheet, "model") else sheet
        if model not in self.sheets:
            self.sheets.append(model)
        return model

    def sheet(
        self,
        title: str,
        description: str = "",
        layout: Optional[Union[SchematicLayoutModel, Dict[str, Any]]] = None,
    ) -> "SchematicSheet":
        """Declare and register a new SchematicSheet under this configuration."""
        sh = SchematicSheet(title=title, description=description, layout=layout, config=self)
        return sh

    def get(self, title: str, default: Optional[SchematicSheetModel] = None) -> Optional[SchematicSheetModel]:
        """Find schematic sheet model by exact or case-insensitive title."""
        for s in self.sheets:
            if s.title == title:
                return s
        clean_title = title.strip().lower()
        for s in self.sheets:
            if s.title.strip().lower() == clean_title:
                return s
        return default

    def __getitem__(self, title: str) -> SchematicSheetModel:
        """Access schematic sheet model by title with dictionary indexing."""
        res = self.get(title)
        if res is None:
            available = [s.title for s in self.sheets]
            raise KeyError(f"Schematic sheet '{title}' not found in SchematicConfig. Available sheets: {available}")
        return res

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to sheets by normalized title slug."""
        clean_name = name.lower().replace("_", "")
        for s in self.sheets:
            if s.title.lower().replace(" ", "").replace("_", "").replace("-", "") == clean_name:
                return s
        raise AttributeError(f"'SchematicConfig' object has no attribute or sheet named '{name}'")


class BuildSchematic:
    """Context manager for declarative schematic sheet organization nested inside BuildPcb."""

    def __init__(self, sheet_size: Optional[Union[SheetSize, str]] = None) -> None:
        """Initialize schematic builder context."""
        self.sheet_size = SheetSize(sheet_size) if isinstance(sheet_size, str) else sheet_size
        self.sheets: List[SchematicSheetModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildSchematic":
        """Enter schematic builder context."""
        self._token = _current_build_schematic.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit schematic builder context and register sheets to active BuildPcb."""
        if self._token is not None:
            try:
                _current_build_schematic.reset(self._token)
            except ValueError:
                _current_build_schematic.set(None)
            self._token = None

        from provider.pcb.board import BuildPcb

        pcb = BuildPcb.current()
        if pcb is not None:
            for s in self.sheets:
                if s not in pcb.schematic_sheets and not any(
                    existing.title == s.title for existing in pcb.schematic_sheets
                ):
                    pcb.schematic_sheets.append(s)
            if self.sheet_size is not None:
                pcb.sheet_size = self.sheet_size

    @classmethod
    def current(cls) -> Optional["BuildSchematic"]:
        """Return active BuildSchematic context if set."""
        return _current_build_schematic.get()

    @property
    def config(self) -> SchematicConfig:
        """Return a SchematicConfig containing this builder's sheets."""
        cfg = SchematicConfig(sheet_size=self.sheet_size or SheetSize.A4)
        cfg.sheets = list(self.sheets)
        return cfg

    def add(
        self,
        item: Union[
            SchematicConfig,
            "SchematicSheet",
            SchematicSheetModel,
            Sequence[Union[SchematicConfig, "SchematicSheet", SchematicSheetModel]],
        ],
    ) -> None:
        """Add schematic configuration, sheets, or sheet models."""
        if isinstance(item, SchematicConfig):
            for s in item.sheets:
                if s not in self.sheets and not any(existing.title == s.title for existing in self.sheets):
                    self.sheets.append(s)
            if item.sheet_size is not None:
                self.sheet_size = item.sheet_size
        elif isinstance(item, SchematicSheetModel):
            if item not in self.sheets and not any(existing.title == item.title for existing in self.sheets):
                self.sheets.append(item)
        elif hasattr(item, "model") and isinstance(item.model, SchematicSheetModel):
            if item.model not in self.sheets and not any(
                existing.title == item.model.title for existing in self.sheets
            ):
                self.sheets.append(item.model)
        elif isinstance(item, (list, tuple)):
            for s in item:
                self.add(s)


class SchematicSheet:
    """Declarative schematic sheet primitive evaluated inside a SchematicConfig or BuildSchematic context."""

    def __init__(
        self,
        title: str,
        description: str = "",
        components: Optional[Sequence[Union[str, Any]]] = None,
        pin_breakouts: Optional[Dict[Any, Sequence[str]]] = None,
        pin_sides: Optional[Dict[Any, Union[PinSideDef, Dict[str, str]]]] = None,
        layout: Optional[Union[SchematicLayoutModel, Dict[str, Any]]] = None,
        config: Optional[SchematicConfig] = None,
    ) -> None:
        """Define an individual schematic sheet with strongly typed properties.

        Args:
            title: Sheet title displayed in engineering title block.
            description: Functional description of circuitry on this sheet.
            components: Optional list of component designators or ComponentInstance handles.
            pin_breakouts: Optional Component -> subset of pin names to display on this sheet.
            pin_sides: Optional Component -> PinSideDef or {pin_name: 'left' | 'right'} pin overrides.
            layout: Optional layout grid dimensions and position overrides.
            config: Optional SchematicConfig container to register into directly.
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
            if isinstance(v, PinSideDef):
                parsed_sides[k_name] = {pk: pv.value for pk, pv in v.to_side_map().items()}
                if k_name not in parsed_breakouts:
                    parsed_breakouts[k_name] = v.to_breakout_list()
            else:
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

        if config is not None:
            config.add(self.model)
        else:
            sched_ctx = BuildSchematic.current()
            if sched_ctx is not None:
                sched_ctx.add(self.model)
            else:
                cfg_ctx = SchematicConfig.current()
                if cfg_ctx is not None:
                    cfg_ctx.add(self.model)

    @property
    def title(self) -> str:
        """Sheet title."""
        return self.model.title

    @property
    def description(self) -> str:
        """Functional description."""
        return self.model.description

    @property
    def components(self) -> List[str]:
        """Component designators on this sheet."""
        return self.model.components

    @property
    def pin_breakouts(self) -> Dict[str, List[str]]:
        """Component pin breakout lists."""
        return self.model.pin_breakouts

    @property
    def pin_sides(self) -> Dict[str, Dict[str, str]]:
        """Component pin placement overrides."""
        return self.model.pin_sides

    def add_component(
        self,
        name: str,
        pin_breakout: Optional[Sequence[str]] = None,
        pin_sides: Optional[Union[PinSideDef, Dict[str, Any]]] = None,
    ) -> None:
        """Add component designator and pin configuration to this sheet."""
        self.model.add_component(name=name, pin_breakout=pin_breakout, pin_sides=pin_sides)

    def __repr__(self) -> str:
        """Return formatted string representation of schematic sheet."""
        return f"<SchematicSheet '{self.title}' ({len(self.components)} components)>"
