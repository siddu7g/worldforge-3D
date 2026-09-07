from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from look_agent.brief import WorldBrief
from look_agent.config import LookConfig
from look_agent.prompt_smith import DraftPrompt


@dataclass(frozen=True)
class DraftScore:
    name: str
    score: float
    reasons: list[str]


class CriticAgent:
    """Score draft prompts / worlds against the user brief."""

    def __init__(self, cfg: LookConfig):
        self.cfg = cfg

    def score_prompt(self, brief: WorldBrief, draft: DraftPrompt) -> DraftScore:
        if self.cfg.openrouter_api_key:
            try:
                return self._score_llm(brief, draft)
            except Exception:
                pass
        return self._score_heuristic(brief, draft)

    def pick_best(self, brief: WorldBrief, drafts: list[DraftPrompt]) -> tuple[DraftPrompt, list[DraftScore]]:
        scores = [self.score_prompt(brief, d) for d in drafts]
        best_idx = max(range(len(scores)), key=lambda i: scores[i].score)
        return drafts[best_idx], scores

    def _score_heuristic(self, brief: WorldBrief, draft: DraftPrompt) -> DraftScore:
        text = draft.text_prompt.lower()
        reasons: list[str] = []
        score = 0.4

        # Keyword coverage from brief
        tokens = [t for t in re.split(r"[^a-z0-9]+", brief.prompt.lower()) if len(t) > 3]
        hits = sum(1 for t in set(tokens) if t in text)
        if tokens:
            cov = hits / max(len(set(tokens)), 1)
            score += 0.35 * cov
            reasons.append(f"brief_token_coverage={cov:.2f}")

        for item in brief.must_include:
            if item.lower() in text:
                score += 0.05
                reasons.append(f"includes:{item}")
            else:
                score -= 0.05
                reasons.append(f"missing:{item}")

        for bad in brief.avoid:
            if bad.lower() in text:
                score -= 0.1
                reasons.append(f"avoid_hit:{bad}")

        for cue in ("construction", "scaffold", "staging", "perimeter", "photoreal", "eye-level"):
            if cue in text:
                score += 0.02

        # Prefer concrete spatial language
        if any(w in text for w in ("lane", "yard", "gate", "ground", "building")):
            score += 0.05
            reasons.append("spatial_cues")

        score = max(0.0, min(1.0, score))
        return DraftScore(name=draft.name, score=score, reasons=reasons)

    def _score_llm(self, brief: WorldBrief, draft: DraftPrompt) -> DraftScore:
        system = (
            "Score how well a Marble world prompt matches a user brief for a showcase 3D world. "
            "Return ONLY JSON: {\"score\":0-1,\"reasons\":[str,...]}."
        )
        user = {"brief": brief.model_dump(), "draft": {"name": draft.name, "text_prompt": draft.text_prompt}}
        headers = {
            "Authorization": f"Bearer {self.cfg.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.cfg.openrouter_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user)},
            ],
            "temperature": 0.0,
        }
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{self.cfg.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        data = json.loads(content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
        return DraftScore(
            name=draft.name,
            score=float(data.get("score", 0.5)),
            reasons=[str(x) for x in (data.get("reasons") or [])],
        )
