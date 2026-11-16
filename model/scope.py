"""Data models for interactive CAD/PCB Scope Workstation."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScopeTargetModel(BaseModel):
    """Target within a project available for inspection."""

    name: str = Field(description="Target name (e.g. bowl, carrier_board, pump_cover)")
    subassemblies: List[str] = Field(default_factory=list, description="Subassemblies available for target")
    modes: List[str] = Field(default_factory=list, description="Supported modes: CAD, PCB, SIMULATE, DIAGRAM")


class ScopeProjectModel(BaseModel):
    """Discoverable project containing inspectable targets."""

    name: str = Field(description="Project name (e.g. carrier_board, cat_fountain)")
    targets: List[ScopeTargetModel] = Field(default_factory=list, description="Available targets")


class ScopeAnnotationModel(BaseModel):
    """3D spatial user annotation pin with notes."""

    id: int = Field(description="Unique annotation index")
    x: float = Field(description="X coordinate in 3D space")
    y: float = Field(description="Y coordinate in 3D space")
    z: float = Field(description="Z coordinate in 3D space")
    text: str = Field(description="Annotation text note")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp")


class ScopeMarkupModel(BaseModel):
    """2D diagram markup drawing (pen, rect, circle, line, text)."""

    type: str = Field(description="Markup tool type: pen, rect, circle, line, arrow, text")
    color: str = Field(default="#ff3333", description="Hex color")
    stroke_width: int = Field(default=2, description="Line stroke width")
    data: Dict[str, Any] = Field(default_factory=dict, description="Geometry details (points, rect bounds, text)")


class ScopeTargetBugRequest(BaseModel):
    """Bug report submission payload from Target Bug button."""

    project: str = Field(description="Project name")
    target: str = Field(description="Target name")
    subassembly: Optional[str] = Field(default=None, description="Active subassembly")
    mode: str = Field(default="CAD", description="Active visualization mode")
    title: str = Field(description="Bug title")
    severity: str = Field(default="MEDIUM", description="Bug severity (CRITICAL, HIGH, MEDIUM, LOW, NIT)")
    category: str = Field(default="CAD", description="Defect category (CAD, PCB, SIMULATION, FABRICATION)")
    description: str = Field(description="Detailed defect description")
    reproduction_steps: str = Field(description="Reproduction command/steps")
    image_base64: str = Field(description="Composited PNG screenshot data URL or base64")
    annotations: List[ScopeAnnotationModel] = Field(default_factory=list, description="Active 3D spatial annotations")
    markups: List[ScopeMarkupModel] = Field(default_factory=list, description="Active 2D markups")
