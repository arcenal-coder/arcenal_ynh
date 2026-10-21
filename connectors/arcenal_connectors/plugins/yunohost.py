"""arcenal-yunohost : identité OS dédiée, opérations fermées, aucun shell."""

import json
import subprocess
import uuid

from ..contracts import Denied, require, validate_action
from ..inventory import validate_inventory


class LocalHelper:
    def approved_cli(self, profile, step, generated_values, request_id):
        payload = {"profile": profile, "operation": "approved.cli", "request_id": request_id,
                   "argv": step["argv"], "verify": step["verify"], "generated_values": generated_values}
        try:
            result = subprocess.run(["/usr/bin/sudo", "-n", "/usr/local/libexec/arcenal-yunohost"],
                input=json.dumps(payload), text=True, capture_output=True, timeout=300, check=False)
            require(result.returncode == 0, "commande_yunohost_echec")
            value = json.loads(result.stdout)
            require(isinstance(value, dict), "preuve_yunohost_invalide")
            return {"ok": value.get("ok") is True, "verified": value.get("verified") is True}
        except (OSError, ValueError, subprocess.SubprocessError):
            raise Denied("commande_yunohost_echec") from None

    def request(self, profile, operation, target, request_id=None):
        try:
            result = subprocess.run(
                ["/usr/bin/sudo", "-n", "/usr/local/libexec/arcenal-yunohost"],
                input=json.dumps({"profile": profile, "operation": operation, "target": target,
                                  "request_id": request_id or uuid.uuid4().hex}),
                text=True, capture_output=True, timeout=300, check=False,
            )
            require(result.returncode == 0, "operation_yunohost_refusee")
            value = json.loads(result.stdout)
            require(isinstance(value, dict) and value.get("ok") is True, "operation_yunohost_refusee")
            if operation == "server.inventory":
                return {"ok": True, "inventory": validate_inventory(value.get("inventory"))}
            return {"ok": True, "state": value.get("state", "termine")}
        except (OSError, ValueError, subprocess.SubprocessError):
            raise Denied("operation_yunohost_refusee") from None


class YunoHost:
    tools = ("server.inventory", "service.status", "service.start", "service.stop", "service.restart", "backup.create")

    def __init__(self, helper):
        self.helper = helper

    def test(self, config, secret, profile):
        targets = config["scope"].get("service.status", [])
        require(targets, "test_yunohost_non_autorise")
        self.helper.request(profile, "service.status", targets[0])

    def execute(self, config, secret, name, target, data, profile, *, request_id=None):
        validate_action("yunohost", name, target, data)
        return self.helper.request(profile, name, target, request_id=request_id)
