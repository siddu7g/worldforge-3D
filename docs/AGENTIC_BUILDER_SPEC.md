# Agentic Construction Site Builder — Spec (Draft v0)

**Product spine:** Regional construction sites → Isaac-ready USD  
**Secondary surface:** Marble look / demo worlds (credit-gated)  
**Host:** Linux 24.04 · NVIDIA RTX 4070 · Isaac Sim at `~/isaacsim` (5.1)

---

## 1. Goal

From a `SiteSpec`, generate a simple construction-site 3D world that:

1. Exports as layered **OpenUSD** openable in **NVIDIA Isaac Sim**
2. Is **explorable** (viewport camera + lights)
3. Supports **regional packs**: `asia` | `europe` | `americas`
4. Offers a UI toggle: **Local (procedural)** vs **Marble (generative demo)**
5. Runs agentic QA + optional polish without burning credits by default

**v0 success:** `seed=42`, `region=americas`, `plot_m=[40,60]` → `site.usd` opens in Isaac; SimQA pass; optional browser GLB preview.

---

## 2. Non-goals (v0)

- Robot policy training / teleop
- Full BIM / Revit import
- Workers, crowds, deformable mud/debris
- Vehicle drivetrains
- Merging Marble mesh into procedural USD as one physics scene
- In-browser Isaac

---

## 3. Pipelines

### 3.1 Local (default — product)

```
SiteSpec → LayoutComposer → layered USD → SimQA → SemanticTagger → [local polish]
```

No Marble. Marginal cost ≈ local GPU/CPU.

### 3.2 Marble (optional — demo / look)

```
SiteSpec → LookAgent (mini drafts → VLM pick → one plus call)
        → export PLY + GLB collider
        → local polish (mesh / V-HACD / textures)
        → Isaac import path (NuRec USDZ + GLB)
        → SimQA-ish checks on collider
        → CreditGuard escalation only if structural fail + budget left
```

Marble does **not** refine an existing USD. It generates a **parallel** world. Local polish agents operate on Marble **exports**.

---

## 4. Agent graph

| Agent | Role | Paid API |
|-------|------|----------|
| **SitePlanner** | Build / validate `SiteSpec` from UI or prompt | No |
| **LayoutComposer** | Place pack assets → layered USD | No |
| **SimQA** | Isaac/pxr: rigid settle, eye-height raycast, axis/scale checks | No |
| **SemanticTagger** | Qwen3-VL (or configured VLM) labels on renders | Local endpoint |
| **LocalPolish** | Hole-fill, decimate, V-HACD, texture touch-ups | No |
| **LookAgent** | Marble draft/score/one-shot plus | Marble credits |
| **CreditGuard** | Poll credits; allow LookAgent escalate only | Read-only |

**Rule:** LookAgent never replaces LayoutComposer collision geometry for the product path.

---

## 5. SiteSpec (contract)

```json
{
  "region": "americas",
  "seed": 42,
  "plot_m": [40, 60],
  "phases": ["structure"],
  "zones": ["excavation", "staging", "build", "perimeter"],
  "density": "low",
  "include_scaffolding": true,
  "pipeline": "local"
}
```

| Field | Values | Notes |
|-------|--------|-------|
| `region` | `asia` \| `europe` \| `americas` | Selects asset pack + layout priors |
| `seed` | int | Deterministic placement |
| `plot_m` | `[width, depth]` meters | Site bounds |
| `phases` | e.g. `structure` | v0: single phase |
| `zones` | list | Layout partitions |
| `density` | `low` \| `med` | Prop count priors |
| `pipeline` | `local` \| `marble` | UI toggle |

Regional difference lives in **packs + priors**, not forked composers.

---

## 6. Regional packs (v0 minimal)

Per region, at least:

| Asset class | Semantic label | v0 geometry |
|-------------|----------------|-------------|
| Ground | `ground` | Plane / thin box |
| Building footprint | `building` | Box |
| Scaffold | `scaffold` | Box tower / simple frame |
| Barrier | `barrier` | Thin boxes |
| Material pile | `material_pile` | Low boxes / cylinders |
| Gate gap | `gate` | Empty perimeter segment |

**Priors (examples):**

- **Asia:** higher density, narrower lanes, compact staging  
- **Europe:** modular scaffold spacing, stricter perimeter  
- **Americas:** wider vehicle lanes, larger staging yard  

v0 may use primitives + distinct materials per region; swap real meshes later without changing prim paths.

---

## 7. USD / Isaac contract

**Stage**

- `upAxis = Z`
- `metersPerUnit = 1.0`
- Default prim `/World`

**Layers**

```
artifacts/{site_id}/
  site.usd                 # composition root
  payloads/geometry.usd
  payloads/physics.usd
  payloads/semantics.usd
  payloads/lights_cameras.usd
  qa_report.json
  preview.glb              # optional web
```

**Physics (v0)**

- Static site geometry: `PhysicsCollisionAPI` (no rigid body on buildings/scaffold)
- Approximation: `boundingCube` or `convexHull`
- Later: V-HACD for complex props

**Explore defaults**

- Dome / distant light
- Perspective camera at humanoid eye height (~1.6 m), looking at build zone

**Isaac install**

```
ISAAC_SIM_PATH=/home/sidg/isaacsim
# Use: $ISAAC_SIM_PATH/python.sh for headless scripts
# Launch UI: $ISAAC_SIM_PATH/isaac-sim.sh
```

Hardware note: RTX 4070 laptop — keep scenes light (low poly, few lights); prefer headless SimQA scripts over full RTX quality for CI loops.

---

## 8. Backend API (draft)

Base: FastAPI · artifacts on disk under `APP_DATA_DIR`

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/sites` | Create job from SiteSpec |
| `GET` | `/v1/sites/{id}` | Status + artifact URLs + QA |
| `GET` | `/v1/packs` | List regions / asset classes |
| `GET` | `/v1/health` | App + optional Isaac path check |
| `GET` | `/v1/credits` | Marble credits (if configured) |

`POST /v1/sites` body = SiteSpec. Response: `{ "id", "status", "pipeline" }`.

Worker runs selected pipeline asynchronously.

---

## 9. Frontend (v0 thin)

Single page:

1. SiteSpec form (region, seed, plot, density)
2. Mode toggle: **Local** | **Marble**
3. Generate → poll job status
4. Links: download `site.usd`, `qa_report.json`, `preview.glb`
5. Marble mode: show credits used / remaining (if API available)

No in-app Isaac. Show copy-paste: open folder in Isaac Sim.

---

## 10. Environment (`.env`)

```bash
APP_DATA_DIR=./data
DEFAULT_PIPELINE=local

ISAAC_SIM_PATH=/home/sidg/isaacsim

# Marble mode only
MARBLE_API_KEY=
MARBLE_BASE_URL=https://api.worldlabs.ai
MARBLE_CREDIT_BUDGET=5000
MARBLE_MINI_MODEL=marble-0.1-mini
MARBLE_PLUS_MODEL=marble-0.1-plus

# SemanticTagger / draft scorer (local)
VLM_BASE_URL=http://localhost:8000/v1
VLM_MODEL=qwen3-vl
```

Local pipeline must run with `MARBLE_API_KEY` unset.

---

## 11. SimQA checks (v0)

1. Stage loads; default prim exists  
2. `upAxis=Z`, `metersPerUnit=1`  
3. Drop N probe cubes from z=5; none fall below ground −0.5 m within T seconds  
4. Raycast grid at z=1.6 m; flag large unintended voids inside build/staging AABB  
5. Write `qa_report.json` with pass/fail + metrics  

Prefer Isaac headless via `python.sh`. If Isaac unavailable, run subset with `usd-core` only and mark `isaac: skipped`.

---

## 12. Marble LookAgent economics (optional)

1. 4–5 mini drafts (~150–250 credits each)  
2. VLM scores vs SiteSpec criteria → pick prompt+seed  
3. One plus generation (~1500–1600 credits)  
4. Local polish forever  
5. Escalate only if structural fail **and** budget left  

Do not use Marble as the definition of a construction site for the product path.

---

## 13. Repo layout (target)

```
3D/
  docs/AGENTIC_BUILDER_SPEC.md    # this file
  prompts/START_BUILD.md          # agent kickoff prompt
  .env.example
  apps/
    api/                          # FastAPI
    web/                          # thin UI
  packages/
    site_spec/
    asset_registry/
    layout/
    usd_compose/
    isaac_ready/
    sim_qa/
    look_agent/                   # Marble path
    semantic_tagger/
  packs/
    americas/
    europe/
    asia/
  data/                           # artifacts (gitignored)
```

---

## 14. Build order (weeks)

1. `site_spec` + `asset_registry` (americas primitives)  
2. `layout` + `usd_compose` → first `site.usd`  
3. Open in Isaac manually; fix axis/scale  
4. `sim_qa` via `~/isaacsim/python.sh`  
5. FastAPI + thin web (Local mode only)  
6. europe/asia pack material variants  
7. SemanticTagger  
8. LookAgent + CreditGuard (Marble) behind toggle  

---

## 15. Acceptance checklist (v0)

- [ ] `pipeline=local` produces layered USD under `data/`  
- [ ] File opens in `~/isaacsim` without import errors  
- [ ] SimQA writes pass on probe settle  
- [ ] Changing `region` changes materials/priors, same prim path scheme  
- [ ] UI can submit Local job and download artifacts  
- [ ] Marble mode disabled or clearly gated without API key  
