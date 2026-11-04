"""Cliente mínimo da API REST do NetBox com httpx: paginação, retry e operações idempotentes."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from .model import Device, Interface, natural_key

RETRY_STATUS = {429, 502, 503, 504}


class NetBoxError(RuntimeError):
    pass


class NetBox:
    def __init__(
        self,
        url: str,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
        retries: int = 3,
        backoff: float = 0.5,
        verify: bool = True,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        # Tokens v2 (NetBox 4.5+) começam com "nbt_" e usam Bearer; os antigos usam Token
        scheme = "Bearer" if token.startswith("nbt_") else "Token"
        self._http = httpx.Client(
            base_url=url.rstrip("/") + "/api/",
            headers={"Authorization": f"{scheme} {token}", "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
            verify=verify,
        )
        self.retries = retries
        self.backoff = backoff
        self._sleep = sleep

    def close(self) -> None:
        self._http.close()

    # --- HTTP -------------------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        last: str = ""
        for attempt in range(1, self.retries + 1):
            try:
                resp = self._http.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                last = f"{type(exc).__name__}: {exc}"
            else:
                if resp.status_code not in RETRY_STATUS:
                    if resp.is_error:
                        raise NetBoxError(f"{method} {path}: HTTP {resp.status_code} {resp.text[:300]}")
                    return resp.json() if resp.content else None
                last = f"HTTP {resp.status_code}"
            if attempt < self.retries:
                self._sleep(self.backoff * 2 ** (attempt - 1))
        raise NetBoxError(f"{method} {path}: falhou após {self.retries} tentativas ({last})")

    def list(self, path: str, **params: Any) -> list[dict[str, Any]]:
        params.setdefault("limit", 1000)
        results: list[dict[str, Any]] = []
        while True:
            page = self._request("GET", path, params=params)
            results += page["results"]
            if not page.get("next"):
                return results
            # Usa só a query do "next": o host dele pode ser o de dentro do container
            params = dict(httpx.URL(page["next"]).params)

    def get_one(self, path: str, **params: Any) -> dict[str, Any] | None:
        found = self.list(path, **params)
        if len(found) > 1:
            raise NetBoxError(f"{path} {params}: esperado 1 objeto, vieram {len(found)}")
        return found[0] if found else None

    def create(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, json=payload)

    def update(self, path: str, obj_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"{path}{obj_id}/", json=payload)

    def ensure(
        self, path: str, lookup: dict[str, Any], payload: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Cria se não existe, corrige só os campos diferentes. Retorna (objeto, ação)."""
        current = self.get_one(path, **lookup)
        if current is None:
            return self.create(path, payload), "created"
        changes = {k: v for k, v in payload.items() if _differs(current.get(k), v)}
        if not changes:
            return current, "unchanged"
        return self.update(path, current["id"], changes), "updated"


def _differs(current: Any, desired: Any) -> bool:
    if isinstance(current, dict):
        if "id" in current:  # chave estrangeira (site, role, device...)
            return current["id"] != desired
        if "value" in current:  # campo de escolha (status, type...)
            return current["value"] != desired
    return current != desired


# --- NetBox -> modelo da fábrica --------------------------------------------------------------


def fetch_devices(nb: NetBox, site: str, platform: str = "srlinux") -> list[Device]:
    devices: list[Device] = []
    for d in nb.list("dcim/devices/", site=site, platform=platform):
        name = d["name"]
        role = (d.get("role") or d.get("device_role") or {}).get("slug", "")
        mgmt = (d.get("primary_ip4") or {}).get("address")
        if not mgmt:
            raise NetBoxError(f"{name}: sem primary_ip4 no NetBox")

        ips = {
            ip["assigned_object_id"]: ip["address"]
            for ip in nb.list("ipam/ip-addresses/", device_id=d["id"])
            if ip.get("assigned_object_type") == "dcim.interface"
        }
        loopback = None
        interfaces: list[Interface] = []
        for i in nb.list("dcim/interfaces/", device_id=d["id"]):
            if i["name"] == "system0":
                loopback = ips.get(i["id"])
            if not i["name"].startswith("ethernet-"):
                continue
            peer = (i.get("link_peers") or [None])[0]
            peer_dev = peer["device"]["name"] if peer else None
            peer_if = peer["name"] if peer else None
            desc = i.get("description") or (f"to {peer_dev} {peer_if}" if peer else "")
            interfaces.append(
                Interface(i["name"], ips.get(i["id"]), desc, i.get("enabled", True), peer_dev, peer_if)
            )
        if not loopback:
            raise NetBoxError(f"{name}: system0 sem IP no NetBox")
        interfaces.sort(key=lambda x: natural_key(x.name))
        devices.append(Device(name, role, mgmt, loopback, interfaces))
    return sorted(devices, key=lambda x: natural_key(x.name))
