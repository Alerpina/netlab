import json

import httpx
import pytest

from netauto.srl_client import SRLClient, SRLError


def client(handler):
    return SRLClient("10.0.0.1", "admin", "x", transport=httpx.MockTransport(handler))


def test_get_monta_o_json_rpc():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content), url=str(req.url))
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": [{"version": "v24"}]})

    assert client(handler).get("/system/information", datastore="state") == {"version": "v24"}
    assert seen["url"] == "https://10.0.0.1/jsonrpc"
    assert seen["method"] == "get"
    assert seen["params"]["commands"] == [{"path": "/system/information", "datastore": "state"}]


def test_erro_do_equipamento_vira_excecao():
    def handler(req):
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "error": {"message": "Path not valid"}})

    with pytest.raises(SRLError, match="Path not valid"):
        client(handler).get("/nada")


def test_falha_de_rede_vira_excecao():
    def handler(req):
        raise httpx.ConnectError("recusado")

    with pytest.raises(SRLError, match="ConnectError"):
        client(handler).get("/system")
