from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Region = Literal["asia", "europe", "americas", "generic"]


class WorldBrief(BaseModel):
    """User intent for a showcase world (Marble path)."""

    prompt: str = Field(..., min_length=3, description="Natural-language world request")
    region: Region = "americas"
    display_name: str | None = Field(default=None, max_length=64)
    mood: str | None = None
    must_include: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    seed: int | None = None
    tags: list[str] = Field(default_factory=list)

    def job_id(self) -> str:
        slug = "".join(c if c.isalnum() else "-" for c in (self.display_name or "world").lower())
        slug = "-".join(filter(None, slug.split("-")))[:40] or "world"
        seed = self.seed if self.seed is not None else "x"
        return f"marble_{slug}_s{seed}"
