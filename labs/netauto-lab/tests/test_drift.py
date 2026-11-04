from netauto.drift import compare, normalize
from netauto.intent import build_intent

EXPECTED = {
    "admin-state": "enable",
    "description": "to leaf1 ethernet-1/49",
    "subinterface": [
        {
            "index": 0,
            "admin-state": "enable",
            "ipv4": {"admin-state": "enable", "address": [{"ip-prefix": "10.0.0.0/31"}]},
        }
    ],
}


def running(**changes):
    import copy

    value = copy.deepcopy(EXPECTED)
    value["oper-state"] = "up"  # campos extras de fora da intenção são ignorados
    value.update(changes)
    return value


def test_sem_drift():
    assert compare(EXPECTED, running(), "/interface[name=ethernet-1/1]") == []


def test_descricao_alterada_na_mao():
    diffs = compare(EXPECTED, running(description="teste"), "/i")
    assert diffs == [
        {"path": "/i/description", "kind": "changed", "expected": "to leaf1 ethernet-1/49", "actual": "teste"}
    ]


def test_ip_trocado_aparece_como_missing_e_extra():
    sub = [
        {
            "index": 0,
            "admin-state": "enable",
            "ipv4": {"admin-state": "enable", "address": [{"ip-prefix": "10.9.9.0/31"}]},
        }
    ]
    kinds = {(d["kind"], d["path"]) for d in compare(EXPECTED, running(subinterface=sub), "/i")}
    assert ("missing", "/i/subinterface[index=0]/ipv4/address[ip-prefix=10.0.0.0/31]") in kinds
    assert ("extra", "/i/subinterface[index=0]/ipv4/address[ip-prefix=10.9.9.0/31]") in kinds


def test_subinterface_removida():
    diffs = compare(EXPECTED, running(subinterface=[]), "/i")
    assert [d["kind"] for d in diffs] == ["missing"]


def test_normaliza_prefixo_de_modulo_yang():
    raw = {"srl_nokia-network-instance:type": "srl_nokia-network-instance:default", "x": "10.0.0.0/31"}
    assert normalize(raw) == {"type": "default", "x": "10.0.0.0/31"}


def test_intencao_inteira_contra_running_igual(devices):
    for upd in build_intent(devices["spine2"])["updates"]:
        assert compare(upd["value"], normalize(upd["value"]), upd["path"]) == []
