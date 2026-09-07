from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


Region = Literal["asia", "europe", "americas"]
Density = Literal["low", "med"]
Pipeline = Literal["local", "marble"]


class SiteSpec(BaseModel):
    """Authoritative input for Local / Marble site generation."""

    region: Region = "americas"
    seed: int = 42
    plot_m: tuple[float, float] = Field(default=(40.0, 60.0), description="[width, depth] meters")
    phases: list[str] = Field(default_factory=lambda: ["structure"])
    zones: list[str] = Field(
        default_factory=lambda: ["excavation", "staging", "build", "perimeter"]
    )
    density: Density = "low"
    include_scaffolding: bool = True
    pipeline: Pipeline = "local"

    @field_validator("plot_m")
    @classmethod
    def _plot_positive(cls, v: tuple[float, float]) -> tuple[float, float]:
        if len(v) != 2 or v[0] <= 0 or v[1] <= 0:
            raise ValueError("plot_m must be [width, depth] with positive meters")
        return (float(v[0]), float(v[1]))

    def site_id(self) -> str:
        w, d = self.plot_m
        return f"{self.region}_s{self.seed}_{int(w)}x{int(d)}"
