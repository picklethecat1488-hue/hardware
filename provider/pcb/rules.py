"""build123d context managers and primitives for PCB fabrication rules, net classes, flex zones, and obstacles."""

from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional, Sequence, Union

from model.pcb import (
    CapacitiveElectrodeModel,
    FlexZoneModel,
    NetClassModel,
    PCBDesignRulesModel,
    PCBObstacleModel,
)

_current_build_design_rules: ContextVar[Optional["BuildDesignRules"]] = ContextVar(
    "_current_build_design_rules", default=None
)
_current_build_net_classes: ContextVar[Optional["BuildNetClasses"]] = ContextVar(
    "_current_build_net_classes", default=None
)
_current_build_flex_zones: ContextVar[Optional["BuildFlexZones"]] = ContextVar(
    "_current_build_flex_zones", default=None
)
_current_build_obstacles: ContextVar[Optional["BuildObstacles"]] = ContextVar("_current_build_obstacles", default=None)
_current_build_capacitive_sensors: ContextVar[Optional["BuildCapacitiveSensors"]] = ContextVar(
    "_current_build_capacitive_sensors", default=None
)


class BuildDesignRules:
    """Context manager for declarative PCB fabrication rules and clearance constraints."""

    def __init__(self, rules: Optional[Union[PCBDesignRulesModel, Dict[str, Any]]] = None) -> None:
        """Initialize design rules context."""
        if isinstance(rules, PCBDesignRulesModel):
            self.rules: Optional[PCBDesignRulesModel] = rules
        elif isinstance(rules, dict):
            self.rules = PCBDesignRulesModel(**rules)
        else:
            self.rules = None
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildDesignRules":
        """Enter design rules context."""
        self._token = _current_build_design_rules.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit design rules context and attach to active BuildPcb."""
        if self._token is not None:
            _current_build_design_rules.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None and self.rules is not None:
            active_pcb.design_rules = self.rules

    @classmethod
    def current(cls) -> Optional["BuildDesignRules"]:
        """Return the active BuildDesignRules context if set."""
        return _current_build_design_rules.get()

    def add(self, rules: Union[PCBDesignRulesModel, Dict[str, Any]]) -> None:
        """Assign fabrication design rules."""
        if isinstance(rules, PCBDesignRulesModel):
            self.rules = rules
        elif isinstance(rules, dict):
            self.rules = PCBDesignRulesModel(**rules)


class BuildNetClasses:
    """Context manager for declarative high-speed, differential, and impedance net classes."""

    def __init__(self) -> None:
        """Initialize net classes context."""
        self.net_classes: List[NetClassModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildNetClasses":
        """Enter net classes context."""
        self._token = _current_build_net_classes.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit net classes context and attach to active BuildPcb."""
        if self._token is not None:
            _current_build_net_classes.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.net_classes.extend(self.net_classes)

    @classmethod
    def current(cls) -> Optional["BuildNetClasses"]:
        """Return the active BuildNetClasses context if set."""
        return _current_build_net_classes.get()

    def add(self, item: Union[NetClassModel, Sequence[NetClassModel], Dict[str, Any]]) -> None:
        """Append one or more net class specifications."""
        if isinstance(item, NetClassModel):
            self.net_classes.append(item)
        elif isinstance(item, dict):
            self.net_classes.append(NetClassModel(**item))
        elif isinstance(item, (list, tuple)):
            for nc in item:
                self.add(nc)


class BuildFlexZones:
    """Context manager for declarative rigid-flex flexible substrate zones."""

    def __init__(self) -> None:
        """Initialize flex zones context."""
        self.flex_zones: List[FlexZoneModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildFlexZones":
        """Enter flex zones context."""
        self._token = _current_build_flex_zones.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit flex zones context and attach to active BuildPcb."""
        if self._token is not None:
            _current_build_flex_zones.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.flex_zones.extend(self.flex_zones)

    @classmethod
    def current(cls) -> Optional["BuildFlexZones"]:
        """Return the active BuildFlexZones context if set."""
        return _current_build_flex_zones.get()

    def add(self, item: Union[FlexZoneModel, Sequence[FlexZoneModel], Dict[str, Any]]) -> None:
        """Append one or more flex zone specifications."""
        if isinstance(item, FlexZoneModel):
            self.flex_zones.append(item)
        elif isinstance(item, dict):
            self.flex_zones.append(FlexZoneModel(**item))
        elif isinstance(item, (list, tuple)):
            for fz in item:
                self.add(fz)


class BuildObstacles:
    """Context manager for declarative 3D keepout clearance obstacles on PCBs."""

    def __init__(self) -> None:
        """Initialize obstacles context."""
        self.obstacles: List[PCBObstacleModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildObstacles":
        """Enter obstacles context."""
        self._token = _current_build_obstacles.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit obstacles context and attach to active BuildPcb."""
        if self._token is not None:
            _current_build_obstacles.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.obstacles.extend(self.obstacles)

    @classmethod
    def current(cls) -> Optional["BuildObstacles"]:
        """Return the active BuildObstacles context if set."""
        return _current_build_obstacles.get()

    def add(self, item: Union[PCBObstacleModel, Sequence[PCBObstacleModel], Dict[str, Any]]) -> None:
        """Append one or more 3D clearance obstacle specifications."""
        if isinstance(item, PCBObstacleModel):
            self.obstacles.append(item)
        elif isinstance(item, dict):
            self.obstacles.append(PCBObstacleModel(**item))
        elif isinstance(item, (list, tuple)):
            for obs in item:
                self.add(obs)


class BuildCapacitiveSensors:
    """Context manager for declarative capacitive sensing electrode configurations."""

    def __init__(self) -> None:
        """Initialize capacitive sensors context."""
        self.capacitive_sensors: List[CapacitiveElectrodeModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildCapacitiveSensors":
        """Enter capacitive sensors context."""
        self._token = _current_build_capacitive_sensors.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit capacitive sensors context and attach to active BuildPcb."""
        if self._token is not None:
            _current_build_capacitive_sensors.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.capacitive_sensors.extend(self.capacitive_sensors)

    @classmethod
    def current(cls) -> Optional["BuildCapacitiveSensors"]:
        """Return the active BuildCapacitiveSensors context if set."""
        return _current_build_capacitive_sensors.get()

    def add(self, item: Union[CapacitiveElectrodeModel, Sequence[CapacitiveElectrodeModel], Dict[str, Any]]) -> None:
        """Append one or more capacitive electrode specifications."""
        if isinstance(item, CapacitiveElectrodeModel):
            self.capacitive_sensors.append(item)
        elif isinstance(item, dict):
            self.capacitive_sensors.append(CapacitiveElectrodeModel(**item))
        elif isinstance(item, (list, tuple)):
            for cs in item:
                self.add(cs)
