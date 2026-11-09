"""build123d context manager and primitives for declarative PCB netlists and electrical wiring."""

from contextvars import ContextVar, Token
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from model.pcb import DifferentialPairModel
from model.wiring import NetModel, PinRef

_current_build_wiring: ContextVar[Optional["BuildWiring"]] = ContextVar("_current_build_wiring", default=None)


class BuildWiring:
    """Context manager for declarative PCB netlists and multi-block wiring definitions."""

    def __init__(self, name: Optional[str] = None) -> None:
        """Initialize wiring builder context block.

        Args:
            name: Block identifier (e.g. 'power_distribution', 'mcu_signals', 'analog').
        """
        self.name = name or "wiring"
        self.nets: List[NetModel] = []
        self.diff_pairs: List[DifferentialPairModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildWiring":
        """Enter wiring builder context."""
        self._token = _current_build_wiring.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit wiring context and merge declared nets into active BuildPcb."""
        if self._token is not None:
            try:
                _current_build_wiring.reset(self._token)
            except ValueError:
                _current_build_wiring.set(None)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            # Merge nets into active PCB netlist
            for net in self.nets:
                existing = next((n for n in active_pcb.nets if n.name == net.name), None)
                if existing is not None:
                    # Merge pins without duplicates
                    for p in net.pins:
                        if p not in existing.pins:
                            existing.pins.append(p)
                    existing.pin_names.update(net.pin_names)
                    if net.path and not existing.path:
                        existing.path = list(net.path)
                    if net.priority is not None and existing.priority is None:
                        existing.priority = net.priority
                else:
                    active_pcb.nets.append(net.model_copy(deep=True))

            # Update connected_nets on symbol table entries
            for net in active_pcb.nets:
                for comp_name, _ in net.pins:
                    if comp_name in active_pcb.symbol_table:
                        sym = active_pcb.symbol_table[comp_name]
                        if net.name not in sym.connected_nets:
                            sym.connected_nets.append(net.name)

    @classmethod
    def current(cls) -> Optional["BuildWiring"]:
        """Retrieve active wiring builder context if present."""
        return _current_build_wiring.get()

    @classmethod
    def _get_context(cls) -> Optional["BuildWiring"]:
        """Retrieve active wiring builder context if present."""
        return _current_build_wiring.get()

    def add(self, item: Any) -> None:
        """Add nets from a Wiring instance, NetModel, or sequence of NetModels."""
        from model.wiring import Wiring

        if isinstance(item, Wiring):
            for net in item.nets:
                self.add_net(
                    name=net.name,
                    pins=net.pins,
                    pin_names=net.pin_names,
                    color=net.color,
                    offset=net.offset,
                    path=net.path,
                    priority=net.priority,
                )
            from provider.pcb.board import BuildPcb

            active_pcb = BuildPcb.current()
            if active_pcb is not None:
                for fp in item.footprints:
                    if fp not in active_pcb.footprints:
                        active_pcb.footprints.append(fp)
                if hasattr(item, "symbol_table") and item.symbol_table:
                    active_pcb.symbol_table.update(item.symbol_table)
        elif isinstance(item, NetModel):
            self.add_net(
                name=item.name,
                pins=item.pins,
                pin_names=item.pin_names,
                color=item.color,
                offset=item.offset,
                path=item.path,
                priority=item.priority,
            )
        elif isinstance(item, (list, tuple)):
            for n in item:
                self.add(n)

    def add_net(
        self,
        name: str,
        pins: Sequence[Tuple[str, str]],
        pin_names: Optional[Dict[Tuple[str, str], str]] = None,
        color: str = "green",
        offset: Tuple[float, float] = (0.0, 0.0),
        path: Optional[Sequence[Tuple[float, float, float]]] = None,
        priority: Optional[int] = None,
    ) -> NetModel:
        """Add or merge a net into this wiring context."""
        existing = next((n for n in self.nets if n.name == name), None)
        if existing is not None:
            for p in pins:
                if p not in existing.pins:
                    existing.pins.append(p)
            if pin_names:
                existing.pin_names.update(pin_names)
            if path and not existing.path:
                existing.path = list(path)
            if priority is not None:
                existing.priority = priority
            if color != "green" and existing.color == "green":
                existing.color = color
            return existing

        net = NetModel(
            name=name,
            color=color,
            pins=list(pins),
            pin_names=dict(pin_names or {}),
            offset=offset,
            path=[tuple(pt) for pt in (path or [])],
            priority=priority,
        )
        self.nets.append(net)
        return net


class Net:
    """Declarative electrical net primitive evaluated inside a BuildWiring context."""

    def __init__(
        self,
        name: str,
        pins: Sequence[Union[PinRef, Tuple[str, Any], Dict[str, Any]]],
        color: str = "green",
        offset: Tuple[float, float] = (0.0, 0.0),
        path: Optional[Sequence[Tuple[float, float, float]]] = None,
        priority: Optional[int] = None,
    ) -> None:
        """Declare a multi-point electrical net."""
        ctx = BuildWiring._get_context()
        self.name = name
        self.color = color

        parsed_pins: List[Tuple[str, str]] = []
        pin_names: Dict[Tuple[str, str], str] = {}

        for p in pins:
            if isinstance(p, PinRef):
                tup = p.as_tuple()
                parsed_pins.append(tup)
                func_name = p.pin_name or p.name
                pin_names[tup] = str(func_name)
            elif isinstance(p, (tuple, list)):
                if len(p) == 2:
                    comp, pin_num = str(p[0]).strip(), str(p[1]).strip()
                    parsed_pins.append((comp, pin_num))
                elif len(p) >= 3:
                    comp, pin_num, pin_func = str(p[0]).strip(), str(p[1]).strip(), str(p[2]).strip()
                    parsed_pins.append((comp, pin_num))
                    pin_names[(comp, pin_num)] = pin_func
            elif isinstance(p, dict):
                comp = str(p.get("component") or p.get("comp", "")).strip()
                pin_num = str(p.get("pin") or p.get("number", "")).strip()
                parsed_pins.append((comp, pin_num))
                func_name = p.get("pin_name") or p.get("name") or p.get("label")
                if func_name:
                    pin_names[(comp, pin_num)] = str(func_name).strip()

        if ctx is not None:
            self.model = ctx.add_net(
                name=name,
                pins=parsed_pins,
                pin_names=pin_names,
                color=color,
                offset=offset,
                path=path,
                priority=priority,
            )
        else:
            self.model = NetModel(
                name=name,
                color=color,
                pins=parsed_pins,
                pin_names=pin_names,
                offset=offset,
                path=[tuple(pt) for pt in (path or [])],
                priority=priority,
            )


class DiffPair:
    """Declarative high-speed differential signal pair (positive and negative lines)."""

    def __init__(
        self,
        name: str,
        pos: Optional[Sequence[Union[PinRef, Tuple[str, Any]]]] = None,
        neg: Optional[Sequence[Union[PinRef, Tuple[str, Any]]]] = None,
        pos_net: Optional[str] = None,
        neg_net: Optional[str] = None,
        color: str = "blue",
        target_impedance_ohms: float = 90.0,
        p_pins: Optional[Sequence[Union[PinRef, Tuple[str, Any]]]] = None,
        n_pins: Optional[Sequence[Union[PinRef, Tuple[str, Any]]]] = None,
    ) -> None:
        """Define a differential pair with matched positive and negative nets."""
        pos = pos if pos is not None else p_pins or []
        neg = neg if neg is not None else n_pins or []
        self.name = name
        self.pos_name = pos_net or (name if name.endswith(("_P", "_DP", "+")) else f"{name}_P")
        self.neg_name = neg_net or (name if name.endswith(("_N", "_DN", "-")) else f"{name}_N")

        pos_seq = (
            [pos]
            if isinstance(pos, (PinRef, tuple, list))
            and (isinstance(pos, PinRef) or (len(pos) == 2 and isinstance(pos[0], str)))
            else list(pos)
        )
        neg_seq = (
            [neg]
            if isinstance(neg, (PinRef, tuple, list))
            and (isinstance(neg, PinRef) or (len(neg) == 2 and isinstance(neg[0], str)))
            else list(neg)
        )

        self.net_pos = Net(self.pos_name, pins=pos_seq, color=color)
        self.net_neg = Net(self.neg_name, pins=neg_seq, color=color)

        self.diff_model = DifferentialPairModel(
            name=name,
            pos_net=self.pos_name,
            neg_net=self.neg_name,
            target_impedance_ohms=target_impedance_ohms,
        )

        ctx = BuildWiring._get_context()
        if ctx is not None:
            ctx.diff_pairs.append(self.diff_model)


class Bus:
    """Declarative bus primitive generating individual named signal nets from a dictionary of pins."""

    def __init__(
        self,
        name_prefix: str,
        signals: Optional[Mapping[str, Sequence[Union[PinRef, Tuple[str, Any]]]]] = None,
        color: str = "green",
        width: Optional[int] = None,
        pin_map: Optional[Mapping[Any, Sequence[Union[PinRef, Tuple[str, Any]]]]] = None,
    ) -> None:
        """Declare multiple related bus nets under a common prefix."""
        self.name_prefix = name_prefix
        self.nets: Dict[str, Net] = {}
        target_signals = signals if signals is not None else (pin_map or {})
        for sig_name, p_list in target_signals.items():
            net_name = (
                f"{name_prefix}_{sig_name}"
                if not name_prefix.endswith(("_", "[")) and not str(sig_name).isdigit()
                else f"{name_prefix}{sig_name}"
            )
            self.nets[str(sig_name)] = Net(net_name, pins=list(p_list), color=color)
