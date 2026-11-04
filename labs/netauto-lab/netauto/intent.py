"""Transforma o modelo da fábrica em intenção SR Linux (lista de {path, value}).

Funções puras: mesma entrada, mesma saída. É o que torna o código testável sem equipamento
e o diff do PR legível.
"""

from __future__ import annotations

import re
from typing import Any

from .model import Device, Interface

NETWORK_INSTANCE = "default"
LOOPBACK = "system0"
# Campos que identificam itens de lista no YANG do SR Linux
LIST_KEYS = ("name", "index", "ip-prefix", "peer-address", "group-name", "afi-safi-name")


def _subinterface(ipv4: str) -> dict[str, Any]:
    return {
        "index": 0,
        "admin-state": "enable",
        "ipv4": {"admin-state": "enable", "address": [{"ip-prefix": ipv4}]},
    }


def interface_update(iface: Interface) -> dict[str, Any]:
    value: dict[str, Any] = {"admin-state": "enable" if iface.enabled else "disable"}
    if iface.description:
        value["description"] = iface.description
    if iface.ipv4:
        value["subinterface"] = [_subinterface(iface.ipv4)]
    return {"path": f"/interface[name={iface.name}]", "value": value}


def loopback_update(device: Device) -> dict[str, Any]:
    return {
        "path": f"/interface[name={LOOPBACK}]",
        "value": {"admin-state": "enable", "subinterface": [_subinterface(device.loopback)]},
    }


def network_instance_update(device: Device) -> dict[str, Any]:
    names = [f"{i.name}.0" for i in device.interfaces if i.ipv4] + [f"{LOOPBACK}.0"]
    return {
        "path": f"/network-instance[name={NETWORK_INSTANCE}]",
        "value": {
            "type": "default",
            "admin-state": "enable",
            "interface": [{"name": n} for n in names],
        },
    }


def build_intent(device: Device) -> dict[str, Any]:
    """Intenção completa de um equipamento, mais os metadados usados pelos checks."""
    return {
        "host": device.name,
        "role": device.role,
        "mgmt_ip": device.mgmt_ip.split("/")[0],
        "links": [
            {"interface": i.name, "peer_device": i.peer_device, "peer_interface": i.peer_interface}
            for i in device.interfaces
            if i.peer_device
        ],
        "updates": [
            *(interface_update(i) for i in device.interfaces),
            loopback_update(device),
            network_instance_update(device),
        ],
    }


# --- Visão em CLI "flat" do SR Linux, para revisão humana no PR -----------------------------

_SEGMENT = re.compile(r"([\w-]+)(?:\[[\w-]+=([^\]]+)\])?")


def _path_tokens(path: str) -> list[str]:
    tokens: list[str] = []
    for name, key in _SEGMENT.findall(path):
        tokens.append(name)
        if key:
            tokens.append(key)
    return tokens


def _list_key(item: dict[str, Any]) -> str | None:
    return next((k for k in LIST_KEYS if k in item), None)


def _quote(value: Any) -> str:
    text = str(value)
    return f'"{text}"' if " " in text else text


def _walk(tokens: list[str], value: Any) -> list[str]:
    if isinstance(value, dict):
        lines: list[str] = []
        for k, v in value.items():
            lines += _walk([*tokens, k], v)
        return lines or [" ".join(tokens)]
    if isinstance(value, list):
        if value and all(isinstance(i, dict) for i in value):
            lines = []
            for item in value:
                key = _list_key(item)
                rest = {k: v for k, v in item.items() if k != key}
                base = [*tokens, str(item[key])] if key else tokens
                lines += _walk(base, rest) if rest else [" ".join(base)]
            return lines
        return [" ".join(tokens) + " [ " + " ".join(str(v) for v in value) + " ]"]
    return [" ".join([*tokens, _quote(value)])]


def to_cli(updates: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for upd in updates:
        lines += [f"set / {line}" for line in _walk(_path_tokens(upd["path"]), upd["value"])]
    return lines
