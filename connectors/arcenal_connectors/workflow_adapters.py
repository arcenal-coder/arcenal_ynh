"""API métiers réelles du flux projet. Aucun appel Ksaar sans contrat livré."""

import json
import re
from urllib.parse import quote, urlencode
import xml.etree.ElementTree as ET

from .contracts import require, dav_path
from .network import object_response


def project_status(project, field):
    require(field in ("statut", "opp_status") or re.fullmatch(r"array_options\.options_[a-z0-9_]{1,48}", field))
    value = project
    for key in field.split("."):
        require(isinstance(value, dict) and key in value, "statut_projet_absent")
        value = value[key]
    require(type(value) in (str, int) and len(str(value)) <= 80, "statut_projet_invalide")
    return str(value)


class DolibarrProjects:
    def __init__(self, plugin, connection):
        self.plugin, self.connection = plugin, connection

    def read(self, project_id):
        require(re.fullmatch(r"[1-9][0-9]{0,9}", str(project_id)))
        c = self.connection
        value = object_response(self.plugin.network.request(c["config"], "GET", "/projects/" + str(project_id),
                                self.plugin.headers(c["config"], c["secret"])))
        require(str(value.get("id")) == str(project_id), "identite_projet_incorrecte")
        return value

    def link(self, project_id, field):
        value = self.read(project_id).get("array_options", {}).get(field)
        require(value is None or isinstance(value, str), "lien_projet_invalide")
        return value or ""

    def update_link(self, project_id, field, url, run_id, before_write=None):
        c = self.connection
        require(field in c["config"].get("project_link_fields", []), "extrachamp_non_autorise")
        current = self.link(project_id, field)
        require(not current or current == url, "lien_projet_conflit")
        if current != url:
            if before_write is not None:
                before_write()
            body = json.dumps({"array_options": {field: url}, "caller": "arcenal" + run_id}).encode()
            self.plugin.network.request(c["config"], "PUT", "/projects/" + str(project_id),
                                        self.plugin.headers(c["config"], c["secret"]), body)
        require(self.link(project_id, field) == url, "lien_projet_non_confirme")


class NextcloudProjects:
    def __init__(self, plugin, connection):
        self.plugin, self.connection = plugin, connection

    def request(self, method, suffix, body=None, accepted=(), extra_headers=None):
        c = self.connection
        headers = self.plugin.headers(c["config"], c["secret"]) | (extra_headers or {})
        return self.plugin.network.request_response(c["config"], method, suffix, headers, body, accepted=accepted)

    def dav(self, path):
        return "/remote.php/dav/files/" + quote(self.connection["config"]["account"], safe="") + "/" + quote(dav_path(path), safe="/")

    def folder(self, path):
        code, content = self.request("PROPFIND", self.dav(path), accepted=(207, 404), extra_headers={"Depth": "0"})
        if code == 404:
            return None
        require(b"<!DOCTYPE" not in content.upper() and b"<!ENTITY" not in content.upper(), "dav_invalide")
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            require(False, "dav_invalide")
        props = [node.find("{DAV:}prop") for node in root.findall(".//{DAV:}propstat")
                 if "200" in (node.findtext("{DAV:}status") or "")]
        matches = [node for node in props if node is not None and node.find("{DAV:}resourcetype/{DAV:}collection") is not None]
        require(len(matches) == 1, "cible_non_dossier")
        file_id = matches[0].findtext("{http://owncloud.org/ns}fileid")
        require(file_id is not None and re.fullmatch(r"[1-9][0-9]{0,19}", file_id), "identifiant_dossier_absent")
        return file_id

    def ensure_folder(self, path, before_write=None):
        found = self.folder(path)
        if found is None:
            if before_write is not None:
                before_write()
            self.request("MKCOL", self.dav(path), accepted=(405,))
            found = self.folder(path)
        require(found is not None, "dossier_non_confirme")
        return found

    def _ocs(self, method, suffix, body=None):
        _, content = self.request(method, "/ocs/v2.php/apps/files_sharing/api/v1/shares" + suffix, body,
                                  extra_headers={"Content-Type": "application/x-www-form-urlencoded"})
        ocs = object_response(content).get("ocs", {})
        require(ocs.get("meta", {}).get("statuscode") in (100, 200), "partage_refuse")
        return ocs.get("data")

    def _share(self, value, path, group, file_id):
        require(isinstance(value, dict) and str(value.get("share_type")) == "1"
                and value.get("share_with") == group and str(value.get("permissions")) == "1"
                and value.get("uid_owner") == self.connection["config"]["account"]
                and str(value.get("file_source")) == file_id, "partage_non_conforme")
        share_id = str(value.get("id", ""))
        require(re.fullmatch(r"[1-9][0-9]{0,19}", share_id), "partage_invalide")
        return {"share_id": share_id, "file_id": file_id,
                "link": self.connection["config"]["url"] + "/index.php/f/" + file_id}

    def find_share(self, path, group, file_id):
        values = self._ocs("GET", "?" + urlencode({"path": "/" + dav_path(path), "reshares": "true", "format": "json"}))
        require(isinstance(values, list), "partage_invalide")
        matches = [item for item in values if isinstance(item, dict) and str(item.get("share_type")) == "1"
                   and item.get("share_with") == group and item.get("uid_owner") == self.connection["config"]["account"]]
        require(len(matches) <= 1, "partages_multiples_a_verifier")
        return self._share(matches[0], path, group, file_id) if matches else None

    def create_share(self, path, group, file_id):
        require(group in self.connection["config"].get("share_groups", []), "groupe_non_autorise")
        value = self._ocs("POST", "?format=json", urlencode({"path": "/" + dav_path(path),
                          "shareType": 1, "shareWith": group, "permissions": 1}).encode())
        return self._share(value, path, group, file_id)
