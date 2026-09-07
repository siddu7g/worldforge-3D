from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env() -> None:
    """Load `.env` from repo root if present (does not override existing env)."""
    load_dotenv(_repo_root() / ".env", override=False)


@dataclass(frozen=True)
class LookConfig:
    marble_api_key: str
    marble_base_url: str
    credit_budget: int
    draft_model: str
    full_model: str
    plus_model: str
    draft_count: int
    poll_interval_s: float
    poll_timeout_s: float
    openrouter_api_key: str | None
    openrouter_base_url: str
    openrouter_model: str
    data_dir: Path

    @classmethod
    def from_env(cls) -> LookConfig:
        load_env()
        key = (os.environ.get("MARBLE_API_KEY") or "").strip()
        return cls(
            marble_api_key=key,
            marble_base_url=(os.environ.get("MARBLE_BASE_URL") or "https://api.worldlabs.ai").rstrip("/"),
            credit_budget=int(os.environ.get("MARBLE_CREDIT_BUDGET") or "5000"),
            draft_model=os.environ.get("MARBLE_DRAFT_MODEL") or "marble-1.0-draft",
            full_model=os.environ.get("MARBLE_FULL_MODEL") or "marble-1.1",
            plus_model=os.environ.get("MARBLE_PLUS_MODEL") or "marble-1.1-plus",
            draft_count=max(1, int(os.environ.get("MARBLE_DRAFT_COUNT") or "3")),
            poll_interval_s=float(os.environ.get("MARBLE_POLL_INTERVAL_S") or "5"),
            poll_timeout_s=float(os.environ.get("MARBLE_POLL_TIMEOUT_S") or "900"),
            openrouter_api_key=(os.environ.get("OPENROUTER_API_KEY") or "").strip() or None,
            openrouter_base_url=(os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/"),
            openrouter_model=os.environ.get("OPENROUTER_MODEL") or "openai/gpt-4o-mini",
            data_dir=Path(os.environ.get("APP_DATA_DIR") or "./data").expanduser().resolve(),
        )

    def require_marble_key(self) -> None:
        if not self.marble_api_key:
            raise RuntimeError(
                "MARBLE_API_KEY is missing. Paste it into /home/sidg/3D/.env "
                "(see .env.example). Get a key at https://platform.worldlabs.ai/api-keys"
            )
