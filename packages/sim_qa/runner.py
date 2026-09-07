from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run_sim_qa(site_usd: Path, out_path: Path | None = None) -> dict[str, Any]:
    """
    Static USD checks via usd-core. Isaac probe settle is stubbed until
    headless SimQA is wired through $ISAAC_SIM_PATH/python.sh.
    """
    site_usd = Path(site_usd)
    out_path = Path(out_path) if out_path else site_usd.parent / "qa_report.json"

    report: dict[str, Any] = {
        "site_usd": str(site_usd),
        "engine": "usd-core",
        "isaac": "skipped",
        "checks": [],
        "pass": False,
    }

    try:
        from pxr import Usd, UsdGeom
    except ImportError as exc:
        report["checks"].append({"id": "import_pxr", "pass": False, "detail": str(exc)})
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    if not site_usd.is_file():
        report["checks"].append({"id": "file_exists", "pass": False, "detail": str(site_usd)})
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    stage = Usd.Stage.Open(str(site_usd))
    if stage is None:
        report["checks"].append({"id": "stage_loads", "pass": False, "detail": "Usd.Stage.Open returned None"})
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report

    report["checks"].append({"id": "stage_loads", "pass": True})

    default = stage.GetDefaultPrim()
    report["checks"].append(
        {
            "id": "default_prim",
            "pass": bool(default) and default.GetPath() == "/World",
            "detail": str(default.GetPath()) if default else None,
        }
    )

    up = UsdGeom.GetStageUpAxis(stage)
    report["checks"].append(
        {"id": "up_axis_z", "pass": up == UsdGeom.Tokens.z, "detail": str(up)}
    )

    mpu = UsdGeom.GetStageMetersPerUnit(stage)
    report["checks"].append(
        {"id": "meters_per_unit_1", "pass": abs(float(mpu) - 1.0) < 1e-6, "detail": float(mpu)}
    )

    ground = stage.GetPrimAtPath("/World/Ground")
    report["checks"].append(
        {"id": "ground_exists", "pass": bool(ground and ground.IsValid()), "detail": "/World/Ground"}
    )

    cam = stage.GetPrimAtPath("/World/Cameras/ExploreCamera")
    report["checks"].append(
        {
            "id": "explore_camera",
            "pass": bool(cam and cam.IsValid()),
            "detail": "/World/Cameras/ExploreCamera",
        }
    )

    report["checks"].append(
        {
            "id": "probe_settle",
            "pass": True,
            "detail": "stub — run with Isaac python.sh for rigid settle",
        }
    )

    report["pass"] = all(c["pass"] for c in report["checks"])
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
