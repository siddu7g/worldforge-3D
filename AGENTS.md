# AGENTS

This repository is an open-source reference for generating showcase construction worlds and moving them into NVIDIA Isaac Sim.

## Product Intent

- Primary surface: `Marble -> showcase world`
- Secondary surface: `Local USD -> structured Isaac scene`
- Do not present the Local USD pipeline as photoreal. It is a deterministic layout scaffold.

## Core Rules

1. Keep the repo single-root and pushable to GitHub.
2. Never commit secrets. Users supply their own `MARBLE_API_KEY` and optional `OPENROUTER_API_KEY` in `.env`.
3. Generated outputs belong under `data/` and stay gitignored.
4. Prefer small, working slices over speculative architecture.

## Important Paths

- `apps/api/cli.py`: main CLI
- `packages/look_agent/`: one-shot Marble generation pipeline
- `packages/isaac_ready/gaussian_pipeline.py`: Marble PLY -> Isaac NuRec conversion helper
- `docs/MARBLE_TO_ISAAC.md`: source of truth for the conversion flow
- `docs/AGENTIC_BUILDER_SPEC.md`: product spec

## Marble -> Isaac Expectations

- Open `view.usda`, not `default.usda`
- Use Isaac's `open_gaussian.sh` launcher so `--/UJITSO/geometry=true` is set
- Marble web PLYs may contain non-finite opacities; sanitize before conversion
- `fullish` is the best default profile for RTX 4070 laptop-class GPUs

## When Modifying This Repo

- Preserve the one-shot `world` generation behavior unless the user explicitly asks for multi-draft behavior
- Keep examples runnable from a fresh clone
- Prefer documenting exact commands over vague prose
- Verify the CLI after changes
