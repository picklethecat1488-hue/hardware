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

warnings.filterwarnings("ignore", category=UserWarning, message=".*jax-mps was built for jaxlib.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*Platform 'mps' is experimental.*")

import sys

# Silence C-level MPS startup banners on stderr during initial JAX device probe
_stderr_fd = sys.stderr.fileno()
_saved_stderr = os.dup(_stderr_fd)
_devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(_devnull, _stderr_fd)
os.close(_devnull)

try:
    import jax

    _ = jax.devices()
finally:
    os.dup2(_saved_stderr, _stderr_fd)
    os.close(_saved_stderr)

import logging

# Enable JAX compilation caching globally to prevent JIT compile latency across tests, builds, and views
_cache_dir = Path(__file__).resolve().parents[2] / "build" / "jax_cache"
jax.config.update("jax_compilation_cache_dir", str(_cache_dir))
if os.environ.get("JAX_LOG_COMPILES") == "1":
    jax.config.update("jax_log_compiles", True)
    jax.config.update("jax_explain_cache_misses", True)

from .types import DAEMON_LOGGERS

# Silence JAX and fluid simulation loggers from console output by default
for logger_name in DAEMON_LOGGERS:
    logging.getLogger(logger_name).setLevel(logging.INFO)
    logging.getLogger(logger_name).propagate = False

# Unset experimental and potentially unstable async dispatch on MPS backend to prevent compilation deadlocks/hangs
if os.environ.get("JAX_MPS_ASYNC_DISPATCH") == "1":
    os.environ["JAX_MPS_ASYNC_DISPATCH"] = "0"

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
