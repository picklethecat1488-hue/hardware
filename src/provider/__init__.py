"""Models package root."""

import warnings
import os
from pathlib import Path

# Load .env file into os.environ before JAX or other packages are imported
env_file = Path(__file__).resolve().parents[2] / ".env"
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k not in os.environ:
                    os.environ[k] = v
                if k.startswith("APP_"):
                    unprefixed = k[4:]
                    if unprefixed not in os.environ:
                        os.environ[unprefixed] = v

from .utils import (
    discover_provider,
    load_manifest,
    get_rgba_color,
    initialize_jax_environment,
)

# Initialize JAX environment configuration deterministically
initialize_jax_environment()

import OCP.TopoDS  # type: ignore

# Monkey-patch TopoDS_Shape to resolve Pydantic validation errors.
# Pydantic 2 probes for a HashCode method when validating OCP-wrapped types.
if not hasattr(OCP.TopoDS.TopoDS_Shape, "HashCode"):
    OCP.TopoDS.TopoDS_Shape.HashCode = lambda self, upper: id(self) % upper  # type: ignore

from .provider import Provider, URDFMetadata, URDFBoundary
from .types import (
    Mode,
    Section,
    MODES,
    ColorType,
    SUBASSEMBLIES,
    MATERIAL,
    EXPORT,
    Simulate,
    URDFShape,
    URDFCollisionType,
    URDFCollisionShapeType,
    URDFBoundaryType,
    URDFJointType,
    URDFMotorType,
    COLOR,
    DAEMON_LOGGERS,
)
from .target_list import TargetList
from .room import Room
from .bullet import Bullet, LinkType
from .fluid import Fluid
from .provider_router import ProviderRouter
from .provider_manager import ProviderManager
from .utils import load_manifest, discover_provider
from .wiring_diagram import WiringDiagram
from model.wiring import Wiring
