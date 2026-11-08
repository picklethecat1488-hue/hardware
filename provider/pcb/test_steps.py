"""build123d context managers and primitives for PCB simulated test steps and flying probe testing."""

from contextvars import ContextVar, Token
from typing import Any, List, Optional, Sequence, Tuple, Union

from model.pcb import AssemblyTestModel, AssemblyTestStepModel
from model.wiring import PinRef

_current_test_steps: ContextVar[Optional["BuildTestSteps"]] = ContextVar("_current_test_steps", default=None)


class BuildAssemblyTestSteps:
    """Context manager for declarative PCB assembly and flying probe simulation test steps."""

    __test__ = False

    def __init__(
        self,
        test_fixture: str = "flying_probe",
        pass_criteria: str = "all_steps_within_tolerance",
        subassembly: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize test steps builder context."""
        self.test_fixture = test_fixture
        self.pass_criteria = pass_criteria
        self.subassembly = subassembly or name
        self.steps: List[AssemblyTestStepModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildAssemblyTestSteps":
        """Enter test steps builder context."""
        self._token = _current_test_steps.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit test steps builder context and attach to active BuildPcb."""
        if self._token is not None:
            _current_test_steps.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.test_steps.extend(self.steps)
            active_pcb.assembly_test = AssemblyTestModel(
                instructions=list(active_pcb.test_steps),
                test_fixture=self.test_fixture,
                pass_criteria=self.pass_criteria,
            )

    @classmethod
    def _get_context(cls) -> Optional["BuildAssemblyTestSteps"]:
        """Retrieve active test steps builder context if present."""
        return _current_test_steps.get()

    def add(self, item: Union[AssemblyTestStepModel, Sequence[AssemblyTestStepModel]]) -> None:
        """Append one or more test step models."""
        if isinstance(item, AssemblyTestStepModel):
            self.steps.append(item)
        else:
            self.steps.extend(item)


BuildTestSteps = BuildAssemblyTestSteps
AssemblyTestMetadata = BuildAssemblyTestSteps


class TestStep:
    """Declarative assembly or flying probe test step primitive evaluated inside a BuildTestSteps context."""

    __test__ = False

    def __init__(
        self,
        step_id: str,
        description: str,
        test_type: str = "continuity",
        net_name: Optional[Union[str, Any]] = None,
        net_or_points: Optional[Union[str, Any, Sequence[Any]]] = None,
        pad_a: Optional[Union[Tuple[float, float], PinRef, Any]] = None,
        pad_b: Optional[Union[Tuple[float, float], PinRef, Any]] = None,
        nominal: Optional[float] = None,
        expected_nominal: Optional[float] = None,
        tolerance_pct: Optional[float] = 10.0,
        unit: str = "ohm",
        stimulus: Optional[str] = None,
        measured: Optional[float] = None,
        pad_a_mm: Optional[Tuple[float, float]] = None,
        pad_b_mm: Optional[Tuple[float, float]] = None,
        subassembly: Optional[str] = None,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Define an automated test fixture step with type-safe net and pin references."""
        pad_a = pad_a if pad_a is not None else pad_a_mm
        pad_b = pad_b if pad_b is not None else pad_b_mm
        ctx = BuildAssemblyTestSteps._get_context()
        from provider.pcb.board import BuildPcb

        current_pcb = BuildPcb.current()
        resolved_sub = (
            subassembly or name or (ctx.subassembly if ctx else None) or (current_pcb.name if current_pcb else None)
        )

        resolved_net_name = net_name
        resolved_net_points: List[str] = []
        if hasattr(net_name, "name"):
            resolved_net_name = getattr(net_name, "name")

        if net_or_points is not None:
            if isinstance(net_or_points, str):
                resolved_net_points = [net_or_points]
                if not resolved_net_name:
                    resolved_net_name = net_or_points
            elif hasattr(net_or_points, "name"):
                resolved_net_points = [str(getattr(net_or_points, "name"))]
                if not resolved_net_name:
                    resolved_net_name = str(getattr(net_or_points, "name"))
            elif isinstance(net_or_points, (list, tuple)):
                for np in net_or_points:
                    if hasattr(np, "name"):
                        resolved_net_points.append(str(getattr(np, "name")))
                    elif isinstance(np, PinRef):
                        resolved_net_points.append(f"{np.component_name}.{np.name}")
                    else:
                        resolved_net_points.append(str(np))
                if not resolved_net_name and resolved_net_points:
                    resolved_net_name = resolved_net_points[0]

        if resolved_net_name and not resolved_net_points:
            resolved_net_points = [str(resolved_net_name)]

        # Resolve pad coordinates
        def _resolve_coord(p: Any) -> Optional[Tuple[float, float]]:
            if p is None:
                return None
            if isinstance(p, PinRef):
                return (round(p.x, 4), round(p.y, 4))
            if hasattr(p, "pos"):
                pos = getattr(p, "pos")
                return (round(float(pos[0]), 4), round(float(pos[1]), 4))
            if isinstance(p, (tuple, list)) and len(p) >= 2:
                return (round(float(p[0]), 4), round(float(p[1]), 4))
            return None

        pt_a = _resolve_coord(pad_a)
        pt_b = _resolve_coord(pad_b)
        val_nom = nominal if nominal is not None else expected_nominal

        self.model = AssemblyTestStepModel(
            step_id=step_id,
            subassembly=resolved_sub,
            description=description,
            test_type=test_type,
            net_name=str(resolved_net_name or ""),
            net_or_points=resolved_net_points,
            pad_a_mm=pt_a,
            pad_b_mm=pt_b,
            nominal=val_nom,
            expected_nominal=val_nom,
            tolerance_pct=tolerance_pct,
            unit=unit,
            stimulus=stimulus,
            measured=measured,
        )

        if ctx:
            ctx.add(self.model)
