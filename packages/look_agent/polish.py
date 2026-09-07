from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from look_agent.marble_client import MarbleClient, MarbleError

# Prefer smaller free exports first; 150k is NOT always available per-world.
_SPLAT_FALLBACKS = ("100k", "500k", "full_res")


def polish_and_export(
    client: MarbleClient,
    *,
    world: dict[str, Any],
    out_dir: Path,
    export_mesh: bool = False,
    splat_resolution: str = "100k",
) -> dict[str, Any]:
    """
    Download showcase assets for a finished Marble world.
    PLY splats are free; HQ mesh GLB costs credits (opt-in).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    world_id = world["world_id"]
    (out_dir / "world.json").write_text(json.dumps(world, indent=2) + "\n", encoding="utf-8")

    result: dict[str, Any] = {
        "world_id": world_id,
        "world_marble_url": world.get("world_marble_url"),
        "exports": {},
    }

    ply_path, used_res = _export_ply_with_fallback(
        client, world_id, out_dir, preferred=splat_resolution
    )
    if ply_path:
        result["exports"]["ply"] = str(ply_path)
        result["exports"]["ply_resolution"] = used_res

    if export_mesh:
        mesh_op = client.export_world(world_id, asset_type="mesh", fmt="glb")
        mesh_op = _ensure_done(client, mesh_op)
        mesh_url = (mesh_op.get("response") or {}).get("url")
        if mesh_url:
            mesh_path = client.download_url(mesh_url, out_dir / "world_mesh.glb")
            result["exports"]["glb"] = str(mesh_path)

    polish = {
        "status": "exported" if result["exports"] else "world_only",
        "notes": [
            "PLY splat downloaded for showcase." if ply_path else "PLY export skipped/failed.",
            "Open world_marble_url in Marble for interactive showcase.",
            "Local mesh polish / collider bake can run on GLB when exported.",
        ],
        "next_controls": [
            "reprompt_with_critique",
            "export_mesh",
            "try_splat_resolution_500k_or_full_res",
            "raise_to_plus_model",
        ],
    }
    (out_dir / "polish.json").write_text(json.dumps(polish, indent=2) + "\n", encoding="utf-8")
    result["polish"] = polish
    return result


def _export_ply_with_fallback(
    client: MarbleClient,
    world_id: str,
    out_dir: Path,
    *,
    preferred: str,
) -> tuple[Path | None, str | None]:
    tried: list[str] = []
    queue: list[str] = []
    for res in (preferred, *_SPLAT_FALLBACKS):
        if res not in queue:
            queue.append(res)

    last_err: Exception | None = None
    while queue:
        resolution = queue.pop(0)
        if resolution in tried:
            continue
        tried.append(resolution)
        try:
            ply_op = client.export_world(
                world_id,
                asset_type="splats",
                fmt="ply",
                resolution=resolution,
            )
            ply_op = _ensure_done(client, ply_op)
            ply_url = (ply_op.get("response") or {}).get("url")
            if not ply_url:
                continue
            path = client.download_url(ply_url, out_dir / f"world_{resolution}.ply")
            return path, resolution
        except MarbleError as exc:
            last_err = exc
            available = _parse_available_resolutions(str(exc))
            for res in available:
                if res not in tried and res not in queue:
                    queue.append(res)

    if last_err:
        # Don't fail the whole showcase job — world URL is still usable
        (out_dir / "export_error.txt").write_text(str(last_err) + "\n", encoding="utf-8")
    return None, None


def _parse_available_resolutions(message: str) -> list[str]:
    """Parse '... Available resolutions: 100k, 500k, full_res.' from Marble 400s."""
    m = re.search(r"Available resolutions:\s*([^.]+)", message, re.IGNORECASE)
    if not m:
        return []
    return [p.strip() for p in m.group(1).split(",") if p.strip()]


def _ensure_done(client: MarbleClient, op: dict[str, Any]) -> dict[str, Any]:
    if op.get("done"):
        if op.get("error"):
            raise RuntimeError(f"Export failed: {op['error']}")
        return op
    op_id = op.get("operation_id")
    if not op_id:
        raise RuntimeError(f"Export response missing operation_id: {op}")
    return client.wait_operation(op_id)
