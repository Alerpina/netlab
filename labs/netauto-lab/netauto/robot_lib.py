"""Keywords do Robot Framework para os pre/post-checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .drift import check_intent, load_intents, normalize
from .settings import Settings
from .srl_client import SRLClient


class NetautoLibrary:
    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(self, intent_dir: str = "build/intents") -> None:
        self.intent_dir = Path(intent_dir)
        self.cfg = Settings.from_env()
        self._intents: dict[str, dict[str, Any]] | None = None

    # --- apoio -----------------------------------------------------------------------------

    @property
    def intents(self) -> dict[str, dict[str, Any]]:
        if self._intents is None:
            self._intents = {i["host"]: i for i in load_intents(self.intent_dir)}
        return self._intents

    def _client(self, host: str) -> SRLClient:
        self.cfg.require_device_credentials()
        return SRLClient(
            self.intents[host]["mgmt_ip"],
            self.cfg.srl_user,
            self.cfg.srl_password,
            verify=self.cfg.srl_verify,
        )

    # --- keywords --------------------------------------------------------------------------

    def get_lab_hosts(self) -> list[str]:
        return sorted(self.intents)

    def device_should_be_reachable(self, host: str) -> str:
        with self._client(host) as c:
            version = normalize(c.get("/system/information/version"))
        if not version:
            raise AssertionError(f"{host}: não retornou versão")
        return str(version)

    def interfaces_should_be_up(self, host: str) -> None:
        names = [link["interface"] for link in self.intents[host]["links"]]
        with self._client(host) as c:
            states = c.get_many([f"/interface[name={n}]/oper-state" for n in names])
        down = [n for n, s in zip(names, states, strict=True) if normalize(s) != "up"]
        if down:
            raise AssertionError(f"{host}: interfaces fora do ar: {', '.join(down)}")

    def lldp_neighbors_should_match_source_of_truth(self, host: str) -> None:
        links = self.intents[host]["links"]
        with self._client(host) as c:
            data = c.get_many([f"/system/lldp/interface[name={x['interface']}]" for x in links])
        errors = []
        for link, entry in zip(links, data, strict=True):
            neighbors = normalize(entry or {}).get("neighbor", [])
            seen = {(n.get("system-name"), n.get("port-id")) for n in neighbors}
            wanted = (link["peer_device"], link["peer_interface"])
            if wanted not in seen:
                errors.append(f"{link['interface']}: esperado {wanted}, visto {sorted(seen) or 'nada'}")
        if errors:
            raise AssertionError(f"{host}: cabeamento diferente do NetBox:\n" + "\n".join(errors))

    def configuration_should_have_no_drift(self, host: str) -> None:
        with self._client(host) as c:
            diffs = check_intent(c, self.intents[host])
        if diffs:
            lines = [f"{d['kind']}: {d['path']}" for d in diffs]
            raise AssertionError(f"{host}: {len(diffs)} diferença(s):\n" + "\n".join(lines))
