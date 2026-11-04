from netauto.intent import build_intent, to_cli


def _by_path(intent):
    return {u["path"]: u["value"] for u in intent["updates"]}


def test_intencao_do_spine(devices):
    intent = build_intent(devices["spine1"])
    updates = _by_path(intent)

    e1 = updates["/interface[name=ethernet-1/1]"]
    assert e1["admin-state"] == "enable"
    assert e1["description"] == "to leaf1 ethernet-1/49"
    assert e1["subinterface"][0]["ipv4"]["address"] == [{"ip-prefix": "10.0.0.0/31"}]

    lo = updates["/interface[name=system0]"]
    assert lo["subinterface"][0]["ipv4"]["address"] == [{"ip-prefix": "10.255.0.1/32"}]

    ni = updates["/network-instance[name=default]"]
    assert [i["name"] for i in ni["interface"]] == [
        "ethernet-1/1.0",
        "ethernet-1/2.0",
        "system0.0",
    ]
    assert intent["mgmt_ip"] == "172.30.30.11"


def test_links_para_o_post_check(devices):
    links = build_intent(devices["leaf2"])["links"]
    assert {"interface": "ethernet-1/50", "peer_device": "spine2", "peer_interface": "ethernet-1/2"} in links


def test_intencao_e_deterministica(fabric):
    from netauto.model import devices_from_fabric

    first = [build_intent(d) for d in devices_from_fabric(fabric)]
    second = [build_intent(d) for d in devices_from_fabric(fabric)]
    assert first == second


def test_visao_cli_para_revisao(devices):
    lines = to_cli(build_intent(devices["leaf1"])["updates"])
    assert 'set / interface ethernet-1/49 description "to spine1 ethernet-1/1"' in lines
    assert "set / interface ethernet-1/49 subinterface 0 ipv4 address 10.0.0.1/31" in lines
    assert "set / network-instance default interface system0.0" in lines
