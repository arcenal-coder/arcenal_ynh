"""arcenal-dolibarr : contrat central v1, API REST Dolibarr."""

import json

from ..contracts import require, validate_action
from ..network import object_response


class Dolibarr:
    tools = ("contact.create", "contact.delete", "project.read", "project.update_link")

    def __init__(self, network):
        self.network = network

    def headers(self, config, secret):
        result = {"DOLAPIKEY": secret, "Content-Type": "application/json"}
        if config.get("entity") is not None:
            result["DOLAPIENTITY"] = str(config["entity"])
        return result

    def test(self, config, secret, profile):
        value = object_response(self.network.request(config, "GET", "/users/info", self.headers(config, secret)))
        require(value.get("login") == config["account"], "identite_technique_incorrecte")

    def execute(self, config, secret, name, target, data, profile, *, request_id=None):
        validate_action("dolibarr", name, target, data)
        if name.startswith("project."):
            from ..workflow_adapters import DolibarrProjects
            adapter = DolibarrProjects(self, {"config": config, "secret": secret})
            project_id = target.split(":")[1]
            if name == "project.read":
                adapter.read(project_id)
            else:
                adapter.update_link(project_id, data["field"], data["url"], request_id or "manual")
            return {"ok": True}
        if name == "contact.create":
            body = json.dumps(dict(data, socid=int(target.split(":")[1]))).encode()
            self.network.request(config, "POST", "/contacts", self.headers(config, secret), body)
        else:
            self.network.request(config, "DELETE", "/contacts/" + target.split(":")[1], self.headers(config, secret))
        return {"ok": True}
