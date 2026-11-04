import json

import httpx
import pytest

from netauto.intent import build_intent
from netauto.netbox_client import NetBox, NetBoxError, fetch_devices


def make(handler, **kw):
    return NetBox(
        "http://netbox.test", "abc123", transport=httpx.MockTransport(handler), sleep=lambda _: None, **kw
    )


def page(results, next_url=None):
    return httpx.Response(200, json={"count": len(results), "next": next_url, "results": results})


def test_header_de_token_v1_e_v2():
    seen = []

    def handler(req):
        seen.append(req.headers["Authorization"])
        return page([])

    make(handler).list("dcim/sites/")
    NetBox("http://netbox.test", "nbt_k.s", transport=httpx.MockTransport(handler)).list("dcim/sites/")
    assert seen == ["Token abc123", "Bearer nbt_k.s"]


def test_paginacao_segue_next_mesmo_com_host_interno():
    def handler(req):
        if req.url.params.get("offset") == "1":
            return page([{"id": 2}])
        return page([{"id": 1}], "http://netbox:8080/api/dcim/sites/?limit=1&offset=1")

    assert [s["id"] for s in make(handler).list("dcim/sites/", limit=1)] == [1, 2]


def test_retry_em_503_e_depois_sucesso():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else page([{"id": 1}])

    assert make(handler).list("dcim/sites/") == [{"id": 1}]
    assert calls["n"] == 3


def test_erro_4xx_nao_tem_retry():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(403, json={"detail": "Invalid token"})

    with pytest.raises(NetBoxError, match="403"):
        make(handler).list("dcim/sites/")
    assert calls["n"] == 1


def test_ensure_cria_atualiza_ou_mantem():
    state = {"obj": None, "methods": []}

    def handler(req):
        state["methods"].append(req.method)
        if req.method == "GET":
            return page([state["obj"]] if state["obj"] else [])
        body = json.loads(req.content)
        state["obj"] = {**(state["obj"] or {"id": 7}), **body}
        if "status" in body:
            state["obj"]["status"] = {"value": body["status"], "label": body["status"]}
        return httpx.Response(200, json=state["obj"])

    nb = make(handler)
    payload = {"name": "LAB", "slug": "lab", "status": "active"}
    assert nb.ensure("dcim/sites/", {"slug": "lab"}, payload)[1] == "created"
    assert nb.ensure("dcim/sites/", {"slug": "lab"}, payload)[1] == "unchanged"
    assert nb.ensure("dcim/sites/", {"slug": "lab"}, {**payload, "name": "LAB2"})[1] == "updated"
    assert state["methods"] == ["GET", "POST", "GET", "GET", "PATCH"]


def _netbox_from_fabric(devices):
    """Simula as respostas do NetBox para o fabric do repo."""
    db = {"dcim/devices/": [], "dcim/interfaces/": [], "ipam/ip-addresses/": []}
    ids = iter(range(1, 10_000))
    by_if = {}
    for dev in devices.values():
        dev_id = next(ids)
        mgmt_ip = {"id": next(ids), "address": dev.mgmt_ip}
        db["dcim/devices/"].append(
            {"id": dev_id, "name": dev.name, "role": {"id": 1, "slug": dev.role}, "primary_ip4": mgmt_ip}
        )
        lo = {"id": next(ids), "device_id": dev_id, "name": "system0"}
        db["dcim/interfaces/"].append(lo)
        db["ipam/ip-addresses/"].append(
            {
                "device_id": dev_id,
                "address": dev.loopback,
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": lo["id"],
            }
        )
        for i in dev.interfaces:
            row = {
                "id": next(ids),
                "device_id": dev_id,
                "name": i.name,
                "enabled": True,
                "description": i.description,
                "link_peers": [],
            }
            by_if[(dev.name, i.name)] = row
            db["dcim/interfaces/"].append(row)
            db["ipam/ip-addresses/"].append(
                {
                    "device_id": dev_id,
                    "address": i.ipv4,
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": row["id"],
                }
            )
    for dev in devices.values():
        for i in dev.interfaces:
            by_if[(dev.name, i.name)]["link_peers"] = [
                {"name": i.peer_interface, "device": {"name": i.peer_device}}
            ]

    def handler(req):
        path = req.url.path.removeprefix("/api/")
        rows = db[path]
        if "device_id" in req.url.params:
            rows = [r for r in rows if str(r["device_id"]) == req.url.params["device_id"]]
        return page(rows)

    return handler


def test_netbox_e_yaml_geram_a_mesma_intencao(devices):
    nb = make(_netbox_from_fabric(devices))
    from_netbox = {d.name: build_intent(d) for d in fetch_devices(nb, "lab-dc1")}
    from_file = {name: build_intent(d) for name, d in devices.items()}
    assert from_netbox == from_file
