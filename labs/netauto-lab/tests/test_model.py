import copy

import pytest

from netauto.model import FabricError, devices_from_fabric, natural_key, validate_fabric


def test_fabric_do_repo_e_valido(fabric):
    validate_fabric(fabric)


def test_fabric_mini_e_valido_e_tem_3_equipamentos():
    from pathlib import Path

    from netauto.model import load_fabric

    mini = load_fabric(Path(__file__).resolve().parent.parent / "data" / "fabric-mini.yml")
    devices = devices_from_fabric(mini)
    assert [d.name for d in devices] == ["leaf1", "leaf2", "spine1"]
    assert len(mini["links"]) == 2


def test_lado_a_recebe_primeiro_ip_do_31(devices):
    spine1 = {i.name: i for i in devices["spine1"].interfaces}
    leaf1 = {i.name: i for i in devices["leaf1"].interfaces}
    assert spine1["ethernet-1/1"].ipv4 == "10.0.0.0/31"
    assert leaf1["ethernet-1/49"].ipv4 == "10.0.0.1/31"
    assert leaf1["ethernet-1/49"].peer_device == "spine1"


def test_interfaces_em_ordem_natural():
    assert sorted(["ethernet-1/10", "ethernet-1/2"], key=natural_key) == [
        "ethernet-1/2",
        "ethernet-1/10",
    ]


@pytest.mark.parametrize(
    ("mutate", "erro"),
    [
        (lambda f: f["links"][0].update(subnet="10.0.0.0/30"), "/31"),
        (lambda f: f["links"][1].update(subnet="10.0.0.0/31"), "usado em"),
        (lambda f: f["links"][0].update(b="leaf9:ethernet-1/1"), "não existe"),
        (lambda f: f["links"][1].update(a="spine1:ethernet-1/1"), "já está em outro link"),
        (lambda f: f["devices"]["leaf2"].update(loopback="10.255.0.11/32"), "usado em"),
        (lambda f: f["devices"]["leaf2"].update(role="border"), "role"),
    ],
)
def test_validacao_barra_dados_inconsistentes(fabric, mutate, erro):
    broken = copy.deepcopy(fabric)
    mutate(broken)
    with pytest.raises(FabricError, match=erro):
        devices_from_fabric(broken)
