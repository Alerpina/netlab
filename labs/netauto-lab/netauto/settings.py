"""Configuração por variáveis de ambiente (nada de segredo no código)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim"}


@dataclass(frozen=True)
class Settings:
    netbox_url: str
    netbox_token: str
    site: str
    platform: str
    srl_user: str
    srl_password: str
    srl_verify: bool
    build_dir: Path

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            netbox_url=os.getenv("NETBOX_URL", "http://localhost:8000"),
            netbox_token=os.getenv("NETBOX_TOKEN", ""),
            site=os.getenv("NETAUTO_SITE", "lab-dc1"),
            platform=os.getenv("NETAUTO_PLATFORM", "srlinux"),
            srl_user=os.getenv("SRL_USER", "admin"),
            srl_password=os.getenv("SRL_PASSWORD", ""),
            # O SR Linux do lab usa certificado autoassinado
            srl_verify=_bool(os.getenv("SRL_VERIFY"), False),
            build_dir=Path(os.getenv("BUILD_DIR", LAB_ROOT / "build")),
        )

    def require_netbox(self) -> None:
        if not self.netbox_token:
            raise SystemExit("Defina NETBOX_TOKEN (Admin > API Tokens no NetBox).")

    def require_device_credentials(self) -> None:
        if not self.srl_password:
            raise SystemExit("Defina SRL_PASSWORD com a senha dos equipamentos.")
