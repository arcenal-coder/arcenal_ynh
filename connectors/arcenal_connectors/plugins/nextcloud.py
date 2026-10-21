"""arcenal-nextcloud : contrat central v1, OCS et WebDAV du compte dédié."""

import base64
from urllib.parse import quote

from ..contracts import require, validate_action
from ..network import object_response


class Nextcloud:
    tools = ("file.mkdir", "file.write", "file.delete", "file.share_group", "file.exists")

    def __init__(self, network):
        self.network = network

    def headers(self, config, secret):
        token = base64.b64encode((config["account"] + ":" + secret).encode()).decode()
        return {"Authorization": "Basic " + token, "OCS-APIRequest": "true"}

    def test(self, config, secret, profile):
        value = object_response(self.network.request(config, "GET", "/ocs/v2.php/cloud/user?format=json",
                                                     self.headers(config, secret)))
        require(isinstance(value.get("ocs"), dict), "reponse_distante_invalide")
        ocs = value["ocs"]
        require(ocs.get("meta", {}).get("statuscode") in (100, 200)
                and ocs.get("data", {}).get("id") == config["account"], "identite_technique_incorrecte")

    def execute(self, config, secret, name, target, data, profile, *, request_id=None):
        validate_action("nextcloud", name, target, data)
        if name == "file.share_group":
            from ..workflow_adapters import NextcloudProjects
            adapter = NextcloudProjects(self, {"config": config, "secret": secret})
            file_id = adapter.folder(target)
            require(file_id is not None, "dossier_absent")
            require(data["group"] in config.get("share_groups", []), "groupe_non_autorise")
            if adapter.find_share(target, data["group"], file_id) is None:
                adapter.create_share(target, data["group"], file_id)
            return {"ok": True}
        path = "/remote.php/dav/files/" + quote(config["account"], safe="") + "/" + quote(target, safe="/")
        if name == "file.exists":
            code, _ = self.network.request_response(config, "HEAD", path, self.headers(config, secret), accepted=(404,))
            return {"ok": True, "exists": code != 404}
        method = {"file.mkdir": "MKCOL", "file.write": "PUT", "file.delete": "DELETE"}[name]
        body = data["content"].encode() if name == "file.write" else None
        self.network.request(config, method, path, self.headers(config, secret), body)
        return {"ok": True}
