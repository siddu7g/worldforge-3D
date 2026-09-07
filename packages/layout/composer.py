from __future__ import annotations

import math
import random
from dataclasses import dataclass

from asset_registry import AssetPack, load_pack
from site_spec import SiteSpec


@dataclass(frozen=True)
class ZoneRect:
    name: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) * 0.5, (self.y0 + self.y1) * 0.5)

    @property
    def size(self) -> tuple[float, float]:
        return (self.x1 - self.x0, self.y1 - self.y0)


@dataclass(frozen=True)
class Placement:
    """One low-poly prim to emit into geometry.usd."""

    name: str
    prim_path: str
    asset_class: str
    semantic_label: str
    translate: tuple[float, float, float]
    size: tuple[float, float, float]
    color: tuple[float, float, float]
    visible: bool = True


class LayoutComposer:
    """Place pack primitives from SiteSpec + regional priors (no forked engines)."""

    def compose(self, spec: SiteSpec, pack: AssetPack | None = None) -> list[Placement]:
        pack = pack or load_pack(spec.region)
        rng = random.Random(spec.seed)
        w, d = spec.plot_m
        zones = self._zones(w, d, pack.priors)

        placements: list[Placement] = [self._ground(w, d, pack)]
        if "excavation" in zones:
            placements.append(self._excavation(zones["excavation"], pack))
        if "build" in zones:
            placements.extend(self._building_and_scaffold(spec, zones["build"], pack, rng))
        if "staging" in zones:
            placements.extend(self._material_piles(spec, zones["staging"], pack, rng))
        placements.extend(self._perimeter(w, d, pack))
        return placements

    def zone_rects(self, spec: SiteSpec, pack: AssetPack | None = None) -> dict[str, ZoneRect]:
        pack = pack or load_pack(spec.region)
        w, d = spec.plot_m
        return self._zones(w, d, pack.priors)

    def _zones(self, w: float, d: float, priors: dict) -> dict[str, ZoneRect]:
        fracs = priors.get("zone_fractions") or {
            "excavation": 0.2,
            "staging": 0.3,
            "build": 0.5,
        }
        x0, x1 = -w * 0.5, w * 0.5
        y0 = -d * 0.5
        out: dict[str, ZoneRect] = {}
        cursor = y0
        for name in ("excavation", "staging", "build"):
            span = d * float(fracs.get(name, 0.0))
            out[name] = ZoneRect(name, x0, cursor, x1, cursor + span)
            cursor += span
        out["perimeter"] = ZoneRect("perimeter", x0, y0, x1, y0 + d)
        return out

    def _ground(self, w: float, d: float, pack: AssetPack) -> Placement:
        thickness = 0.2
        return Placement(
            name="Ground",
            prim_path="/World/Ground",
            asset_class="ground",
            semantic_label="ground",
            translate=(0.0, 0.0, -thickness * 0.5),
            size=(w, d, thickness),
            color=pack.color("ground"),
        )

    def _excavation(self, zone: ZoneRect, pack: AssetPack) -> Placement:
        zw, zd = zone.size
        cx, cy = zone.center
        depth = 1.5
        pad = 2.0
        return Placement(
            name="Excavation",
            prim_path="/World/Zones/Excavation",
            asset_class="excavation",
            semantic_label="excavation",
            translate=(cx, cy, -depth * 0.5),
            size=(max(zw - pad, 4.0), max(zd - pad, 4.0), depth),
            color=pack.color("excavation"),
        )

    def _building_and_scaffold(
        self,
        spec: SiteSpec,
        zone: ZoneRect,
        pack: AssetPack,
        rng: random.Random,
    ) -> list[Placement]:
        priors = pack.priors
        bx, by, bz = [float(v) for v in priors.get("building_size_m", [12, 16, 8])]
        lane = float(priors.get("lane_width_m", 6.0))
        zw, zd = zone.size
        bx = min(bx, max(zw - 2 * lane, 4.0))
        by = min(by, max(zd - lane, 4.0))
        cx, cy = zone.center
        cx += rng.uniform(-1.0, 1.0)
        cy += rng.uniform(-1.0, 1.0)

        out = [
            Placement(
                name="Building",
                prim_path="/World/Building",
                asset_class="building",
                semantic_label="building",
                translate=(cx, cy, bz * 0.5),
                size=(bx, by, bz),
                color=pack.color("building"),
            )
        ]
        if not spec.include_scaffolding:
            return out

        bay = float(priors.get("scaffold_bay_m", 2.5))
        clearance = float(priors.get("scaffold_clearance_m", 0.8))
        post = 0.2
        height = bz + 1.0
        half_x = bx * 0.5 + clearance
        half_y = by * 0.5 + clearance
        idx = 0

        faces = [
            ("x", half_x, half_y),
            ("x", half_x, -half_y),
            ("y", half_y, half_x),
            ("y", half_y, -half_x),
        ]
        for axis, span_half, fixed in faces:
            n = max(2, int(math.floor(2 * span_half / bay)) + 1)
            for i in range(n):
                t = -1.0 + (2.0 * i / (n - 1))
                if axis == "x":
                    px, py = cx + t * span_half, cy + fixed
                else:
                    px, py = cx + fixed, cy + t * span_half
                out.append(
                    Placement(
                        name=f"Scaffold_{idx}",
                        prim_path=f"/World/Scaffold/Post_{idx}",
                        asset_class="scaffold",
                        semantic_label="scaffold",
                        translate=(px, py, height * 0.5),
                        size=(post, post, height),
                        color=pack.color("scaffold"),
                    )
                )
                idx += 1
        return out

    def _material_piles(
        self,
        spec: SiteSpec,
        zone: ZoneRect,
        pack: AssetPack,
        rng: random.Random,
    ) -> list[Placement]:
        priors = pack.priors
        key = "pile_count_low" if spec.density == "low" else "pile_count_med"
        n = int(priors.get(key, 3))
        sx, sy, sz = [float(v) for v in priors.get("pile_size_m", [2, 2, 1.2])]
        margin = 2.0
        out: list[Placement] = []
        for i in range(n):
            px = rng.uniform(zone.x0 + margin, zone.x1 - margin)
            py = rng.uniform(zone.y0 + margin, zone.y1 - margin)
            out.append(
                Placement(
                    name=f"Pile_{i}",
                    prim_path=f"/World/Materials/Pile_{i}",
                    asset_class="material_pile",
                    semantic_label="material_pile",
                    translate=(px, py, sz * 0.5),
                    size=(sx, sy, sz),
                    color=pack.color("material_pile"),
                )
            )
        return out

    def _perimeter(self, w: float, d: float, pack: AssetPack) -> list[Placement]:
        priors = pack.priors
        h = float(priors.get("barrier_height_m", 1.2))
        thick = float(priors.get("barrier_thickness_m", 0.15))
        seg = float(priors.get("barrier_segment_m", 4.0))
        gate_w = float(priors.get("gate_width_m", 8.0))
        gate_side = str(priors.get("gate_side", "south"))

        x0, x1 = -w * 0.5, w * 0.5
        y0, y1 = -d * 0.5, d * 0.5
        out: list[Placement] = []
        idx = 0

        def emit(tx: float, ty: float, sx: float, sy: float) -> None:
            nonlocal idx
            out.append(
                Placement(
                    name=f"Barrier_{idx}",
                    prim_path=f"/World/Perimeter/Barrier_{idx}",
                    asset_class="barrier",
                    semantic_label="barrier",
                    translate=(tx, ty, h * 0.5),
                    size=(sx, sy, h),
                    color=pack.color("barrier"),
                )
            )
            idx += 1

        def segments_along(length: float) -> list[tuple[float, float]]:
            """Return (center_offset_from_start, segment_length) pairs."""
            n = max(1, int(math.ceil(length / seg)))
            sl = length / n
            return [((i + 0.5) * sl, sl) for i in range(n)]

        # North (+Y)
        for off, sl in segments_along(w):
            emit(x0 + off, y1, sl, thick)
        # South (-Y) with gate gap
        for off, sl in segments_along(w):
            cx = x0 + off
            if gate_side == "south" and abs(cx) < gate_w * 0.5:
                continue
            emit(cx, y0, sl, thick)
        # East (+X)
        for off, sl in segments_along(d):
            emit(x1, y0 + off, thick, sl)
        # West (-X)
        for off, sl in segments_along(d):
            emit(x0, y0 + off, thick, sl)

        out.append(
            Placement(
                name="Gate",
                prim_path="/World/Perimeter/Gate",
                asset_class="gate",
                semantic_label="gate",
                translate=(0.0, y0, 0.05),
                size=(gate_w, 1.0, 0.1),
                color=pack.color("gate"),
            )
        )
        return out
