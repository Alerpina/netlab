"""Carrega data/fabric.yml no NetBox. Idempotente: rodar duas vezes não muda nada."""

from __future__ import annotations

import argparse
import ipaddress
from typing import Any

from .logging_setup import get_logger
from .model import _endpoint, load_fabric, validate_fabric
from .netbox_client import NetBox
from .settings import LAB_ROOT, Settings

log = get_logger("seed")
ETH_TYPE = "100gbase-x-qsfp28"


def _ensure(nb: NetBox, path: str, lookup: dict, payload: dict) -> dict[str, Any]:
    obj, action = nb.ensure(path, lookup, payload)
    if action != "unchanged":
        log.info(action, extra={"object": path, "lookup": lookup})
    return obj


def _ensure_ip(nb: NetBox, address: str, iface_id: int) -> dict[str, Any]:
    return _ensure(
        nb,
        "ipam/ip-addresses/",
        {"address": address},
        {
            "address": address,
            "status": "active",
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": iface_id,
        },
    )


def seed(nb: NetBox, data: dict[str, Any]) -> None:
    validate_fabric(data)
    s, m, p, t = data["site"], data["manufacturer"], data["platform"], data["device_type"]

    site = _ensure(nb, "dcim/sites/", {"slug": s["slug"]}, {**s, "status": "active"})
    mfr = _ensure(nb, "dcim/manufacturers/", {"slug": m["slug"]}, m)
    platform = _ensure(nb, "dcim/platforms/", {"slug": p["slug"]}, {**p, "manufacturer": mfr["id"]})
    dtype = _ensure(nb, "dcim/device-types/", {"slug": t["slug"]}, {**t, "manufacturer": mfr["id"]})
    roles = {r["slug"]: _ensure(nb, "dcim/device-roles/", {"slug": r["slug"]}, r) for r in data["roles"]}

    devices: dict[str, dict] = {}
    ifaces: dict[tuple[str, str], dict] = {}

    def iface(dev: str, name: str, payload: dict) -> dict:
        obj = _ensure(
            nb,
            "dcim/interfaces/",
            {"device_id": devices[dev]["id"], "name": name},
            {"device": devices[dev]["id"], "name": name, **payload},
        )
        ifaces[(dev, name)] = obj
        return obj

    for name, d in data["devices"].items():
        devices[name] = _ensure(
            nb,
            "dcim/devices/",
            {"name": name, "site_id": site["id"]},
            {
                "name": name,
                "site": site["id"],
                "role": roles[d["role"]]["id"],
                "device_type": dtype["id"],
                "platform": platform["id"],
                "status": "active",
            },
        )
        mgmt_if = iface(name, "mgmt0", {"type": "1000base-t", "mgmt_only": True})
        mgmt_ip = _ensure_ip(nb, d["mgmt"], mgmt_if["id"])
        lo_if = iface(name, "system0", {"type": "virtual"})
        _ensure_ip(nb, d["loopback"], lo_if["id"])
        if (devices[name].get("primary_ip4") or {}).get("id") != mgmt_ip["id"]:
            nb.update("dcim/devices/", devices[name]["id"], {"primary_ip4": mgmt_ip["id"]})
            log.info("primary_ip4", extra={"device": name, "address": d["mgmt"]})

    for link in data.get("links", []):
        (a_dev, a_if), (b_dev, b_if) = _endpoint(link["a"]), _endpoint(link["b"])
        net = ipaddress.ip_network(link["subnet"])
        a_ip, b_ip = (f"{ip}/{net.prefixlen}" for ip in net)
        a = iface(a_dev, a_if, {"type": ETH_TYPE, "description": f"to {b_dev} {b_if}"})
        b = iface(b_dev, b_if, {"type": ETH_TYPE, "description": f"to {a_dev} {a_if}"})
        _ensure_ip(nb, a_ip, a["id"])
        _ensure_ip(nb, b_ip, b["id"])

        if a.get("cable") or b.get("cable"):
            continue  # cabo já existe; o post-check (LLDP) confirma se está certo
        nb.create(
            "dcim/cables/",
            {
                "a_terminations": [{"object_type": "dcim.interface", "object_id": a["id"]}],
                "b_terminations": [{"object_type": "dcim.interface", "object_id": b["id"]}],
                "status": "connected",
            },
        )
        log.info("created", extra={"object": "dcim/cables/", "link": f"{link['a']} <-> {link['b']}"})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Popula o NetBox a partir do fabric.yml")
    parser.add_argument("--fabric", default=LAB_ROOT / "data" / "fabric.yml")
    args = parser.parse_args(argv)
    cfg = Settings.from_env()
    cfg.require_netbox()
    nb = NetBox(cfg.netbox_url, cfg.netbox_token)
    try:
        seed(nb, load_fabric(args.fabric))
    finally:
        nb.close()
    log.info("seed concluído")


if __name__ == "__main__":
    main()
