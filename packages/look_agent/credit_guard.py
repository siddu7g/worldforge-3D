from __future__ import annotations

from dataclasses import dataclass

from look_agent.config import LookConfig
from look_agent.marble_client import MarbleClient


@dataclass
class CreditDecision:
    remaining: float
    budget: int
    allow_generate: bool
    allow_full: bool
    allow_plus: bool
    allow_mesh_export: bool
    notes: list[str]
    # legacy aliases used by older call sites
    allow_drafts: bool = False


class CreditGuard:
    """Gate Marble calls against remaining credits + session budget."""

    COST_DRAFT_TEXT = 230
    COST_FULL_TEXT = 1580
    COST_PLUS_TEXT_MAX = 3080
    COST_MESH = 3500

    def __init__(self, cfg: LookConfig, client: MarbleClient):
        self.cfg = cfg
        self.client = client

    def assess_oneshot(self, *, model: str, want_mesh: bool) -> CreditDecision:
        remaining = self.client.get_credits()
        budget = self.cfg.credit_budget
        notes: list[str] = [f"remaining_credits={remaining}", f"session_budget={budget}"]

        is_plus = "plus" in model
        gen_cost = self.COST_PLUS_TEXT_MAX if is_plus else self.COST_FULL_TEXT
        mesh_cost = self.COST_MESH if want_mesh else 0

        allow_full = remaining >= self.COST_FULL_TEXT and self.COST_FULL_TEXT <= budget
        allow_plus = remaining >= self.COST_FULL_TEXT and gen_cost <= budget
        # Plus may bill variable up to ~3080; require headroom vs remaining wallet too
        if is_plus and remaining < self.COST_FULL_TEXT:
            allow_plus = False
        allow_generate = (allow_plus if is_plus else allow_full)
        allow_mesh = want_mesh and remaining >= mesh_cost and (gen_cost + mesh_cost) <= max(budget, mesh_cost)

        if not allow_generate:
            notes.append(
                f"blocked_generate: need ~{gen_cost} credits within budget for model={model}"
            )
        if want_mesh and not allow_mesh:
            notes.append("blocked_mesh: HQ mesh export is 3500 credits")

        return CreditDecision(
            remaining=remaining,
            budget=budget,
            allow_generate=allow_generate,
            allow_full=allow_full,
            allow_plus=allow_plus,
            allow_mesh_export=allow_mesh,
            allow_drafts=allow_generate,
            notes=notes,
        )
