"""build123d context managers and primitives for PCB simulated test steps and flying probe testing."""

from contextvars import ContextVar, Token
from typing import Any, List, Optional, Sequence, Tuple, Union

from model.pcb import AssemblyTestStepModel
from model.wiring import PinRef

_current_test_steps: ContextVar[Optional["BuildTestSteps"]] = ContextVar("_current_test_steps", default=None)


class BuildTestSteps:
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

    def __enter__(self) -> "BuildTestSteps":
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

    @classmethod
    def _get_context(cls) -> Optional["BuildTestSteps"]:
        """Retrieve active test steps builder context if present."""
        return _current_test_steps.get()

    def add(self, item: Union[AssemblyTestStepModel, Sequence[AssemblyTestStepModel]]) -> None:
        """Append one or more test step models."""
        if isinstance(item, AssemblyTestStepModel):
            self.steps.append(item)
        else:
            self.steps.extend(item)


class TestStep:
    """Declarative assembly or flying probe test step primitive evaluated inside a BuildTestSteps context."""

    __test__ = False

    def __init__(
        self,
        step_id: str,
        description: str,
        test_type: str = "continuity",
        net_name: Optional[str] = None,
        pad_a: Optional[Union[Tuple[float, float], PinRef, Any]] = None,
        pad_b: Optional[Union[Tuple[float, float], PinRef, Any]] = None,
        nominal: Optional[float] = None,
        tolerance_pct: Optional[float] = 10.0,
        unit: str = "ohm",
        stimulus: Optional[str] = None,
        measured: Optional[float] = None,
        pad_a_mm: Optional[Tuple[float, float]] = None,
        pad_b_mm: Optional[Tuple[float, float]] = None,
        subassembly: Optional[str] = None,
    ) -> None:
        """Define an automated test fixture step."""
        pad_a = pad_a or pad_a_mm
        pad_b = pad_b or pad_b_mm
        ctx = BuildTestSteps._get_context()
        resolved_sub = subassembly or (ctx.subassembly if ctx else None)

        # Resolve pad coordinates
        def _resolve_coord(p: Any) -> Optional[Tuple[float, float]]:
            if p is None:
                return None
            if isinstance(p, PinRef):
                return (p.x, p.y)
            if hasattr(p, "pos"):
                return tuple(p.pos)
            if isinstance(p, (tuple, list)) and len(p) >= 2:
                return (round(float(p[0]), 4), round(float(p[1]), 4))
            return None

        pt_a = _resolve_coord(pad_a)
        pt_b = _resolve_coord(pad_b)

        self.model = AssemblyTestStepModel(
            step_id=step_id,
            subassembly=resolved_sub,
            description=description,
            test_type=test_type,
            net_name=net_name or "",
            pad_a_mm=pt_a,
            pad_b_mm=pt_b,
            nominal=nominal,
            expected_nominal=nominal,
            tolerance_pct=tolerance_pct,
            unit=unit,
            stimulus=stimulus,
            measured=measured,
        )

        if ctx:
            ctx.add(self.model)
