"""NVIDIA Omniverse SimReady OpenUSD (.usda) Asset Parser & Subsea Physics Bridge for ROV-01.

Integrates curated generic industrial OpenUSD assets from `nvidia/simready-assets` on Hugging Face
with `UsdPhysics` rigid-body mass, buoyancy-adjusted submerged weight, collision restitution/friction
impulse calculation, and B2B ultrasonic thickness (UT) inspection targets (`UT-SR-01`, `UT-SR-02`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import pathlib
import re
from typing import Any

import numpy as np

RHO_SEAWATER_KG_M3 = 1025.0
GRAVITY_M_S2 = 9.80665
ROV01_MASS_KG = 18.5


def _default_simready_dir() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve().parent
    candidates = [
        here.parent / "viewer" / "simready_usd",
        here.parent.parent / "simready_usd",
        here / "simready_usd",
    ]
    for c in candidates:
        if c.is_dir() and (c / "simready_catalog.json").is_file():
            return c
    return candidates[0]


@dataclass
class UsdPhysicsAsset:
    asset_id: str
    prim_name: str
    usd_file: str
    title_zh: str
    title_en: str
    mission_id: str
    mission_code: str
    category: str
    hf_dataset: str
    hf_package: str
    hf_package_id: str
    hf_root_usd: str
    hf_content_sha256: str
    license: str
    api_schemas: list[str]
    rigid_body_enabled: bool
    collision_enabled: bool
    approximation: str
    mass_kg: float
    displacement_m3: float
    center_of_mass: tuple[float, float, float]
    static_friction: float
    dynamic_friction: float
    restitution: float
    ned_pos: tuple[float, float, float]
    scale: tuple[float, float, float]
    extent_min: tuple[float, float, float]
    extent_max: tuple[float, float, float]
    ut_checkpoint_id: str | None = None
    ut_label: str | None = None
    ut_zone: str | None = None
    ut_nominal_mm: float = 12.0
    ut_actual_mm: float = 11.8
    shape_archetype: str = "industrial_frame"
    pbr_color_hex: str = "#38BDF8"
    secondary_color_hex: str = "#1E293B"
    mesh_vertex_count: int = 8
    mesh_face_count: int = 6
    stage_up_axis: str = "Z"
    meters_per_unit: float = 1.0

    @property
    def buoyancy_force_n(self) -> float:
        return round(RHO_SEAWATER_KG_M3 * self.displacement_m3 * GRAVITY_M_S2, 2)

    @property
    def dry_weight_n(self) -> float:
        return round(self.mass_kg * GRAVITY_M_S2, 2)

    @property
    def submerged_weight_n(self) -> float:
        return round(max(0.0, self.dry_weight_n - self.buoyancy_force_n), 2)

    @property
    def bounding_box_size_m(self) -> tuple[float, float, float]:
        return (
            round(abs(self.extent_max[0] - self.extent_min[0]) * self.scale[0], 3),
            round(abs(self.extent_max[1] - self.extent_min[1]) * self.scale[1], 3),
            round(abs(self.extent_max[2] - self.extent_min[2]) * self.scale[2], 3),
        )

    @property
    def bounding_radius_m(self) -> float:
        bx, by, bz = self.bounding_box_size_m
        return round(0.5 * math.sqrt(bx * bx + by * by + bz * bz), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "prim_name": self.prim_name,
            "usd_file": self.usd_file,
            "usd_url": f"./simready_usd/{self.usd_file}",
            "title_zh": self.title_zh,
            "title_en": self.title_en,
            "mission_id": self.mission_id,
            "mission_code": self.mission_code,
            "category": self.category,
            "hf_dataset": self.hf_dataset,
            "hf_package": self.hf_package,
            "hf_package_id": self.hf_package_id,
            "hf_root_usd": self.hf_root_usd,
            "hf_content_sha256": self.hf_content_sha256,
            "hf_url": f"https://huggingface.co/datasets/{self.hf_dataset}/tree/main/{self.hf_package}",
            "license": self.license,
            "stage_up_axis": self.stage_up_axis,
            "meters_per_unit": self.meters_per_unit,
            "api_schemas": list(self.api_schemas),
            "usd_physics": {
                "rigid_body_enabled": self.rigid_body_enabled,
                "collision_enabled": self.collision_enabled,
                "approximation": self.approximation,
                "mass_kg": self.mass_kg,
                "displacement_m3": self.displacement_m3,
                "dry_weight_n": self.dry_weight_n,
                "buoyancy_force_n": self.buoyancy_force_n,
                "submerged_weight_n": self.submerged_weight_n,
                "center_of_mass": list(self.center_of_mass),
                "static_friction": self.static_friction,
                "dynamic_friction": self.dynamic_friction,
                "restitution": self.restitution,
            },
            "ned_pos": list(self.ned_pos),
            "scale": list(self.scale),
            "extent_min": list(self.extent_min),
            "extent_max": list(self.extent_max),
            "bounding_box_size_m": list(self.bounding_box_size_m),
            "bounding_radius_m": self.bounding_radius_m,
            "ut_checkpoint_id": self.ut_checkpoint_id,
            "ut_label": self.ut_label,
            "ut_zone": self.ut_zone,
            "ut_nominal_mm": self.ut_nominal_mm,
            "ut_actual_mm": self.ut_actual_mm,
            "shape_archetype": self.shape_archetype,
            "pbr_color_hex": self.pbr_color_hex,
            "secondary_color_hex": self.secondary_color_hex,
            "mesh_vertex_count": self.mesh_vertex_count,
            "mesh_face_count": self.mesh_face_count,
        }


def _extract_float(text: str, pattern: str, default: float) -> float:
    m = re.search(pattern, text)
    if not m:
        return default
    try:
        return float(m.group(1))
    except (TypeError, ValueError):
        return default


def _extract_str(text: str, pattern: str, default: str = "") -> str:
    m = re.search(pattern, text)
    return m.group(1) if m else default


def _extract_vec3(text: str, pattern: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    m = re.search(pattern, text)
    if not m:
        return default
    try:
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    except (TypeError, ValueError):
        return default


def parse_usda_text(usda_text: str, usd_filename: str = "unknown.usda", catalog_meta: dict[str, Any] | None = None) -> UsdPhysicsAsset:
    """Parse an ASCII OpenUSD (.usda) file and extract UsdPhysics & subsea inspection attributes."""
    meta = catalog_meta or {}
    default_prim = _extract_str(usda_text, r'defaultPrim\s*=\s*"([^"]+)"', meta.get("prim_name", "SimReadyPrim"))
    up_axis = _extract_str(usda_text, r'upAxis\s*=\s*"([^"]+)"', "Z")
    meters_per_unit = _extract_float(usda_text, r"metersPerUnit\s*=\s*([0-9.+-eE]+)", 1.0)

    schemas_match = re.search(r"prepend\s+apiSchemas\s*=\s*\[([^\]]+)\]", usda_text)
    if schemas_match:
        api_schemas = [s.strip().strip('"') for s in schemas_match.group(1).split(",") if s.strip()]
    else:
        api_schemas = ["PhysicsCollisionAPI", "PhysicsMassAPI", "PhysicsMaterialAPI"]

    asset_id = _extract_str(usda_text, r'simready:assetId\s*=\s*"([^"]+)"', meta.get("asset_id", "SR-IND-00"))
    hf_dataset = _extract_str(usda_text, r'simready:hfDataset\s*=\s*"([^"]+)"', meta.get("hf_dataset", "nvidia/simready-assets"))
    hf_package = _extract_str(usda_text, r'simready:hfPackage\s*=\s*"([^"]+)"', meta.get("hf_package", "generic_industrial"))
    hf_package_id = _extract_str(usda_text, r'simready:hfPackageId\s*=\s*"([^"]+)"', meta.get("hf_package_id", ""))
    hf_root_usd = _extract_str(usda_text, r'simready:hfRootUsd\s*=\s*"([^"]+)"', meta.get("hf_root_usd", ""))
    hf_sha256 = _extract_str(usda_text, r'simready:hfContentSha256\s*=\s*"([^"]+)"', meta.get("hf_content_sha256", ""))
    license_str = _extract_str(usda_text, r'simready:license\s*=\s*"([^"]+)"', meta.get("license", "CC-BY-4.0"))
    mission_id = _extract_str(usda_text, r'simready:missionId\s*=\s*"([^"]+)"', meta.get("mission_id", "mission_1_pool"))
    mission_code = _extract_str(usda_text, r'simready:missionCode\s*=\s*"([^"]+)"', meta.get("mission_code", "M1"))
    title_zh = _extract_str(usda_text, r'simready:titleZh\s*=\s*"([^"]+)"', meta.get("title_zh", asset_id))
    title_en = _extract_str(usda_text, r'simready:titleEn\s*=\s*"([^"]+)"', meta.get("title_en", asset_id))
    shape_archetype = _extract_str(usda_text, r'simready:shapeArchetype\s*=\s*"([^"]+)"', meta.get("shape_archetype", "calibration_rack"))
    pbr_color = _extract_str(usda_text, r'simready:pbrColorHex\s*=\s*"([^"]+)"', meta.get("pbr_color_hex", "#38BDF8"))
    sec_color = _extract_str(usda_text, r'simready:secondaryColorHex\s*=\s*"([^"]+)"', meta.get("secondary_color_hex", "#1E293B"))

    ut_cp_id = _extract_str(usda_text, r'subsea:utCheckpointId\s*=\s*"([^"]+)"', meta.get("ut_checkpoint_id") or "")
    ut_nominal = _extract_float(usda_text, r"subsea:utNominalWallMm\s*=\s*([0-9.+-eE]+)", float(meta.get("ut_nominal_mm", 12.0)))
    ut_actual = _extract_float(usda_text, r"subsea:utActualWallMm\s*=\s*([0-9.+-eE]+)", float(meta.get("ut_actual_mm", 11.8)))
    displacement = _extract_float(usda_text, r"subsea:displacementM3\s*=\s*([0-9.+-eE]+)", float(meta.get("displacement_m3", 0.03)))

    rigid_enabled = "physics:rigidBodyEnabled = true" in usda_text
    collision_enabled = "physics:collisionEnabled = true" in usda_text
    approximation = _extract_str(usda_text, r'physics:approximation\s*=\s*"([^"]+)"', "convexHull")
    mass_kg = _extract_float(usda_text, r"physics:mass\s*=\s*([0-9.+-eE]+)", float(meta.get("mass_kg", 200.0)))
    com = _extract_vec3(
        usda_text,
        r"physics:centerOfMass\s*=\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)",
        tuple(meta.get("center_of_mass", (0.0, 0.0, 0.0))),
    )
    static_friction = _extract_float(usda_text, r"physics:staticFriction\s*=\s*([0-9.+-eE]+)", float(meta.get("static_friction", 0.6)))
    dynamic_friction = _extract_float(usda_text, r"physics:dynamicFriction\s*=\s*([0-9.+-eE]+)", float(meta.get("dynamic_friction", 0.5)))
    restitution = _extract_float(usda_text, r"physics:restitution\s*=\s*([0-9.+-eE]+)", float(meta.get("restitution", 0.15)))

    ned_pos = _extract_vec3(
        usda_text,
        r"xformOp:translate\s*=\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)",
        tuple(meta.get("ned_pos", (0.0, 0.0, 4.0))),
    )
    scale = _extract_vec3(
        usda_text,
        r"xformOp:scale\s*=\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)",
        tuple(meta.get("scale", (1.0, 1.0, 1.0))),
    )

    extent_match = re.search(
        r"extent\s*=\s*\[\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)\s*,\s*\(\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*,\s*([0-9.+-eE]+)\s*\)\s*\]",
        usda_text,
    )
    if extent_match:
        extent_min = (float(extent_match.group(1)), float(extent_match.group(2)), float(extent_match.group(3)))
        extent_max = (float(extent_match.group(4)), float(extent_match.group(5)), float(extent_match.group(6)))
    else:
        extent_min = tuple(meta.get("extent_min", (-1.0, -1.0, -1.0)))
        extent_max = tuple(meta.get("extent_max", (1.0, 1.0, 1.0)))

    points_block = re.search(r"point3f\[\]\s+points\s*=\s*\[([^\]]+)\]", usda_text, re.DOTALL)
    vertex_count = len(re.findall(r"\(\s*[0-9.+-eE]+", points_block.group(1))) if points_block else 8

    faces_block = re.search(r"int\[\]\s+faceVertexCounts\s*=\s*\[([^\]]+)\]", usda_text)
    face_count = len([x.strip() for x in faces_block.group(1).split(",") if x.strip()]) if faces_block else 6

    return UsdPhysicsAsset(
        asset_id=asset_id,
        prim_name=default_prim,
        usd_file=usd_filename,
        title_zh=title_zh,
        title_en=title_en,
        mission_id=mission_id,
        mission_code=mission_code,
        category=meta.get("category", "SimReady Subsea Industrial Asset"),
        hf_dataset=hf_dataset,
        hf_package=hf_package,
        hf_package_id=hf_package_id,
        hf_root_usd=hf_root_usd,
        hf_content_sha256=hf_sha256,
        license=license_str,
        api_schemas=api_schemas,
        rigid_body_enabled=rigid_enabled,
        collision_enabled=collision_enabled,
        approximation=approximation,
        mass_kg=mass_kg,
        displacement_m3=displacement,
        center_of_mass=com,
        static_friction=static_friction,
        dynamic_friction=dynamic_friction,
        restitution=restitution,
        ned_pos=ned_pos,
        scale=scale,
        extent_min=extent_min,
        extent_max=extent_max,
        ut_checkpoint_id=ut_cp_id if ut_cp_id else None,
        ut_label=meta.get("ut_label"),
        ut_zone=meta.get("ut_zone"),
        ut_nominal_mm=ut_nominal,
        ut_actual_mm=ut_actual,
        shape_archetype=shape_archetype,
        pbr_color_hex=pbr_color,
        secondary_color_hex=sec_color,
        mesh_vertex_count=vertex_count,
        mesh_face_count=face_count,
        stage_up_axis=up_axis,
        meters_per_unit=meters_per_unit,
    )


def parse_usda_file(usd_path: str | pathlib.Path, catalog_meta: dict[str, Any] | None = None) -> UsdPhysicsAsset:
    p = pathlib.Path(usd_path)
    text = p.read_text(encoding="utf-8")
    return parse_usda_text(text, usd_filename=p.name, catalog_meta=catalog_meta)


def load_simready_assets(usd_dir: str | pathlib.Path | None = None) -> list[UsdPhysicsAsset]:
    base = pathlib.Path(usd_dir) if usd_dir else _default_simready_dir()
    cat_path = base / "simready_catalog.json"
    if not cat_path.is_file():
        return []
    raw = json.loads(cat_path.read_text(encoding="utf-8"))
    assets: list[UsdPhysicsAsset] = []
    for item in raw.get("assets", []):
        usd_file = item.get("usd_file", "")
        usd_path = base / usd_file
        if usd_path.is_file():
            assets.append(parse_usda_file(usd_path, catalog_meta=item))
    return assets


def load_simready_catalog_dict(usd_dir: str | pathlib.Path | None = None) -> dict[str, Any]:
    base = pathlib.Path(usd_dir) if usd_dir else _default_simready_dir()
    cat_path = base / "simready_catalog.json"
    raw = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.is_file() else {}
    parsed_assets = [a.to_dict() for a in load_simready_assets(base)]
    return {
        "schema_version": raw.get("schema_version", "SimReady-OpenUSD-Subsea-1.0"),
        "source_dataset": raw.get("source_dataset", "https://huggingface.co/datasets/nvidia/simready-assets"),
        "source_space": raw.get("source_space", "https://huggingface.co/spaces/nvidia/simready-central"),
        "web_viewer_package": raw.get("web_viewer_package", "@huggingface/usd-web-viewer@0.2.0"),
        "web_viewer_changelog": raw.get("web_viewer_changelog", "https://huggingface.co/changelog/openusd-viewer-and-simready-asset-previews"),
        "ip_compliance": raw.get("ip_compliance", "100% Generic Industrial NVIDIA SimReady Assets (CC-BY-4.0)"),
        "asset_count": len(parsed_assets),
        "assets": parsed_assets,
    }


def get_simready_usda_payload(asset_id: str, usd_dir: str | pathlib.Path | None = None) -> dict[str, Any] | None:
    base = pathlib.Path(usd_dir) if usd_dir else _default_simready_dir()
    for a in load_simready_assets(base):
        if a.asset_id.upper() == str(asset_id).strip().upper():
            usd_path = base / a.usd_file
            raw_usda = usd_path.read_text(encoding="utf-8") if usd_path.is_file() else ""
            return {
                "asset": a.to_dict(),
                "raw_usda": raw_usda,
                "stage_hierarchy": [
                    {
                        "path": f"/{a.prim_name}",
                        "type": "Xform",
                        "api_schemas": a.api_schemas,
                    },
                    {
                        "path": f"/{a.prim_name}/Visual_And_Collision_Hull",
                        "type": "Mesh",
                        "api_schemas": ["PhysicsCollisionAPI"],
                        "vertices": a.mesh_vertex_count,
                        "faces": a.mesh_face_count,
                    },
                ],
            }
    return None


def compute_usd_collision_impulse(
    asset: UsdPhysicsAsset,
    rov_vel_ned: tuple[float, float, float] | list[float] | np.ndarray,
    rov_pos_ned: tuple[float, float, float] | list[float] | np.ndarray | None = None,
    rov_mass_kg: float = ROV01_MASS_KG,
) -> dict[str, Any]:
    """Compute realistic 3D rigid-body collision impulse (N*s), rebound velocity, and friction drag
    between ROV-01 and a SimReady OpenUSD asset using UsdPhysics mass, restitution, and friction.
    """
    v = np.asarray(rov_vel_ned, dtype=float)
    if v.shape != (3,) or not np.all(np.isfinite(v)):
        v = np.array([0.85, 0.0, 0.0], dtype=float)
    speed = float(np.linalg.norm(v))
    if speed < 1e-3:
        v = np.array([0.85, 0.0, 0.0], dtype=float)
        speed = float(np.linalg.norm(v))

    asset_pos = np.asarray(asset.ned_pos, dtype=float)
    if rov_pos_ned is not None:
        r_pos = np.asarray(rov_pos_ned, dtype=float)
        diff = r_pos - asset_pos
        dist = float(np.linalg.norm(diff))
        normal = (diff / dist) if dist > 1e-4 else (-v / speed)
    else:
        normal = -v / speed

    # Ensure normal opposes incoming velocity
    v_dot_n = float(np.dot(v, normal))
    if v_dot_n > 0:
        normal = -normal
        v_dot_n = -v_dot_n

    v_normal = v_dot_n * normal
    v_tangent = v - v_normal
    tangent_speed = float(np.linalg.norm(v_tangent))

    # Effective reduced mass: 1 / (1/m_rov + 1/m_asset)
    inv_m_rov = 1.0 / max(1.0, float(rov_mass_kg))
    inv_m_asset = 1.0 / max(1.0, float(asset.mass_kg))
    reduced_mass = 1.0 / (inv_m_rov + inv_m_asset)

    e = float(np.clip(asset.restitution, 0.0, 1.0))
    mu_d = float(np.clip(asset.dynamic_friction, 0.0, 1.5))

    # Normal impulse magnitude J_n = m_eff * (1 + e) * |v_n|
    normal_speed = abs(v_dot_n)
    j_normal_ns = float(reduced_mass * (1.0 + e) * normal_speed)

    # Coulomb tangential friction impulse J_t <= mu_d * J_n
    max_j_tangent = float(reduced_mass * tangent_speed)
    j_tangent_ns = min(mu_d * j_normal_ns, max_j_tangent)
    tangent_dir = (-v_tangent / tangent_speed) if tangent_speed > 1e-5 else np.zeros(3, dtype=float)

    impulse_vec = j_normal_ns * normal + j_tangent_ns * tangent_dir
    rebound_vel = v + impulse_vec * inv_m_rov

    # Hull integrity penalty proportional to normal impulse and inverse restitution cushioning
    hull_damage_pct = round(min(28.0, max(1.5, j_normal_ns * 0.42)), 2)

    return {
        "asset_id": asset.asset_id,
        "prim_name": asset.prim_name,
        "title_zh": asset.title_zh,
        "impact_speed_mps": round(speed, 3),
        "normal_impulse_ns": round(j_normal_ns, 3),
        "friction_impulse_ns": round(j_tangent_ns, 3),
        "total_impulse_ns": round(float(np.linalg.norm(impulse_vec)), 3),
        "restitution_used": round(e, 3),
        "dynamic_friction_used": round(mu_d, 3),
        "reduced_mass_kg": round(reduced_mass, 3),
        "rebound_velocity_ned": [round(float(x), 3) for x in rebound_vel],
        "hull_damage_pct": hull_damage_pct,
    }
