from __future__ import annotations

import json
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade

from layout import Placement
from site_spec import SiteSpec


def compose_site(
    spec: SiteSpec,
    placements: list[Placement],
    out_dir: Path,
    *,
    look_at: tuple[float, float, float] | None = None,
) -> Path:
    """Write layered site.usd + payloads under out_dir. Returns path to site.usd."""
    out_dir = Path(out_dir)
    payloads = out_dir / "payloads"
    payloads.mkdir(parents=True, exist_ok=True)

    geom_path = payloads / "geometry.usd"
    phys_path = payloads / "physics.usd"
    sem_path = payloads / "semantics.usd"
    lights_path = payloads / "lights_cameras.usd"
    root_path = out_dir / "site.usd"

    _write_geometry(geom_path, placements)
    _write_physics(phys_path, placements)
    _write_semantics(sem_path, placements)
    _write_lights_cameras(lights_path, spec, look_at=look_at)
    _write_root(root_path)

    meta = {
        "site_id": spec.site_id(),
        "region": spec.region,
        "seed": spec.seed,
        "plot_m": list(spec.plot_m),
        "pipeline": spec.pipeline,
        "prim_count": len(placements),
        "layers": [
            "site.usd",
            "payloads/geometry.usd",
            "payloads/physics.usd",
            "payloads/semantics.usd",
            "payloads/lights_cameras.usd",
        ],
    }
    (out_dir / "site_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return root_path


def _new_stage(path: Path) -> Usd.Stage:
    if path.exists():
        path.unlink()
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    return stage


def _write_geometry(path: Path, placements: list[Placement]) -> None:
    stage = _new_stage(path)
    for p in placements:
        _ensure_xform_ancestors(stage, p.prim_path)
        cube = UsdGeom.Cube.Define(stage, p.prim_path)
        # UsdGeom.Cube size is edge length; default cube is 2.0 — scale to meters.
        cube.CreateSizeAttr(2.0)
        xformable = UsdGeom.Xformable(cube.GetPrim())
        xformable.ClearXformOpOrder()
        xformable.AddTranslateOp().Set(Gf.Vec3d(*p.translate))
        sx, sy, sz = p.size
        xformable.AddScaleOp().Set(Gf.Vec3f(sx / 2.0, sy / 2.0, sz / 2.0))
        if not p.visible:
            cube.CreateVisibilityAttr().Set("invisible")
        _bind_display_color(stage, cube.GetPrim(), p)
    stage.GetRootLayer().Save()


def _bind_display_color(stage: Usd.Stage, prim: Usd.Prim, p: Placement) -> None:
    # Lightweight: displayColor on gprim (Isaac / usdview friendly)
    gprim = UsdGeom.Gprim(prim)
    gprim.CreateDisplayColorAttr([Gf.Vec3f(*p.color)])
    # Also a simple preview surface for better look in Isaac
    mat_path = f"/World/Looks/{p.name}_Mat"
    _ensure_xform_ancestors(stage, mat_path)
    material = UsdShade.Material.Define(stage, mat_path)
    shader = UsdShade.Shader.Define(stage, f"{mat_path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*p.color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.75)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)


def _write_physics(path: Path, placements: list[Placement]) -> None:
    stage = _new_stage(path)
    for p in placements:
        _ensure_xform_ancestors(stage, p.prim_path)
        # Overlaid prim (same path) — collision only, no rigid body (static site)
        prim = stage.OverridePrim(p.prim_path)
        UsdPhysics.CollisionAPI.Apply(prim)
        mesh_api = UsdPhysics.MeshCollisionAPI.Apply(prim)
        mesh_api.CreateApproximationAttr().Set("boundingCube")
    stage.GetRootLayer().Save()


def _write_semantics(path: Path, placements: list[Placement]) -> None:
    stage = _new_stage(path)
    for p in placements:
        _ensure_xform_ancestors(stage, p.prim_path)
        prim = stage.OverridePrim(p.prim_path)
        prim.CreateAttribute("semantic:label", Sdf.ValueTypeNames.String).Set(p.semantic_label)
        prim.CreateAttribute("semantic:assetClass", Sdf.ValueTypeNames.String).Set(p.asset_class)
        prim.SetCustomDataByKey("semanticLabel", p.semantic_label)
    stage.GetRootLayer().Save()


def _write_lights_cameras(
    path: Path,
    spec: SiteSpec,
    *,
    look_at: tuple[float, float, float] | None = None,
) -> None:
    stage = _new_stage(path)
    w, d = spec.plot_m
    target = look_at or (0.0, d * 0.15, 2.0)

    # Distant sun (Z-up: light direction toward -Z/-Y)
    distant = UsdLux.DistantLight.Define(stage, "/World/Lights/Sun")
    distant.CreateIntensityAttr(3000.0)
    distant.CreateAngleAttr(1.0)
    dx = UsdGeom.Xformable(distant.GetPrim())
    dx.ClearXformOpOrder()
    dx.AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 30.0, 0.0))

    dome = UsdLux.DomeLight.Define(stage, "/World/Lights/Dome")
    dome.CreateIntensityAttr(400.0)

    # Eye-height explore camera looking at build zone
    cam = UsdGeom.Camera.Define(stage, "/World/Cameras/ExploreCamera")
    cam.CreateFocalLengthAttr(18.0)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.1, 500.0))
    eye = Gf.Vec3d(-w * 0.45, -d * 0.45, 1.6)
    target_v = Gf.Vec3d(*target)
    _aim_camera(cam, eye, target_v)

    stage.GetRootLayer().Save()


def _aim_camera(cam: UsdGeom.Camera, eye: Gf.Vec3d, target: Gf.Vec3d) -> None:
    """Z-up camera: -Z look, +Y up (USD camera convention)."""
    forward = (target - eye).GetNormalized()
    world_up = Gf.Vec3d(0, 0, 1)
    right = Gf.Cross(forward, world_up).GetNormalized()
    up = Gf.Cross(right, forward).GetNormalized()
    # Camera looks down local -Z; build rotation matrix with columns right, up, -forward
    rot = Gf.Matrix3d(
        right[0], up[0], -forward[0],
        right[1], up[1], -forward[1],
        right[2], up[2], -forward[2],
    )
    # Orthonormalize via Matrix4d transform
    m = Gf.Matrix4d(
        right[0], right[1], right[2], 0,
        up[0], up[1], up[2], 0,
        -forward[0], -forward[1], -forward[2], 0,
        eye[0], eye[1], eye[2], 1,
    )
    # USD xform prefers translate + orient; use transform op
    xf = UsdGeom.Xformable(cam.GetPrim())
    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(m)
    _ = rot  # constructed for clarity / future euler export


def _write_root(path: Path) -> None:
    if path.exists():
        path.unlink()
    root = Sdf.Layer.CreateNew(str(path))
    root.defaultPrim = "World"
    root.pseudoRoot.SetInfo("upAxis", "Z")
    root.pseudoRoot.SetInfo("metersPerUnit", 1.0)
    root.subLayerPaths = [
        "./payloads/geometry.usd",
        "./payloads/physics.usd",
        "./payloads/semantics.usd",
        "./payloads/lights_cameras.usd",
    ]
    # Ensure /World exists as default prim even before payloads resolve
    world = Sdf.PrimSpec(root, "World", Sdf.SpecifierDef, "Xform")
    root.defaultPrim = world.name
    root.Save()


def _ensure_xform_ancestors(stage: Usd.Stage, prim_path: str) -> None:
    path = Sdf.Path(prim_path)
    for ancestor in path.GetPrefixes()[:-1]:
        if ancestor == Sdf.Path("/World"):
            continue
        if not stage.GetPrimAtPath(ancestor):
            UsdGeom.Xform.Define(stage, ancestor)
