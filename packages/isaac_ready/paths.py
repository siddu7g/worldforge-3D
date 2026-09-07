from __future__ import annotations

import os
from pathlib import Path


def isaac_sim_path() -> Path:
    return Path(os.environ.get("ISAAC_SIM_PATH", "/home/sidg/isaacsim")).expanduser()


def isaac_python() -> Path:
    return isaac_sim_path() / "python.sh"


def isaac_sim_sh() -> Path:
    return isaac_sim_path() / "isaac-sim.sh"
