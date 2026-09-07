"""CLI: Local USD + Marble LookAgent showcase pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load repo .env early so CLI and packages see keys
_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env", override=False)


def _data_dir() -> Path:
    return Path(os.environ.get("APP_DATA_DIR", "./data")).expanduser().resolve()


def cmd_generate_local(args: argparse.Namespace) -> int:
    from asset_registry import load_pack
    from isaac_ready import isaac_sim_path, isaac_sim_sh
    from layout import LayoutComposer
    from sim_qa import run_sim_qa
    from site_spec import SiteSpec
    from usd_compose import compose_site

    if args.spec:
        raw = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        spec = SiteSpec.model_validate(raw)
    else:
        spec = SiteSpec(
            region=args.region,
            seed=args.seed,
            plot_m=(args.plot_w, args.plot_d),
            density=args.density,
            include_scaffolding=not args.no_scaffolding,
            pipeline="local",
        )

    pack = load_pack(spec.region)
    placements = LayoutComposer().compose(spec, pack)
    out_dir = _data_dir() / spec.site_id()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sitespec.json").write_text(spec.model_dump_json(indent=2) + "\n", encoding="utf-8")

    site_usd = compose_site(spec, placements, out_dir)
    qa = run_sim_qa(site_usd, out_dir / "qa_report.json")

    print(f"site_id:   {spec.site_id()}")
    print(f"region:    {spec.region} (pack {pack.version})")
    print(f"prims:     {len(placements)}")
    print(f"site.usd:  {site_usd}")
    print(f"qa_report: {out_dir / 'qa_report.json'}  pass={qa['pass']}")
    print()
    print("Open in Isaac Sim:")
    print(f"  {isaac_sim_sh()} {site_usd}")
    print(f"  # or: cd {isaac_sim_path()} && ./isaac-sim.sh {site_usd}")
    return 0 if qa["pass"] else 1


def cmd_credits(args: argparse.Namespace) -> int:
    from look_agent.config import LookConfig
    from look_agent.marble_client import MarbleClient

    cfg = LookConfig.from_env()
    try:
        cfg.require_marble_key()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    with MarbleClient(cfg) as client:
        remaining = client.get_credits()
    print(f"remaining_credits: {remaining}")
    print(f"session_budget:    {cfg.credit_budget}")
    print("Buy API credits:    https://platform.worldlabs.ai/billing")
    return 0


def cmd_world(args: argparse.Namespace) -> int:
    from look_agent import WorldBrief, run_look_agent
    from look_agent.config import LookConfig

    prompt = args.prompt
    if args.brief:
        raw = json.loads(Path(args.brief).read_text(encoding="utf-8"))
        brief = WorldBrief.model_validate(raw)
        if prompt:
            brief.prompt = prompt
    else:
        if not prompt:
            print("Provide --prompt or --brief", file=sys.stderr)
            return 2
        brief = WorldBrief(
            prompt=prompt,
            region=args.region,
            display_name=args.name,
            mood=args.mood,
            must_include=args.must_include or [],
            avoid=args.avoid or [],
            seed=args.seed,
            tags=args.tag or [],
        )

    cfg = LookConfig.from_env()
    model = args.model
    if args.draft_only:
        model = cfg.draft_model
    elif args.no_plus and not args.model:
        model = cfg.full_model

    try:
        result = run_look_agent(
            brief,
            cfg=cfg,
            model=model,
            export_mesh=args.export_mesh,
            splat_resolution=args.resolution,
        )
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print()
    print(f"job_dir:   {result.job_dir}")
    print(f"report:    {result.report_path}")
    if result.final_world:
        print(f"world_id:  {result.final_world.get('world_id')}")
        print(f"marble:    {result.final_world.get('world_marble_url')}")
    if result.exports.get("exports"):
        for k, v in result.exports["exports"].items():
            print(f"export_{k}: {v}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Re-export PLY/GLB for an existing Marble world_id (no regeneration)."""
    from look_agent.config import LookConfig
    from look_agent.marble_client import MarbleClient
    from look_agent.polish import polish_and_export

    cfg = LookConfig.from_env()
    try:
        cfg.require_marble_key()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else (_data_dir() / "worlds" / f"export_{args.world_id[:8]}")
    with MarbleClient(cfg) as client:
        world = client.get_world(args.world_id)
        result = polish_and_export(
            client,
            world=world,
            out_dir=out_dir,
            export_mesh=args.export_mesh,
            splat_resolution=args.resolution,
        )
    print(f"out:    {out_dir}")
    print(f"marble: {world.get('world_marble_url')}")
    for k, v in (result.get("exports") or {}).items():
        print(f"{k}: {v}")
    return 0 if result.get("exports") else 1


def cmd_marble_to_isaac(args: argparse.Namespace) -> int:
    from isaac_ready import build_open_command, convert_ply_to_isaac_stage

    out_dir = Path(args.out_dir) if args.out_dir else (_data_dir() / "gaussian" / (args.scene_name or Path(args.ply).stem))
    try:
        view_usda = convert_ply_to_isaac_stage(
            Path(args.ply),
            out_dir=out_dir,
            profile_name=args.profile,
            scene_name=args.scene_name,
        )
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"out_dir:   {out_dir}")
    print(f"view_usda: {view_usda}")
    print("open in Isaac:")
    print(f"  {build_open_command(view_usda)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m apps.api.cli", description="Agentic world builder CLI")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Local pipeline → layered site.usd")
    g.add_argument("--spec", type=str, default=None)
    g.add_argument("--region", default="americas", choices=["asia", "europe", "americas"])
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--plot-w", type=float, default=40.0)
    g.add_argument("--plot-d", type=float, default=60.0)
    g.add_argument("--density", default="low", choices=["low", "med"])
    g.add_argument("--no-scaffolding", action="store_true")
    g.set_defaults(func=cmd_generate_local)

    w = sub.add_parser("world", help="One-shot LookAgent → single Marble world (full quality)")
    w.add_argument("--prompt", type=str, default=None, help="Natural language world brief")
    w.add_argument("--brief", type=str, default=None, help="Path to WorldBrief JSON")
    w.add_argument("--name", type=str, default=None, help="Display name (max 64)")
    w.add_argument("--region", default="americas", choices=["asia", "europe", "americas", "generic"])
    w.add_argument("--mood", type=str, default=None)
    w.add_argument("--seed", type=int, default=None)
    w.add_argument("--must-include", action="append", default=[])
    w.add_argument("--avoid", action="append", default=[])
    w.add_argument("--tag", action="append", default=[])
    w.add_argument(
        "--model",
        default=None,
        choices=["marble-1.0-draft", "marble-1.0", "marble-1.1", "marble-1.1-plus"],
        help="Marble model (default: marble-1.1-plus)",
    )
    w.add_argument(
        "--resolution",
        default="full_res",
        choices=["100k", "500k", "full_res"],
        help="PLY export resolution (default: full_res)",
    )
    w.add_argument("--export-mesh", action="store_true", help="Also export HQ GLB (3500 credits)")
    # Deprecated flags kept for compatibility
    w.add_argument("--drafts", type=int, default=None, help=argparse.SUPPRESS)
    w.add_argument("--draft-only", action="store_true", help=argparse.SUPPRESS)
    w.add_argument("--no-plus", action="store_true", help=argparse.SUPPRESS)
    w.set_defaults(func=cmd_world)

    e = sub.add_parser("export", help="Export PLY/GLB for an existing Marble world_id")
    e.add_argument("--world-id", required=True)
    e.add_argument("--out", type=str, default=None, help="Output directory")
    e.add_argument("--resolution", default="100k", choices=["100k", "500k", "full_res"])
    e.add_argument("--export-mesh", action="store_true")
    e.set_defaults(func=cmd_export)

    m = sub.add_parser("marble-to-isaac", help="Convert Marble PLY export into an Isaac-openable NuRec stage")
    m.add_argument("--ply", required=True, help="Path to Marble/World Labs PLY export")
    m.add_argument(
        "--profile",
        default="fullish",
        choices=["100k", "fullish", "500k"],
        help="Sanitize/downsample profile",
    )
    m.add_argument("--out-dir", default=None, help="Output directory (default under APP_DATA_DIR/gaussian)")
    m.add_argument("--scene-name", default=None, help="Optional scene name for generated files")
    m.set_defaults(func=cmd_marble_to_isaac)

    c = sub.add_parser("credits", help="Show Marble API remaining credits")
    c.set_defaults(func=cmd_credits)
    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
