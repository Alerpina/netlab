"""Modelo neutro da fábrica: o que a rede deve ser, venha do NetBox ou do YAML."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class FabricError(ValueError):
    """Dados da fonte da verdade inconsistentes: nada deve ser aplicado."""


@dataclass(frozen=True)
class Interface:
    name: str
    ipv4: str | None = None
    description: str = ""
    enabled: bool = True
    peer_device: str | None = None
    peer_interface: str | None = None


@dataclass
class Device:
    name: str
    role: str
    mgmt_ip: str
    loopback: str
    interfaces: list[Interface] = field(default_factory=list)


def natural_key(name: str) -> tuple:
    """ethernet-1/2 antes de ethernet-1/10."""
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name))


def load_fabric(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _endpoint(raw: str) -> tuple[str, str]:
    device, sep, iface = raw.partition(":")
    if not sep or not device or not iface:
        raise FabricError(f"Endpoint inválido '{raw}': use device:interface")
    return device, iface


def validate_fabric(data: dict[str, Any]) -> None:
    """Valida antes de qualquer mudança. Junta todos os erros numa mensagem só."""
    errors: list[str] = []
    devices: dict[str, Any] = data.get("devices") or {}
    roles = {r["slug"] for r in data.get("roles", [])}
    used_ips: dict[ipaddress.IPv4Address, str] = {}

    def claim(ip: ipaddress.IPv4Address, owner: str) -> None:
        if ip in used_ips:
            errors.append(f"IP {ip} usado em '{used_ips[ip]}' e em '{owner}'")
        used_ips[ip] = owner

    for name, dev in devices.items():
        if dev.get("role") not in roles:
            errors.append(f"{name}: role '{dev.get('role')}' não existe em roles")
        try:
            claim(ipaddress.ip_interface(dev["mgmt"]).ip, f"{name} mgmt")
            loop = ipaddress.ip_interface(dev["loopback"])
            if loop.network.prefixlen != 32:
                errors.append(f"{name}: loopback {loop} deve ser /32")
            claim(loop.ip, f"{name} loopback")
        except (KeyError, ValueError) as exc:
            errors.append(f"{name}: mgmt/loopback inválido ({exc})")

    endpoints: set[tuple[str, str]] = set()
    for i, link in enumerate(data.get("links", []), start=1):
        try:
            a, b = _endpoint(link["a"]), _endpoint(link["b"])
            net = ipaddress.ip_network(link["subnet"])
        except (KeyError, ValueError) as exc:
            errors.append(f"link {i}: {exc}")
            continue
        for dev, iface in (a, b):
            if dev not in devices:
                errors.append(f"link {i}: equipamento '{dev}' não existe")
            if (dev, iface) in endpoints:
                errors.append(f"link {i}: {dev}:{iface} já está em outro link")
            endpoints.add((dev, iface))
        if net.version != 4 or net.prefixlen != 31:
            errors.append(f"link {i}: {net} deve ser um /31 IPv4")
            continue
        for ip in net:
            claim(ip, f"link {i}")

    if errors:
        raise FabricError("Fonte da verdade inválida:\n- " + "\n- ".join(errors))


def devices_from_fabric(data: dict[str, Any]) -> list[Device]:
    validate_fabric(data)
    devices = {
        name: Device(name=name, role=d["role"], mgmt_ip=d["mgmt"], loopback=d["loopback"])
        for name, d in data["devices"].items()
    }
    for link in data.get("links", []):
        (a_dev, a_if), (b_dev, b_if) = _endpoint(link["a"]), _endpoint(link["b"])
        net = ipaddress.ip_network(link["subnet"])
        a_ip, b_ip = (f"{ip}/{net.prefixlen}" for ip in net)
        devices[a_dev].interfaces.append(Interface(a_if, a_ip, f"to {b_dev} {b_if}", True, b_dev, b_if))
        devices[b_dev].interfaces.append(Interface(b_if, b_ip, f"to {a_dev} {a_if}", True, a_dev, a_if))
    for dev in devices.values():
        dev.interfaces.sort(key=lambda i: natural_key(i.name))
    return sorted(devices.values(), key=lambda d: natural_key(d.name))
