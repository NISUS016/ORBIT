"""n8n_client.py — everything related to talking to the n8n API + webhooks."""

import asyncio
import json
from typing import Any

import httpx

from config import N8N_TIMEOUT, get_n8n_api_key, get_n8n_base_url


def unwrap(data: Any) -> Any:
    """n8n webhooks return a list by default — take the first item."""
    if isinstance(data, list):
        return data[0] if data else {}
    return data


async def call_webhook(
    url: str, task: str, model: str, timeout: float = 120.0
) -> tuple[str, int]:
    """POST to an n8n webhook and return (result, http_status)."""
    async with httpx.AsyncClient(timeout=timeout) as http:
        resp = await http.post(url, json={"task": task, "model": model})
        try:
            data = unwrap(resp.json())
        except (json.JSONDecodeError, ValueError):
            return f"n8n error (HTTP {resp.status_code}): {resp.text[:200]}", resp.status_code
        return data.get("result", str(data)), resp.status_code


class N8NClient:
    """Thin wrapper over the n8n REST API used by the factory.
    Base URL/key are resolved live so settings changes apply immediately."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or get_n8n_base_url()).rstrip("/")
        self.api_key = api_key if api_key is not None else get_n8n_api_key()
        self.headers = {"X-N8N-API-KEY": self.api_key, "Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def create_workflow(self, workflow: dict, timeout: float = 20.0) -> dict:
        async with httpx.AsyncClient(timeout=timeout) as http:
            resp = await http.post(
                self._url("/api/v1/workflows"), json=workflow, headers=self.headers
            )
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                return {
                    "error": f"n8n {e.response.status_code}: "
                             f"{e.response.text[:300]}"
                }
            try:
                return resp.json()
            except (json.JSONDecodeError, ValueError):
                return {"error": f"n8n returned non-JSON response (HTTP {resp.status_code}): {resp.text[:200]}"}

    async def list_workflows(self, timeout: float = 20.0) -> list:
        """GET /api/v1/workflows — full list (id, name, active, nodes, ...)."""
        async with httpx.AsyncClient(timeout=timeout) as http:
            resp = await http.get(self._url("/api/v1/workflows"), headers=self.headers)
            resp.raise_for_status()
            return resp.json().get("data", [])

    async def delete_workflow(self, workflow_id: str, timeout: float = 20.0) -> bool:
        """DELETE /api/v1/workflows/{id} — n8n 2xx means gone."""
        async with httpx.AsyncClient(timeout=timeout) as http:
            resp = await http.delete(
                self._url(f"/api/v1/workflows/{workflow_id}"), headers=self.headers
            )
            return resp.status_code in (200, 204)

    async def activate(self, workflow_id: str, timeout: float = 20.0) -> None:
        async with httpx.AsyncClient(timeout=timeout) as http:
            try:
                resp = await http.post(
                    self._url(f"/api/v1/workflows/{workflow_id}/activate"),
                    headers=self.headers,
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                print(f"[n8n_client] activate failed: {e}")
                return {"error": str(e)}

    def webhook_url(self, workflow_or_created: dict, default_path: str) -> str:
        """Build the full webhook URL. Tries to extract path from workflow nodes,
        falls back to default_path."""
        base = self.base_url.rstrip("/")

        # Try to extract from the workflow's Webhook node
        nodes = workflow_or_created.get("nodes", [])
        for node in nodes:
            if node.get("type") == "n8n-nodes-base.webhook":
                path = node.get("parameters", {}).get("path", "")
                if path:
                    return f"{base}/webhook/{path}"

        # Fallback to provided path
        if default_path.startswith("http"):
            return default_path
        return f"{base}/webhook/{default_path}"

    async def call_spawned(
        self,
        task: str,
        model: str,
        webhook_url: str,
        attempts: int = 5,
        delay: float = 0.6,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        """Call a just-activated workflow, retrying to survive n8n activation
        races and slow executions (a timeout means the workflow is still
        running — re-posting re-executes it, so attempts bounds the wait)."""
        timeout = timeout or N8N_TIMEOUT
        result, status = "", 0
        async with httpx.AsyncClient(timeout=timeout) as http:
            for _ in range(attempts):
                try:
                    resp = await http.post(webhook_url, json={"task": task, "model": model})
                    try:
                        data = unwrap(resp.json())
                    except (json.JSONDecodeError, ValueError):
                        result, status = (
                            f"n8n error (HTTP {resp.status_code}): {resp.text[:200]}",
                            resp.status_code,
                        )
                        break
                    result, status = data.get("result", str(data)), resp.status_code
                except httpx.ReadTimeout:
                    result, status = "ReadTimeout", 0
                err = str(result)
                # n8n masks execution failures (incl. LLM rate limits) as
                # "Error in workflow" with a 500 — wait out the rate-limit
                # window between retries instead of hammering.
                rate_limited = status == 429 or "Error in workflow" in err
                if not rate_limited and status < 500 and status != 0:
                    break
                await asyncio.sleep(12.0 if rate_limited else delay)
        return result, status