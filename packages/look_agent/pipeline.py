from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from look_agent.brief import WorldBrief
from look_agent.config import LookConfig
from look_agent.credit_guard import CreditGuard
from look_agent.critic import CriticAgent
from look_agent.marble_client import MarbleClient
from look_agent.polish import polish_and_export
from look_agent.prompt_smith import PromptSmith


LogFn = Callable[[str], None]


@dataclass
class LookResult:
    job_dir: Path
    brief: dict[str, Any]
    drafts: list[dict[str, Any]]
    selected_prompt: str
    selected_score: float
    final_world: dict[str, Any] | None
    exports: dict[str, Any]
    credits: dict[str, Any]
    report_path: Path


def run_look_agent(
    brief: WorldBrief,
    *,
    cfg: LookConfig | None = None,
    model: str | None = None,
    export_mesh: bool = False,
    splat_resolution: str = "full_res",
    log: LogFn | None = None,
    # Legacy knobs kept so old CLI flags don't crash; ignored in one-shot mode.
    draft_count: int | None = None,
    run_plus: bool = True,
    draft_only: bool = False,
) -> LookResult:
    """
    Single agentic loop (one Marble generation):

      user brief
        → PromptSmith (one best prompt)
        → Critic (score / light refine gate)
        → one Marble generate (plus/full)
        → polish export (full_res PLY by default)
    """
    _ = (draft_count, run_plus, draft_only)  # deprecated multi-draft path
    cfg = cfg or LookConfig.from_env()
    cfg.require_marble_key()
    _log = log or (lambda m: print(m, flush=True))

    # One-shot quality model: plus by default, else full
    gen_model = model or cfg.plus_model or cfg.full_model

    job_dir = cfg.data_dir / "worlds" / brief.job_id()
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "brief.json").write_text(brief.model_dump_json(indent=2) + "\n", encoding="utf-8")

    with MarbleClient(cfg) as client:
        guard = CreditGuard(cfg, client)
        decision = guard.assess_oneshot(
            model=gen_model,
            want_mesh=export_mesh,
        )
        _log(f"credits: remaining={decision.remaining} budget={decision.budget}")
        for note in decision.notes:
            _log(f"  · {note}")

        if not decision.allow_generate:
            # Fall back to full model if plus is too expensive for budget
            if gen_model == cfg.plus_model and decision.allow_full:
                gen_model = cfg.full_model
                _log(f"CreditGuard: using {gen_model} instead of plus")
                decision = guard.assess_oneshot(model=gen_model, want_mesh=export_mesh)
            else:
                raise RuntimeError(
                    "Not enough credits/budget for one-shot generation. "
                    "Check https://platform.worldlabs.ai/billing or raise MARBLE_CREDIT_BUDGET."
                )

        # --- Agent step 1: PromptSmith → one prompt ---
        smith = PromptSmith(cfg)
        candidates = smith.expand(brief, n=1)
        prompt = candidates[0]
        _log(f"PromptSmith: crafted 1 prompt ({prompt.name})")

        # --- Agent step 2: Critic scores that prompt (no extra Marble calls) ---
        critic = CriticAgent(cfg)
        score = critic.score_prompt(brief, prompt)
        _log(f"Critic: score={score.score:.2f} reasons={score.reasons[:4]}")
        (job_dir / "prompts.json").write_text(
            json.dumps([{**asdict(prompt), "critic": asdict(score)}], indent=2) + "\n",
            encoding="utf-8",
        )

        # --- Agent step 3: one Marble world ---
        display = (brief.display_name or "Showcase World")[:64]
        _log(f"Generate: model={gen_model} (single call) …")
        op_start = client.generate_text_world(
            text_prompt=prompt.text_prompt,
            model=gen_model,
            display_name=display,
            seed=brief.seed,
            tags=(brief.tags or ["showcase", brief.region])[:10],
        )
        op = client.wait_operation(
            op_start["operation_id"],
            on_progress=lambda o: _progress(_log, gen_model, o),
        )
        final_world = op.get("response") or {}
        cost = (op.get("cost") or {}).get("total_credits")
        _log(
            f"  done world_id={final_world.get('world_id')} "
            f"url={final_world.get('world_marble_url')} cost={cost}"
        )

        draft_records = [
            {
                "name": prompt.name,
                "prompt": prompt.text_prompt,
                "rationale": prompt.rationale,
                "operation_id": op_start.get("operation_id"),
                "world_id": final_world.get("world_id"),
                "world_marble_url": final_world.get("world_marble_url"),
                "cost_credits": cost,
                "model": gen_model,
                "pre_score": score.score,
            }
        ]
        (job_dir / "drafts.json").write_text(json.dumps(draft_records, indent=2) + "\n", encoding="utf-8")

        # --- Agent step 4: polish / full_res export ---
        exports: dict[str, Any] = {}
        if final_world.get("world_id"):
            _log(f"Polish: exporting splat resolution={splat_resolution} …")
            try:
                exports = polish_and_export(
                    client,
                    world=final_world,
                    out_dir=job_dir / "exports",
                    export_mesh=export_mesh and decision.allow_mesh_export,
                    splat_resolution=splat_resolution,
                )
                if exports.get("exports", {}).get("ply"):
                    _log(
                        f"  ply: {exports['exports']['ply']} "
                        f"({exports['exports'].get('ply_resolution')})"
                    )
                else:
                    _log("  ply export unavailable — use world_marble_url for showcase")
            except Exception as exc:
                _log(f"  export warning (world still usable): {exc}")
                exports = {
                    "world_id": final_world.get("world_id"),
                    "world_marble_url": final_world.get("world_marble_url"),
                    "exports": {},
                    "error": str(exc),
                }

        remaining_after = client.get_credits()
        report = {
            "pipeline": "marble_oneshot",
            "job_id": brief.job_id(),
            "final_model": gen_model,
            "selected_prompt": prompt.text_prompt,
            "selected_score": score.score,
            "winner_draft": draft_records[0],
            "drafts": draft_records,
            "final_world": {
                "world_id": final_world.get("world_id"),
                "world_marble_url": final_world.get("world_marble_url"),
                "display_name": final_world.get("display_name"),
            },
            "exports": exports.get("exports") if exports else {},
            "credits": {
                "before_notes": decision.notes,
                "remaining_after": remaining_after,
            },
            "controls": {
                "mode": "oneshot",
                "model": gen_model,
                "splat_resolution": splat_resolution,
                "export_mesh": export_mesh,
            },
        }
        report_path = job_dir / "look_report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        _log(f"report: {report_path}")
        if final_world.get("world_marble_url"):
            _log(f"open in Marble: {final_world['world_marble_url']}")

        return LookResult(
            job_dir=job_dir,
            brief=brief.model_dump(),
            drafts=draft_records,
            selected_prompt=prompt.text_prompt,
            selected_score=score.score,
            final_world=final_world,
            exports=exports,
            credits={"remaining_after": remaining_after},
            report_path=report_path,
        )


def _progress(log: LogFn, label: str, op: dict[str, Any]) -> None:
    meta = op.get("metadata") or {}
    pct = meta.get("progress") or meta.get("percent") or meta.get("progress_percentage")
    if pct is not None:
        log(f"  [{label}] progress={pct}")
    elif int(time.time()) % 15 == 0:
        log(f"  [{label}] waiting… done={op.get('done')}")
