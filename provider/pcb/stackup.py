"""build123d context manager and primitives for declarative PCB physical stackup definition."""

from contextvars import ContextVar, Token
from typing import List, Optional, Sequence, Union

from build123d import Compound, Face, Pos, extrude

from model.pcb import LayerType, PCBMaterialsModel, StackupLayerModel, StackupModel

_current_stackup: ContextVar[Optional["BuildStackup"]] = ContextVar("_current_stackup", default=None)


class BuildStackup:
    """Context manager for declarative PCB multi-layer physical stackup construction."""

    def __init__(
        self,
        finish: str = "ENIG",
        soldermask_color: str = "green",
        silkscreen_color: str = "white",
        materials: Optional[PCBMaterialsModel] = None,
    ) -> None:
        """Initialize stackup builder context.

        Args:
            finish: Surface metallization finish ("ENIG", "HASL", "OSP", "Immersion_Silver").
            soldermask_color: Solder mask color ("green", "matte_black", "blue", etc.).
            silkscreen_color: Silkscreen legend ink color ("white", "black", "yellow").
            materials: Optional PCB materials catalog to resolve missing dielectric and foil specs.
        """
        self.finish = finish
        self.soldermask_color = soldermask_color
        self.silkscreen_color = silkscreen_color
        self.materials = materials or PCBMaterialsModel()
        self.layers: List[StackupLayerModel] = []
        self._token: Optional[Token] = None

    def __enter__(self) -> "BuildStackup":
        """Enter stackup context and register as active builder."""
        self._token = _current_stackup.set(self)
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Exit stackup context and restore previous builder."""
        if self._token is not None:
            _current_stackup.reset(self._token)
            self._token = None

    @classmethod
    def _get_context(cls) -> Optional["BuildStackup"]:
        """Retrieve active stackup builder context if present."""
        return _current_stackup.get()

    def add_layer(
        self,
        name: str,
        material: str = "copper",
        thickness_mm: float = 0.035,
        layer_type: Optional[Union[LayerType, str]] = None,
        dielectric_constant: Optional[float] = None,
        loss_tangent: Optional[float] = None,
    ) -> StackupLayerModel:
        """Add an individual physical stackup layer, resolving defaults from the materials library."""
        mat_spec = self.materials.get(material)
        resolved_layer_type = layer_type
        if resolved_layer_type is None:
            if mat_spec and mat_spec.layer_type is not None:
                resolved_layer_type = mat_spec.layer_type
            else:
                lower = name.lower()
                if "gnd" in lower:
                    resolved_layer_type = LayerType.GROUND
                elif "pwr" in lower:
                    resolved_layer_type = LayerType.POWER
                elif ".cu" in lower:
                    resolved_layer_type = LayerType.SIGNAL
                else:
                    resolved_layer_type = LayerType.DIELECTRIC

        if isinstance(resolved_layer_type, str):
            resolved_layer_type = LayerType(resolved_layer_type)

        resolved_er = dielectric_constant
        if resolved_er is None and mat_spec and mat_spec.dielectric_constant is not None:
            resolved_er = mat_spec.dielectric_constant

        resolved_loss = loss_tangent
        if resolved_loss is None and mat_spec and mat_spec.loss_tangent is not None:
            resolved_loss = mat_spec.loss_tangent

        layer_model = StackupLayerModel(
            name=name,
            layer_type=resolved_layer_type,
            thickness_mm=thickness_mm,
            material=material,
            dielectric_constant=resolved_er,
            loss_tangent=resolved_loss,
        )
        self.layers.append(layer_model)
        return layer_model

    def add(self, item: Union[StackupLayerModel, Sequence[StackupLayerModel]]) -> None:
        """Append one or more layer models directly."""
        if isinstance(item, StackupLayerModel):
            self.layers.append(item)
        else:
            self.layers.extend(item)

    @property
    def total_thickness_mm(self) -> float:
        """Calculate total physical thickness across all copper foils and dielectric layers."""
        return round(sum(layer.thickness_mm for layer in self.layers), 6)

    def to_model(self) -> StackupModel:
        """Convert collected layers into a validated Pydantic StackupModel."""
        return StackupModel(
            layers=list(self.layers),
            finish=self.finish,
            soldermask_color=self.soldermask_color,
            silkscreen_color=self.silkscreen_color,
        )

    def to_solid(self, outline_face: Face) -> Compound:
        """Extrude 2D outline face through each layer thickness, stacking layers along Z."""
        current_z = -self.total_thickness_mm / 2.0
        solids = []
        for layer in self.layers:
            layer_face = outline_face.locate(Pos(0, 0, current_z))
            layer_solid = extrude(layer_face, amount=layer.thickness_mm)
            solids.append(layer_solid)
            current_z += layer.thickness_mm
        return Compound(children=solids)


class StackupLayer:
    """Declarative stackup layer primitive evaluated inside a BuildStackup context."""

    def __init__(
        self,
        name: str,
        material: str = "copper",
        thickness_mm: float = 0.035,
        layer_type: Optional[Union[LayerType, str]] = None,
        dielectric_constant: Optional[float] = None,
        loss_tangent: Optional[float] = None,
    ) -> None:
        """Instantiate a stackup layer and register with active BuildStackup context."""
        self.name = name
        self.material = material
        self.thickness_mm = thickness_mm
        self.model: Optional[StackupLayerModel] = None

        ctx = BuildStackup._get_context()
        if ctx is not None:
            self.model = ctx.add_layer(
                name=name,
                material=material,
                thickness_mm=thickness_mm,
                layer_type=layer_type,
                dielectric_constant=dielectric_constant,
                loss_tangent=loss_tangent,
            )
