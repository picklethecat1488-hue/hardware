"""Strongly-typed physical and optical material configuration models."""

from pathlib import Path
from typing import Any, Optional, Union
from pydantic import BaseModel, Field


class MaterialModel(BaseModel):
    """Physical and optical PBR properties for a material."""

    density: float = Field(default=1.0, description="Material density in g/cm³.")
    boundary_friction: float = Field(default=0.0, description="Boundary friction coefficient for physics.")
    contact_angle: float = Field(default=0.0, description="Contact angle in degrees for fluid interaction.")
    roughness: float = Field(default=0.30, description="Surface roughness (0.0 to 1.0) for PBR rendering.")
    ior: float = Field(default=1.49, description="Index of refraction.")
    transmission: float = Field(default=0.0, description="Optical transmission weight (0.0 to 1.0).")
    metallic: float = Field(default=0.0, description="Metallic reflection weight (0.0 to 1.0).")
    specular: float = Field(default=0.50, description="Specular reflection factor (0.0 to 1.0).")
    fluid_voxel_size: Optional[float] = Field(
        default=None, description="Voxel size in meters for fluid volume reconstruction."
    )
    fluid_point_radius: Optional[float] = Field(
        default=None, description="Point splat radius in meters for fluid volume reconstruction."
    )
    fluid_surface_threshold: Optional[float] = Field(
        default=None, description="Isosurface density threshold for volume-to-mesh."
    )
    fluid_adaptivity: Optional[float] = Field(default=None, description="Mesh adaptivity factor for volume-to-mesh.")
    fluid_smooth_iterations: Optional[int] = Field(
        default=None, description="Number of Laplacian smoothing iterations for reconstructed fluid surface."
    )
    fluid_smooth_factor: Optional[float] = Field(
        default=None, description="Smoothing factor (0.0 to 1.0) for reconstructed fluid surface."
    )
    use_ssfr: Optional[bool] = Field(
        default=None, description="Whether to enable screen-space fluid rendering bilateral blur."
    )


class MaterialsModel(BaseModel):
    """Collection of material models indexed by material identifier."""

    material: dict[str, MaterialModel] = Field(
        default_factory=dict, description="Dictionary of material models keyed by material name."
    )

    def get(self, name: Optional[str], default: Optional[MaterialModel] = None) -> Optional[MaterialModel]:
        """Resolve a material model by key with normalization."""
        if not name:
            return default
        clean_key = str(name).lower().replace("_", "").replace("-", "")
        if clean_key in self.material:
            return self.material[clean_key]
        for k, v in self.material.items():
            if k.lower().replace("_", "").replace("-", "") == clean_key:
                return v
        return default

    def __getitem__(self, key: str) -> MaterialModel:
        """Access material model by key with normalization."""
        res = self.get(key)
        if res is None:
            raise KeyError(f"Material '{key}' not found in MaterialsModel.")
        return res

    def __contains__(self, key: object) -> bool:
        """Check if material key exists."""
        if not isinstance(key, str):
            return False
        return self.get(key) is not None

    @classmethod
    def from_manifest(cls, manifest_data: dict[str, Any]) -> "MaterialsModel":
        """Load materials from a parsed manifest dictionary."""
        material_dict = manifest_data.get("material", {})
        materials = {
            k: MaterialModel.model_validate(v) if isinstance(v, dict) else v
            for k, v in material_dict.items()
            if isinstance(v, (dict, MaterialModel))
        }
        return cls(material=materials)

    @classmethod
    def from_yaml(cls, yaml_path: Union[str, Path]) -> "MaterialsModel":
        """Load materials from a YAML file (such as print_materials.yaml)."""
        from provider.utils import load_manifest

        manifest = load_manifest(str(yaml_path))
        return cls.from_manifest(manifest)

    @classmethod
    def default(cls) -> "MaterialsModel":
        """Load default materials from standard print_materials.yaml."""
        materials_path = Path(__file__).parent.parent / "projects" / "print_materials.yaml"
        if materials_path.exists():
            return cls.from_yaml(materials_path)
        return cls()
