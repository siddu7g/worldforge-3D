from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def packs_root() -> Path:
    """Repo packs/ directory (…/3D/packs)."""
    # packages/asset_registry/registry.py → parents[2] == repo root
    return Path(__file__).resolve().parents[2] / "packs"


@dataclass(frozen=True)
class AssetPack:
    region: str
    version: str
    description: str
    materials: dict[str, list[float]]
    priors: dict[str, Any]
    primitives: dict[str, str] = field(default_factory=dict)
    path: Path | None = None

    def color(self, asset_class: str) -> tuple[float, float, float]:
        rgb = self.materials.get(asset_class) or self.materials.get("ground") or [0.5, 0.5, 0.5]
        return (float(rgb[0]), float(rgb[1]), float(rgb[2]))


def load_pack(region: str, root: Path | None = None) -> AssetPack:
    root = root or packs_root()
    pack_dir = root / region
    pack_file = pack_dir / "pack.yaml"
    if not pack_file.is_file():
        raise FileNotFoundError(f"Missing pack for region={region!r}: {pack_file}")
    raw = yaml.safe_load(pack_file.read_text(encoding="utf-8")) or {}
    return AssetPack(
        region=str(raw.get("region", region)),
        version=str(raw.get("version", "0.0.0")),
        description=str(raw.get("description", "")),
        materials={k: list(v) for k, v in (raw.get("materials") or {}).items()},
        priors=dict(raw.get("priors") or {}),
        primitives=dict(raw.get("primitives") or {}),
        path=pack_dir,
    )
