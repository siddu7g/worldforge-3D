from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from look_agent.config import LookConfig


class MarbleError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class MarbleClient:
    """Thin World Labs Marble API client."""

    def __init__(self, cfg: LookConfig, *, timeout: float = 60.0):
        cfg.require_marble_key()
        self.cfg = cfg
        self._client = httpx.Client(
            base_url=cfg.marble_base_url,
            headers={
                "WLT-Api-Key": cfg.marble_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MarbleClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        r = self._client.request(method, path, **kwargs)
        if r.status_code == 402:
            raise MarbleError(
                "Insufficient Marble API credits. Add credits at https://platform.worldlabs.ai/billing",
                status=402,
                body=_safe_json(r),
            )
        if r.status_code >= 400:
            raise MarbleError(
                f"Marble API {method} {path} failed: HTTP {r.status_code}: {r.text[:500]}",
                status=r.status_code,
                body=_safe_json(r),
            )
        data = _safe_json(r)
        if not isinstance(data, dict):
            raise MarbleError(f"Unexpected Marble response type: {type(data)}")
        return data

    def get_credits(self) -> float:
        data = self._request("GET", "/marble/v1/credits")
        return float(data.get("remaining_credits") or 0)

    def generate_text_world(
        self,
        *,
        text_prompt: str,
        model: str,
        display_name: str | None = None,
        seed: int | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "world_prompt": {"type": "text", "text_prompt": text_prompt[:2000]},
            "permission": {"public": False},
        }
        if display_name:
            body["display_name"] = display_name[:64]
        if seed is not None:
            body["seed"] = int(seed) & 0xFFFFFFFF
        if tags:
            body["tags"] = tags[:10]
        return self._request("POST", "/marble/v1/worlds:generate", json=body)

    def get_operation(self, operation_id: str) -> dict[str, Any]:
        return self._request("GET", f"/marble/v1/operations/{operation_id}")

    def wait_operation(
        self,
        operation_id: str,
        *,
        interval_s: float | None = None,
        timeout_s: float | None = None,
        on_progress: Any = None,
    ) -> dict[str, Any]:
        interval = interval_s if interval_s is not None else self.cfg.poll_interval_s
        timeout = timeout_s if timeout_s is not None else self.cfg.poll_timeout_s
        deadline = time.time() + timeout
        while True:
            op = self.get_operation(operation_id)
            if on_progress:
                on_progress(op)
            if op.get("done"):
                if op.get("error"):
                    err = op["error"]
                    raise MarbleError(
                        f"Marble operation failed: {err.get('message') or err}",
                        body=op,
                    )
                return op
            if time.time() > deadline:
                raise MarbleError(f"Timed out waiting for operation {operation_id}", body=op)
            time.sleep(interval)

    def get_world(self, world_id: str) -> dict[str, Any]:
        return self._request("GET", f"/marble/v1/worlds/{world_id}")

    def export_world(
        self,
        world_id: str,
        *,
        asset_type: str,
        fmt: str,
        resolution: str = "100k",
        mesh_variant: str = "textured",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"asset_type": asset_type, "format": fmt}
        if asset_type == "splats":
            body["resolution"] = resolution
        if asset_type == "mesh":
            body["mesh_variant"] = mesh_variant
        return self._request("POST", f"/marble/v1/worlds/{world_id}:export", json=body)

    def download_url(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Absolute GCS/CDN URLs must not use the API base_url client
        with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as r:
            if r.status_code >= 400:
                raise MarbleError(f"Download failed HTTP {r.status_code}: {url}")
            with dest.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return dest


def _safe_json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}
