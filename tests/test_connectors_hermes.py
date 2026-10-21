"""Découverte et dispatch réels des plugins dans un processus Hermes isolé."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROGRAM = r'''
import json, pathlib, os
from unittest.mock import patch
from arcenal_connectors.provision import install_plugins
home=pathlib.Path(os.environ["HERMES_HOME"])
install_plugins(pathlib.Path(os.environ["PLUGIN_SOURCE"]), home, "https://server.test:9443")
(home/"config.yaml").write_text("plugins:\n  enabled: [arcenal-connectors, arcenal-dolibarr, arcenal-nextcloud, arcenal-yunohost]\n")
from hermes_cli.plugins import discover_plugins
discover_plugins()
from tools.registry import registry
from hermes_cli.plugins import render_system_prompt_sections
sections=render_system_prompt_sections({"platform":"cli"})
native=next(section for section in sections if section.id=="arcenal.yunohost")
from arcenal_connectors.authority_policy import CONTENT, QUESTION
authority=next(section for section in sections if section.id=="arcenal.authority")
assert authority.content==CONTENT.strip()
assert QUESTION in authority.content and "sous-étapes" in authority.content
assert "arcenal_yunohost" in native.content and "server.inventory" in native.content
assert "action.status" in native.content
from hermes_cli.tools_config import _get_platform_tools
assert "arcenal_yunohost" in _get_platform_tools({"platform_toolsets":{"cli":["terminal","file"]}},"cli")
assert "arcenal_yunohost" not in _get_platform_tools({"platform_toolsets":{"cli":["terminal","file"]},
    "known_plugin_toolsets":{"cli":["arcenal_yunohost"]}},"cli")
from model_tools import get_tool_definitions, handle_function_call
schemas=get_tool_definitions(enabled_toolsets=["arcenal_yunohost"],quiet_mode=True,skip_tool_search_assembly=True)
schema=next(row["function"] for row in schemas if row["function"]["name"]=="arcenal_yunohost")
assert "server.inventory" in schema["parameters"]["properties"]["operation"]["enum"]
assert "action.status" in schema["parameters"]["properties"]["operation"]["enum"]
with patch("arcenal_connectors.edge.call", return_value={"ok":True,"state":"done"}) as client:
    result=handle_function_call("arcenal_yunohost", {"operation":"server.inventory","target":"server","data":{}},session_id="real_session")
    assert json.loads(result)["ok"], result
    assert client.call_args.args[0]=="/v1/actions"
for app, op, target in (("dolibarr","contact.create","company:1"),("nextcloud","file.mkdir","ARCenal/test"),("yunohost","service.restart","nginx")):
    with patch("arcenal_connectors.edge.call", return_value={"approval_required":True}) as client:
        data={"lastname":"Exemple"} if app=="dolibarr" else {}
        refused=registry.dispatch("arcenal_"+app, {"operation":op,"target":target,"data":data,"session":"forged"},session_id="real_session")
        assert json.loads(refused)["error"]=="arguments_non_autorises"
        assert not client.called
        result=registry.dispatch("arcenal_"+app, {"operation":op,"target":target,"data":data},session_id="real_session")
        assert json.loads(result)["approval_required"], result
        assert client.call_args.args[0]=="/v1/actions"
        assert client.call_args.args[1]["session"].startswith("real_session_")
with patch("arcenal_connectors.edge.call", return_value={"state":"done","ok":True}) as client:
    result=registry.dispatch("arcenal_yunohost", {"operation":"action.status","target":"a"*32,"data":{}},session_id="real_session")
    assert json.loads(result)["state"]=="done"
    assert client.call_args.args==("/v1/actions/status",{"id":"a"*32})
with patch("arcenal_connectors.edge.UnixConnection") as transport:
    transport.return_value.getresponse.return_value.read.return_value=json.dumps({"id":"b"*32,"question":QUESTION,"state":"pending"}).encode()
    refused=registry.dispatch("arcenal_operation", {"action":"approve","id":"b"*32},session_id="real_session")
    assert json.loads(refused)["error"]=="arguments_non_autorises"
    assert not transport.called
    result=registry.dispatch("arcenal_operation", {"action":"prepare","plan":{"summary":"test"}},session_id="real_session")
    assert json.loads(result)["question"]==QUESTION
    assert transport.return_value.request.call_args.args[1]=="/v1/operations"
from hermes_cli.lifecycle import invoke_hook
with patch("arcenal_connectors.edge.call", return_value={"ok":True}) as client:
    invoke_hook("on_session_end", session_id="real_session", turn_id="turn_1", completed=True)
    assert not client.called, "A turn end must not close the permission session"
    invoke_hook("on_session_finalize", session_id="real_session", platform="tui")
    assert client.call_count==1
    assert client.call_args.args[0]=="/v1/sessions/end"
print("Native plugin discovery and scoped tool dispatch: OK")
'''


class HermesPluginTests(unittest.TestCase):
    def test_real_discovery_and_tool_dispatch(self):
        import hermes_cli

        source = Path(hermes_cli.__file__).parent.parent
        package = Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as directory:
            env = {"PATH": os.environ.get("PATH", ""), "HOME": directory, "HERMES_HOME": directory,
                   "HERMES_RUNTIME_DIR": str(Path(directory) / "tools"),
                   "PYTHONPATH": os.pathsep.join((str(source), str(package / "connectors"))),
                   "PLUGIN_SOURCE": str(package / "connectors/hermes-plugins")}
            result = subprocess.run([sys.executable, "-c", PROGRAM], env=env, cwd=directory,
                                    text=True, capture_output=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("scoped tool dispatch: OK", result.stdout)
