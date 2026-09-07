# Marble To Isaac

This repo supports two paths:

- `Local USD`: procedural site layout for Isaac
- `Marble -> Isaac`: showcase world from World Labs Marble exported as Gaussian PLY, then converted into an Isaac-openable NuRec stage

## Requirements

- Linux
- NVIDIA GPU
- Isaac Sim installed at `ISAAC_SIM_PATH` (default: `/home/sidg/isaacsim`)
- World Labs / Marble API key in `.env` if you want to generate worlds from this repo

## Why This Guide Exists

Raw Marble PLY exports do not always open cleanly in Isaac Sim:

- some Marble web PLYs contain non-finite opacity values
- stock `default.usda` layouts can nest the volume incorrectly for manual opens
- opening the wrong file can produce gray screens or 0 FPS

This repo bakes in the fixes that worked in practice.

## End-To-End

### 1. Generate a world

```bash
source .venv/bin/activate
python -m apps.api.cli world \
  --prompt "Indoor house under construction, walkable rooms, exposed studs" \
  --name "Indoor House" \
  --region americas \
  --seed 7
```

This writes a Marble PLY under `data/worlds/.../exports/`.

### 2. Convert PLY to Isaac stage

```bash
python -m apps.api.cli marble-to-isaac \
  --ply /path/to/world_full_res.ply \
  --profile fullish
```

Profiles:

- `100k`: safest for weaker GPUs
- `fullish`: denser, good default on RTX 4070 laptop
- `500k`: highest-density path, heaviest

This writes:

```text
data/gaussian/<scene-name>/
  <scene-name>.ply
  <scene-name>.usdz
  stage/
    default.usda
    gauss.usda
    <scene-name>.nurec
    view.usda
```

### 3. Open the fixed stage

```bash
/home/sidg/isaacsim/sim/open_gaussian.sh \
  /absolute/path/to/data/gaussian/<scene-name>/stage/view.usda
```

Or use the command printed by `marble-to-isaac`.

In Isaac:

1. Select `/World/gauss`
2. Press `F`
3. Use `Stage Lights`

Open `view.usda`, not `default.usda`.

## Recommended Commands

### Default

```bash
python -m apps.api.cli marble-to-isaac \
  --ply /home/sidg/Downloads/project-indoor-house-build.ply \
  --profile fullish \
  --scene-name indoor-house
```

### Higher Density

```bash
python -m apps.api.cli marble-to-isaac \
  --ply /home/sidg/Downloads/project-indoor-house-build.ply \
  --profile 500k \
  --scene-name indoor-house-500k
```

## What The Repo Fixes Automatically

The conversion helper:

1. sanitizes Marble PLY data
2. clips bad opacity values
3. removes normals Isaac does not need
4. optionally downsamples for GPU-friendly density
5. runs Isaac's bundled `3dgrut` converter
6. extracts the USDZ
7. writes a stable `view.usda` that should be opened in Isaac

## Troubleshooting

### Gray screen

Usually means one of:

- you opened `default.usda` instead of `view.usda`
- you opened the asset by drag-and-drop into an existing stage instead of `File -> Open`
- `--/UJITSO/geometry=true` was not set

Use `open_gaussian.sh`.

### 0 FPS

Try:

- `--profile 100k`
- close other GPU-heavy apps
- fully restart Isaac Sim

### Looks sparse or streaky

That is a limitation of splat-to-NuRec rendering relative to Marble's web viewer.
Try `fullish` or `500k`.

### It still does not look like Marble web

That is expected. Marble's web viewer is the best showcase surface. Isaac is the integration surface.

If you need a more solid look in Isaac, export a Marble mesh GLB and treat it as a separate downstream asset.
