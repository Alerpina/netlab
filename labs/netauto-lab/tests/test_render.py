import json

from netauto.model import devices_from_fabric
from netauto.render import render


def test_render_gera_json_cli_e_manifest(fabric, tmp_path):
    hosts = render(devices_from_fabric(fabric), tmp_path, "file")
    assert hosts == ["leaf1", "leaf2", "spine1", "spine2"]
    intent = json.loads((tmp_path / "spine1.json").read_text())
    assert intent["host"] == "spine1"
    cli = (tmp_path / "spine1.cli").read_text()
    assert cli.startswith("# spine1 (spine)")
    assert 'set / interface ethernet-1/1 description "to leaf1 ethernet-1/49"\n' in cli
    assert "\n\n" not in cli
    assert json.loads((tmp_path / "manifest.json").read_text())["hosts"] == hosts
