"""build123d context managers and primitives for PCB simulated test steps and flying probe testing."""

from contextvars import ContextVar, Token
from typing import Any, List, Optional, Sequence, Tuple, Union

from model.pcb import AssemblyTestModel, AssemblyTestStepModel
from model.wiring import PinRef

_current_assembly_tests: ContextVar[Optional["BuildAssemblyTests"]] = ContextVar(
    "_current_assembly_tests", default=None
)


class BuildAssemblyTests:
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

    def __enter__(self) -> "BuildAssemblyTests":
        """Enter test steps builder context."""
        self._token = _current_assembly_tests.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit test steps builder context and attach to active BuildPcb."""
        if self._token is not None:
            _current_assembly_tests.reset(self._token)
            self._token = None

        from provider.pcb.board import BuildPcb

        active_pcb = BuildPcb.current()
        if active_pcb is not None:
            active_pcb.test_steps.extend(self.steps)
            if getattr(active_pcb, "assembly_test", None) is None:
                active_pcb.assembly_test = AssemblyTestModel(
                    instructions=list(active_pcb.test_steps),
                    test_fixture=self.test_fixture,
                    pass_criteria=self.pass_criteria,
                )

    @classmethod
    def current(cls) -> Optional["BuildAssemblyTests"]:
        """Retrieve active test steps builder context if present."""
        return _current_assembly_tests.get()

    @classmethod
    def _get_context(cls) -> Optional["BuildAssemblyTests"]:
        """Retrieve active test steps builder context if present."""
        return _current_assembly_tests.get()

    def add(
        self,
        item: Union[
            AssemblyTestModel,
            AssemblyTestStepModel,
            Sequence[Union[AssemblyTestModel, AssemblyTestStepModel]],
        ],
    ) -> None:
        """Append one or more test step models or full assembly test plan."""
        if isinstance(item, AssemblyTestModel):
            self.test_fixture = item.test_fixture
            self.pass_criteria = item.pass_criteria
            self.steps.extend(item.instructions)
        elif isinstance(item, AssemblyTestStepModel):
            self.steps.append(item)
        elif isinstance(item, (list, tuple)):
            for step in item:
                self.add(step)


class TestStep:
    """Declarative assembly or flying probe test step primitive evaluated inside a BuildAssemblyTests context."""

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
        ctx = BuildAssemblyTests.current()
        resolved_sub = subassembly or (ctx.subassembly if ctx else None) or name

        resolved_nominal = nominal if nominal is not None else expected_nominal

        # Extract net name string from Net handle or name argument
        parsed_net: Optional[str] = None
        if net_name is not None:
            parsed_net = net_name.name if hasattr(net_name, "name") else str(net_name)
        elif net_or_points is not None:
            if isinstance(net_or_points, str):
                parsed_net = net_or_points
            elif hasattr(net_or_points, "name"):
                parsed_net = str(net_or_points.name)

        # Extract 2D coordinate points from PinRef or tuple
        pt_a: Optional[Tuple[float, float]] = None
        if isinstance(pad_a, PinRef):
            pt_a = pad_a.position_2d
        elif isinstance(pad_a, (tuple, list)) and len(pad_a) >= 2:
            pt_a = (float(pad_a[0]), float(pad_a[1]))

        pt_b: Optional[Tuple[float, float]] = None
        if isinstance(pad_b, PinRef):
            pt_b = pad_b.position_2d
        elif isinstance(pad_b, (tuple, list)) and len(pad_b) >= 2:
            pt_b = (float(pad_b[0]), float(pad_b[1]))

        net_points_list: List[str] = []
        if isinstance(net_or_points, (list, tuple)):
            for p in net_or_points:
                if hasattr(p, "name"):
                    net_points_list.append(str(p.name))
                else:
                    net_points_list.append(str(p))
        elif parsed_net is not None:
            net_points_list = [parsed_net]

        self.model = AssemblyTestStepModel(
            step_id=step_id,
            description=description,
            test_type=test_type,
            net_or_points=net_points_list,
            pad_a_mm=pt_a,
            pad_b_mm=pt_b,
            expected_nominal=resolved_nominal,
            tolerance_pct=tolerance_pct or 10.0,
            unit=unit,
            stimulus=stimulus,
            measured_value=measured,
            subassembly=resolved_sub,
        )

        if ctx is not None:
            ctx.add(self.model)

    def __repr__(self) -> str:
        """Return formatted string representation of test step."""
        return f"<TestStep {self.model.step_id}: {self.model.test_type} ({self.model.description})>"
