# Agentic Construction Site Builder

Open-source reference for building showcase construction worlds with World Labs Marble and moving them into NVIDIA Isaac Sim.

Two supported paths:

- `Marble -> Isaac`: the showcase path
- `Local USD`: deterministic site-layout scaffold for Isaac

## Repo Name Ideas

- `siteforge-ai`
- `worldbuild-isaac`
- `marble-site-pipeline`

## What This Repo Does

### 1. One-shot Marble world generation

`brief -> PromptSmith -> Critic -> one Marble call -> export`

### 2. Local deterministic USD generation

`SiteSpec -> LayoutComposer -> layered USD -> SimQA stub`

### 3. Marble PLY to Isaac conversion

This repo now includes the fixes needed to make Marble splat exports open reliably in Isaac:

- sanitize bad PLY opacity values
- run bundled `3dgrut`
- extract the USDZ
- write a stable `view.usda`

## Quick Start

```bash
cd /home/sidg/3D
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Add your own keys to `.env`:

```bash
MARBLE_API_KEY=your_world_labs_api_key
OPENROUTER_API_KEY=your_openrouter_key   # optional
```

Get the Marble API key from [platform.worldlabs.ai/api-keys](https://platform.worldlabs.ai/api-keys).  
Buy API credits at [platform.worldlabs.ai/billing](https://platform.worldlabs.ai/billing).

## Main Commands

### Check credits

```bash
python -m apps.api.cli credits
```

### Generate a Marble world

```bash
python -m apps.api.cli world \
  --prompt "Indoor house under construction, walkable rooms, exposed studs" \
  --name "Indoor House" \
  --region americas \
  --seed 7
```

### Re-export a world's PLY or GLB

```bash
python -m apps.api.cli export \
  --world-id <world_id> \
  --resolution full_res
```

### Convert a Marble PLY into an Isaac-openable stage

```bash
python -m apps.api.cli marble-to-isaac \
  --ply /path/to/world_full_res.ply \
  --profile fullish \
  --scene-name indoor-house
```

Then open the generated `view.usda` in Isaac:

```bash
/home/sidg/isaacsim/sim/open_gaussian.sh \
  /absolute/path/to/data/gaussian/indoor-house/stage/view.usda
```

### Generate the Local USD scaffold

```bash
python -m apps.api.cli generate --spec examples/americas_s42.json
```

## Profiles For Isaac Conversion

- `100k`: safest
- `fullish`: best default on RTX 4070 laptop-class GPUs
- `500k`: densest, heaviest

## Output Layout

### Marble generation

```text
data/worlds/<job_id>/
  brief.json
  prompts.json
  drafts.json
  look_report.json
  exports/
    world_<resolution>.ply
    world_mesh.glb          # optional
```

### Marble to Isaac conversion

```text
data/gaussian/<scene-name>/
  <scene-name>.ply
  <scene-name>.usdz
  conversion_summary.txt
  stage/
    default.usda
    gauss.usda
    <scene-name>.nurec
    view.usda
```

Open `stage/view.usda`, not `default.usda`.

## Isaac Notes

- Isaac Sim is expected at `ISAAC_SIM_PATH` in `.env`
- the launcher must pass `--/UJITSO/geometry=true`
- Marble's web viewer will still look better than Isaac NuRec
- splats are a showcase/render path, not a perfect mesh reconstruction path

## Docs

- Spec: `docs/AGENTIC_BUILDER_SPEC.md`
- Marble to Isaac guide: `docs/MARBLE_TO_ISAAC.md`
- Agent instructions: `AGENTS.md`
