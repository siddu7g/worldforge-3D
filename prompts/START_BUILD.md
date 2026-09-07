# Kickoff prompt — Agentic Construction Site Builder

Copy everything below the line into a new Cursor agent chat (workspace: `/home/sidg/3D`).

---

You are building the **v0 Agentic Construction Site Builder** in this repo.

## Read first
- Spec: `docs/AGENTIC_BUILDER_SPEC.md` (source of truth)
- Isaac Sim: `/home/sidg/isaacsim` (Linux 24.04, RTX 4070). Use `$ISAAC_SIM_PATH/python.sh` for headless scripts and `isaac-sim.sh` for UI.

## Product rules
1. Default pipeline is **Local**: SiteSpec → LayoutComposer → layered USD → SimQA. **No Marble** in the critical path.
2. Marble is an **optional parallel LookAgent** behind a UI toggle; it does not refine USD — it generates a separate world from exports + local polish.
3. Regional packs (`asia` / `europe` / `americas`) differ by data + layout priors, not forked engines.
4. USD contract: Z-up, metersPerUnit=1, layered `site.usd` + geometry/physics/semantics/lights payloads, static CollisionAPI for site geometry.

## Your first milestone (do this now)
Scaffold the monorepo and deliver a **working Local path**:

1. Create package layout from the spec (`packages/*`, `apps/api`, `packs/americas`, `.env.example`, gitignore `data/`).
2. Implement `SiteSpec` (pydantic) + americas primitive pack.
3. Implement LayoutComposer + usd_compose (`usd-core`) that writes a deterministic `site.usd` for `seed=42`, `region=americas`, `plot_m=[40,60]`.
4. Add a CLI: `python -m apps.api.cli generate --spec ...` (or equivalent) that outputs under `data/`.
5. Document the exact command to open the USD in Isaac Sim.
6. Do **not** implement Marble, web UI, or SemanticTagger yet unless Local USD opens cleanly.

## Constraints
- Prefer small, working slices over architecture theater.
- Keep poly count low (laptop 4070).
- If Isaac headless SimQA is hard, ship USD first and a stub `qa_report.json`, then add SimQA.

Start by reading the spec, then scaffold and generate the first americas `site.usd`.
