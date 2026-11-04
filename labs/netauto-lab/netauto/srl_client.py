"""Cliente JSON-RPC do SR Linux (leitura). Mudanças passam pelo Ansible, não por aqui."""

from __future__ import annotations

import itertools
from typing import Any

import httpx


class SRLError(RuntimeError):
    pass


class SRLClient:
    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        *,
        verify: bool = False,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.host = host
        self._ids = itertools.count(1)
        self._http = httpx.Client(
            base_url=f"https://{host}",
            auth=(user, password),
            verify=verify,
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SRLClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _call(self, method: str, params: dict[str, Any]) -> list[Any]:
        body = {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params}
        try:
            resp = self._http.post("/jsonrpc", json=body)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SRLError(f"{self.host}: {type(exc).__name__}: {exc}") from exc
        data = resp.json()
        if "error" in data:
            raise SRLError(f"{self.host}: {data['error'].get('message', data['error'])}")
        return data["result"]

    def get_many(self, paths: list[str], datastore: str = "state") -> list[Any]:
        commands = [{"path": p, "datastore": datastore} for p in paths]
        return self._call("get", {"commands": commands})

    def get(self, path: str, datastore: str = "state") -> Any:
        return self.get_many([path], datastore)[0]
