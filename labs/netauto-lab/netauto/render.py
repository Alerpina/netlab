"""Gera build/intents/<host>.json (para o Ansible) e <host>.cli (para revisão no PR)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .intent import build_intent, to_cli
from .logging_setup import get_logger, run_context
from .model import Device, devices_from_fabric, load_fabric
from .netbox_client import NetBox, fetch_devices
from .settings import LAB_ROOT, Settings

log = get_logger("render")


def load_devices(source: str, fabric: Path, cfg: Settings) -> list[Device]:
    if source == "file":
        return devices_from_fabric(load_fabric(fabric))
    cfg.require_netbox()
    nb = NetBox(cfg.netbox_url, cfg.netbox_token)
    try:
        return fetch_devices(nb, cfg.site, cfg.platform)
    finally:
        nb.close()


def render(devices: list[Device], out: Path, source: str) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(LAB_ROOT / "templates"),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("srlinux.cli.j2")
    ctx = run_context()
    hosts = []
    for dev in devices:
        intent = build_intent(dev)
        (out / f"{dev.name}.json").write_text(
            json.dumps(intent, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (out / f"{dev.name}.cli").write_text(
            template.render(intent=intent, lines=to_cli(intent["updates"]), source=source),
            encoding="utf-8",
        )
        hosts.append(dev.name)
        log.info("intenção gerada", extra={"host": dev.name, "updates": len(intent["updates"])})
    manifest = {**ctx, "source": source, "hosts": hosts}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return hosts


def main(argv: list[str] | None = None) -> None:
    cfg = Settings.from_env()
    parser = argparse.ArgumentParser(description="Gera a intenção de cada equipamento")
    parser.add_argument("--source", choices=["netbox", "file"], default="netbox")
    parser.add_argument("--fabric", type=Path, default=LAB_ROOT / "data" / "fabric.yml")
    parser.add_argument("--out", type=Path, default=cfg.build_dir / "intents")
    args = parser.parse_args(argv)
    render(load_devices(args.source, args.fabric, cfg), args.out, args.source)


if __name__ == "__main__":
    main()
