"""Drift: compara a intenção (NetBox) com a running de cada equipamento.

Saída 0 = sem drift, 2 = drift encontrado, 1 = erro de acesso.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from .intent import LIST_KEYS
from .logging_setup import get_logger, run_context
from .settings import Settings
from .srl_client import SRLClient, SRLError

log = get_logger("drift")
_NS = re.compile(r"^[a-z][\w-]*:([a-z][\w-]*)$")


def _strip(name: str) -> str:
    match = _NS.match(name)
    return match.group(1) if match else name


def normalize(obj: Any) -> Any:
    """Tira o prefixo de módulo YANG (srl_nokia-xxx:) de chaves e valores."""
    if isinstance(obj, dict):
        return {_strip(k): normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    if isinstance(obj, str):
        return _strip(obj)
    return obj


def _key(item: dict[str, Any]) -> str | None:
    return next((k for k in LIST_KEYS if k in item), None)


def compare(expected: Any, actual: Any, path: str = "") -> list[dict[str, Any]]:
    """Tudo que está na intenção precisa estar igual na running.

    Campos a mais na running são ignorados; itens a mais em listas gerenciadas (IPs,
    interfaces da network-instance) contam como drift.
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [{"path": path or "/", "kind": "changed", "expected": expected, "actual": actual}]
        diffs: list[dict[str, Any]] = []
        for k, v in expected.items():
            child = f"{path}/{k}"
            if k not in actual:
                diffs.append({"path": child, "kind": "missing", "expected": v, "actual": None})
            else:
                diffs += compare(v, actual[k], child)
        return diffs

    if isinstance(expected, list):
        actual = actual if isinstance(actual, list) else []
        if expected and all(isinstance(i, dict) for i in expected):
            key = _key(expected[0])
            if key is None:
                return (
                    []
                    if expected == actual
                    else [{"path": path, "kind": "changed", "expected": expected, "actual": actual}]
                )
            current = {i.get(key): i for i in actual if isinstance(i, dict)}
            diffs = []
            for item in expected:
                item_path = f"{path}[{key}={item[key]}]"
                if item[key] not in current:
                    diffs.append({"path": item_path, "kind": "missing", "expected": item, "actual": None})
                else:
                    diffs += compare(item, current[item[key]], item_path)
            wanted = {i[key] for i in expected}
            diffs += [
                {"path": f"{path}[{key}={k}]", "kind": "extra", "expected": None, "actual": v}
                for k, v in current.items()
                if k not in wanted
            ]
            return diffs
        missing = [v for v in expected if v not in actual]
        extra = [v for v in actual if v not in expected]
        diffs = []
        if missing:
            diffs.append({"path": path, "kind": "missing", "expected": missing, "actual": None})
        if extra:
            diffs.append({"path": path, "kind": "extra", "expected": None, "actual": extra})
        return diffs

    if expected != actual:
        return [{"path": path, "kind": "changed", "expected": expected, "actual": actual}]
    return []


def check_intent(client: SRLClient, intent: dict[str, Any]) -> list[dict[str, Any]]:
    updates = intent["updates"]
    running = client.get_many([u["path"] for u in updates], datastore="running")
    diffs: list[dict[str, Any]] = []
    for upd, actual in zip(updates, running, strict=True):
        diffs += compare(upd["value"], normalize(actual or {}), upd["path"])
    return diffs


def load_intents(intent_dir: Path, hosts: list[str] | None = None) -> list[dict[str, Any]]:
    files = sorted(p for p in intent_dir.glob("*.json") if p.name != "manifest.json")
    intents = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    return [i for i in intents if not hosts or i["host"] in hosts]


def main(argv: list[str] | None = None) -> int:
    cfg = Settings.from_env()
    parser = argparse.ArgumentParser(description="Detecta drift entre NetBox e equipamentos")
    parser.add_argument("--intents", type=Path, default=cfg.build_dir / "intents")
    parser.add_argument("--out", type=Path, default=cfg.build_dir / "drift" / "report.json")
    parser.add_argument("--host", action="append", dest="hosts")
    args = parser.parse_args(argv)
    cfg.require_device_credentials()

    report: dict[str, Any] = {**run_context(), "hosts": {}}
    status = 0
    for intent in load_intents(args.intents, args.hosts):
        host = intent["host"]
        try:
            with SRLClient(intent["mgmt_ip"], cfg.srl_user, cfg.srl_password, verify=cfg.srl_verify) as c:
                diffs = check_intent(c, intent)
        except SRLError as exc:
            log.error("sem acesso", extra={"host": host, "error": str(exc)})
            report["hosts"][host] = {"error": str(exc)}
            status = 1
            continue
        report["hosts"][host] = {"drift": diffs}
        if diffs:
            status = max(status, 2)
            log.warning("drift", extra={"host": host, "count": len(diffs)})
        else:
            log.info("sem drift", extra={"host": host})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
