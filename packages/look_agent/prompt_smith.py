from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from look_agent.brief import WorldBrief
from look_agent.config import LookConfig

# Regional construction priors baked into Marble prompts (showcase language, not USD packs).
_REGION_PRIORS: dict[str, str] = {
    "americas": (
        "wide vehicle lanes, large staging yard, orange safety barriers, "
        "steel scaffold towers, stacked lumber and rebar piles, chain-link perimeter with a gate gap"
    ),
    "europe": (
        "modular scaffold with regular bay spacing, strict perimeter fencing, "
        "compact staging, painted temporary barriers, orderly material stacks"
    ),
    "asia": (
        "higher density props, narrower lanes, compact staging, bamboo or dense metal scaffold, "
        "stacked formwork panels, busy perimeter"
    ),
    "generic": "believable construction-site scale, clear ground plane, readable structure",
}


@dataclass(frozen=True)
class DraftPrompt:
    name: str
    text_prompt: str
    rationale: str


class PromptSmith:
    """Turn a rough user brief into strong Marble text prompts (+ variants)."""

    def __init__(self, cfg: LookConfig):
        self.cfg = cfg

    def expand(self, brief: WorldBrief, n: int) -> list[DraftPrompt]:
        n = max(1, n)
        if self.cfg.openrouter_api_key:
            try:
                return self._expand_llm(brief, n)
            except Exception:
                # Fall back to deterministic templates if OpenRouter fails
                pass
        return self._expand_templates(brief, n)

    def _base_context(self, brief: WorldBrief) -> str:
        parts = [brief.prompt.strip()]
        parts.append(f"Regional construction style: {_REGION_PRIORS.get(brief.region, _REGION_PRIORS['generic'])}.")
        if brief.mood:
            parts.append(f"Mood / lighting: {brief.mood}.")
        if brief.must_include:
            parts.append("Must clearly include: " + ", ".join(brief.must_include) + ".")
        if brief.avoid:
            parts.append("Avoid: " + ", ".join(brief.avoid) + ".")
        parts.append(
            "Photoreal outdoor construction site, human eye-level exploration, "
            "coherent ground, no floating props, no fantasy ruins unless requested."
        )
        return " ".join(parts)

    def _expand_templates(self, brief: WorldBrief, n: int) -> list[DraftPrompt]:
        base = self._base_context(brief)
        variants = [
            (
                "wide_establishing",
                "Wide establishing view of an active construction site. " + base
                + " Emphasize plot extent, perimeter fencing, and staging yard.",
                "Wide establishing / plot readability",
            ),
            (
                "scaffold_focus",
                "Close-to-mid view around a building under structure with scaffold towers. " + base
                + " Emphasize scaffold bays, building footprint, and material piles nearby.",
                "Scaffold + structure focus",
            ),
            (
                "golden_hour_ops",
                "Golden-hour construction site with warm directional light and long soft shadows. " + base
                + " Dust in air, wet concrete textures, orange barriers catching light.",
                "Lighting / atmosphere variant",
            ),
            (
                "overcast_detail",
                "Overcast daylight construction site with soft diffuse lighting and high material detail. " + base
                + " Emphasize dirt ground, tire tracks, cones, and cluttered but readable staging.",
                "Overcast material detail",
            ),
            (
                "gate_entry",
                "View from the site gate looking into the yard. " + base
                + " Gate gap in perimeter, vehicle lane leading to staging then build zone.",
                "Gate / lane narrative",
            ),
        ]
        out: list[DraftPrompt] = []
        for i in range(n):
            name, text, why = variants[i % len(variants)]
            # Light deterministic tweak per slot
            text = _clamp_prompt(text)
            out.append(DraftPrompt(name=f"{name}_{i}", text_prompt=text, rationale=why))
        return out

    def _expand_llm(self, brief: WorldBrief, n: int) -> list[DraftPrompt]:
        system = (
            "You write world-generation prompts for World Labs Marble. "
            "Return ONLY JSON: {\"drafts\":[{\"name\":str,\"text_prompt\":str,\"rationale\":str},...]}. "
            "Each text_prompt must be under 2000 characters, concrete, spatial, photoreal, "
            "and suitable for a navigable 3D construction/site world. "
            f"Produce exactly {n} diverse drafts."
        )
        user = {
            "brief": brief.model_dump(),
            "region_prior": _REGION_PRIORS.get(brief.region),
        }
        payload = {
            "model": self.cfg.openrouter_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user)},
            ],
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {self.cfg.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{self.cfg.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        data = _extract_json(content)
        drafts = data.get("drafts") or []
        out: list[DraftPrompt] = []
        for i, d in enumerate(drafts[:n]):
            out.append(
                DraftPrompt(
                    name=str(d.get("name") or f"llm_{i}"),
                    text_prompt=_clamp_prompt(str(d.get("text_prompt") or "")),
                    rationale=str(d.get("rationale") or "llm"),
                )
            )
        if len(out) < n:
            out.extend(self._expand_templates(brief, n - len(out)))
        return out[:n]


def _clamp_prompt(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def _extract_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return json.loads(content)
