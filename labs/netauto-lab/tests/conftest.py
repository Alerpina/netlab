from pathlib import Path

import pytest

from netauto.model import devices_from_fabric, load_fabric

LAB = Path(__file__).resolve().parent.parent


@pytest.fixture
def fabric() -> dict:
    return load_fabric(LAB / "data" / "fabric.yml")


@pytest.fixture
def devices(fabric):
    return {d.name: d for d in devices_from_fabric(fabric)}
