"""Autorisations durables de flux, observations et journal d'exécution chiffrés."""

import threading
import uuid

from .automation_contract import ACTIONS, ACTION_REGISTRY, definition, paths
from .contracts import Denied, in_scope, require
from .store import fingerprint
from .workflow_adapters import DolibarrProjects, NextcloudProjects, project_status


class Automations:
    def __init__(self, store, owner_allowed):
        self.store, self.owner_allowed = store, owner_allowed
        self.tick_lock = threading.Lock()

    def _revoke_authorization(self, db, item):
        previous = self.store._read(db, "automation_authorization", item.get("epoch", ""))
        if previous is not None:
            previous["revoked"] = True
            self.store._write(db, "automation_authorization", item["epoch"], previous)

    def save(self, actor, value, confirmed=False):
        require(confirmed is True, "validation_humaine_requise")
        spec = definition(value)
        with self.store.transaction(actor) as db:
            self.store._no_secret(db, spec)
            old = self.store._read(db, "automation", spec["id"], {})
            require(not old or old["owner"] == actor, "proprietaire_requis")
            if old and old["spec"] == spec and old.get("action_contract") == fingerprint(ACTION_REGISTRY):
                return old
            if old:
                self._revoke_authorization(db, old)
            version = old.get("version", 0) + 1
            item = {"id": spec["id"], "owner": actor, "version": version, "enabled": False,
                    "epoch": uuid.uuid4().hex, "spec": spec, "actions": list(ACTIONS),
                    "action_contract": fingerprint(ACTION_REGISTRY), "schema": 1}
            self.store._write(db, "automation_version", spec["id"] + ":" + str(version), item)
            self.store._write(db, "automation", spec["id"], item)
            self.store._audit(db, "automate_definition_validee", actor, request_id=spec["id"])
            return item

    def _connections(self, db, item):
        spec = item["spec"]
        connections = {name: self.store._active_connector(db, name) for name in ("dolibarr", "nextcloud")}
        for project in spec["projects"]:
            for op in ("project.read", "project.update_link"):
                require(in_scope("dolibarr", op, "project:" + project, connections["dolibarr"]["config"]["scope"]), "projet_hors_perimetre")
            for path in paths(spec, project):
                require(in_scope("nextcloud", "file.mkdir", path, connections["nextcloud"]["config"]["scope"]), "dossier_hors_perimetre")
            require(in_scope("nextcloud", "file.share_group", paths(spec, project)[0], connections["nextcloud"]["config"]["scope"]), "partage_hors_perimetre")
        require(spec["share_group"] in connections["nextcloud"]["config"].get("share_groups", []), "groupe_non_autorise")
        require(spec["link_field"] in connections["dolibarr"]["config"].get("project_link_fields", []), "extrachamp_non_autorise")
        require(not spec["ksaar_required"], "contrat_ksaar_non_disponible")
        return connections

    def activate(self, actor, automation_id, version, confirmed=False):
        require(confirmed is True, "validation_humaine_requise")
        require(type(version) is int and version > 0, "version_invalide")
        with self.store.transaction(actor) as db:
            item = self.store._read(db, "automation", automation_id)
            require(item and item["owner"] == actor and item["version"] == version, "version_ou_proprietaire_invalide")
            require(self.owner_allowed(actor), "proprietaire_non_autorise")
            require(item["actions"] == list(ACTIONS), "contrat_actions_modifie_reactivation_requise")
            require(item["action_contract"] == fingerprint(ACTION_REGISTRY), "contrat_actions_modifie_reactivation_requise")
            connections = self._connections(db, item)
            revisions = {name: value["revision"] for name, value in connections.items()}
            if item["enabled"] and item.get("revisions") == revisions and item.get("approved_hash") == fingerprint(item["spec"]):
                return {"ok": True, "version": version, "already_active": True}
            self._revoke_authorization(db, item)
            item.update(enabled=True, epoch=uuid.uuid4().hex, approved_hash=fingerprint(item["spec"]),
                        revisions=revisions, next_poll=0)
            self.store._write(db, "automation", automation_id, item)
            self.store._write(db, "automation_authorization", item["epoch"], {
                "id": item["epoch"], "automation": automation_id, "version": version, "owner": actor,
                "approved_at": self.store.clock(), "spec_hash": item["approved_hash"],
                "actions_hash": item["action_contract"], "revisions": revisions, "revoked": False})
            self.store._audit(db, "automate_active", actor, request_id=automation_id)
            return {"ok": True, "version": version}

    def disable(self, actor, automation_id, confirmed=False):
        require(confirmed is True, "validation_humaine_requise")
        with self.store.transaction(actor) as db:
            item = self.store._read(db, "automation", automation_id)
            require(item is not None, "automate_absent")
            self._revoke_authorization(db, item)
            item.update(enabled=False, epoch=uuid.uuid4().hex)
            self.store._write(db, "automation", automation_id, item)
            self.store._audit(db, "automate_revoque", actor, request_id=automation_id)
        return {"ok": True}

    def state(self, actor):
        with self.store.transaction(actor) as db:
            items = [item for _, item in self.store._items(db, "automation")]
            runs = [{k: run.get(k) for k in ("id", "automation", "version", "epoch", "owner", "authorized_revisions", "project", "state", "step", "steps", "error", "attempt", "updated")}
                    for _, run in self.store._items(db, "automation_run")]
            return {"automations": items, "runs": sorted(runs, key=lambda r: r["updated"], reverse=True)[:100],
                    "poll_errors": {key: value for key, value in self.store._items(db, "automation_poll_error")},
                    "ksaar_available": False, "trigger": "authenticated_polling"}

    def _authorized(self, db, item):
        current = self.store._read(db, "automation", item["id"])
        require(current and current["enabled"] and current["version"] == item["version"]
                and current["epoch"] == item["epoch"], "automate_desactive_ou_modifie")
        require(self.owner_allowed(current["owner"]) and current["approved_hash"] == fingerprint(current["spec"]), "autorisation_revoquee")
        require(current.get("schema") == 1 and current["actions"] == list(ACTIONS), "contrat_actions_modifie_reactivation_requise")
        require(current["action_contract"] == fingerprint(ACTION_REGISTRY), "contrat_actions_modifie_reactivation_requise")
        consent = self.store._read(db, "automation_authorization", current["epoch"])
        require(consent and not consent["revoked"] and consent["owner"] == current["owner"]
                and consent["version"] == current["version"] and consent["spec_hash"] == current["approved_hash"]
                and consent["actions_hash"] == current["action_contract"]
                and consent["revisions"] == current["revisions"], "autorisation_revoquee")
        connections = self._connections(db, current)
        require(current["revisions"] == {name: c["revision"] for name, c in connections.items()}, "connecteur_modifie_reactivation_requise")
        return connections

    def preview(self, actor, automation_id, project):
        with self.store.transaction(actor) as db:
            item = self.store._read(db, "automation", automation_id)
            require(item and item["owner"] == actor and project in item["spec"]["projects"], "projet_non_autorise")
            connections = self._connections(db, item)
        source = DolibarrProjects(self.store.plugins["dolibarr"], connections["dolibarr"])
        status = project_status(source.read(project), item["spec"]["status_field"])
        with self.store.transaction(actor) as db:
            self.store._no_secret(db, status)
        return {"dry_run": True, "project": project, "current_status": status,
                "paths": paths(item["spec"], project), "group": item["spec"]["share_group"],
                "actions": list(ACTIONS), "ksaar": "not_available", "writes": 0}

    def _observe(self, item, project, status):
        key = item["id"] + ":" + str(item["version"]) + ":" + item["epoch"] + ":" + project
        with self.store.transaction("scheduler") as db:
            self._authorized(db, item)
            previous = self.store._read(db, "automation_observation", key)
            if previous and previous["status"] == status:
                return
            seq = previous["seq"] + 1 if previous else 0
            self.store._write(db, "automation_observation", key, {"status": status, "seq": seq})
            if not previous or previous["status"] != item["spec"]["from_status"] or status not in item["spec"]["to_statuses"]:
                return
            run_id = fingerprint({"observation": key, "sequence": seq})[:32]
            if self.store._read(db, "automation_run", run_id):
                return
            run = {"id": run_id, "automation": item["id"], "version": item["version"], "epoch": item["epoch"],
                   "owner": item["owner"], "authorized_revisions": item["revisions"],
                   "project": project, "to_status": status, "state": "queued", "step": "verify", "steps": {},
                   "attempt": 0, "updated": self.store.clock(), "retry_at": 0, "lease_until": 0}
            self.store._write(db, "automation_run", run_id, run)
            self.store._audit(db, "automate_transition_recue", "scheduler", request_id=run_id)

    def _checkpoint(self, run, item, step, result=None):
        with self.store.transaction("automation") as db:
            connections = self._authorized(db, item)
            for name, connection in connections.items():
                connection["last_used"] = self.store.clock()
                self.store._write(db, "connector", name, connection)
            current = self.store._read(db, "automation_run", run["id"])
            require(current["lease"] == run["lease"], "bail_perdu")
            if result is not None:
                current["steps"][step] = result
            current.update(step=step, lease_until=self.store.clock() + 120, updated=self.store.clock())
            self.store._write(db, "automation_run", run["id"], current)
            self.store._audit(db, "automate_etape_" + step, "automation", request_id=run["id"])
            run.update(current)
            return connections

    def _effect(self, run, key, value=None):
        with self.store.transaction("automation") as db:
            item = self.store._read(db, "automation", run["automation"])
            self._authorized(db, item)
            require(item["epoch"] == run["epoch"], "autorisation_revoquee")
            old = self.store._read(db, "automation_effect", key)
            if value is not None:
                self.store._write(db, "automation_effect", key, value)
            elif old is None:
                self.store._write(db, "automation_effect", key, {"state": "intent", "run": run["id"]})
            return old

    def _execute(self, run, item):
        spec = item["spec"]
        connections = self._checkpoint(run, item, "verify")
        source = DolibarrProjects(self.store.plugins["dolibarr"], connections["dolibarr"])
        destination = NextcloudProjects(self.store.plugins["nextcloud"], connections["nextcloud"])
        require(project_status(source.read(run["project"]), spec["status_field"]) == run["to_status"], "transition_devenue_ineligible")
        require(destination.folder(spec["base_folder"]) is not None, "dossier_racine_absent")
        tree = paths(spec, run["project"])
        for index, path in enumerate(tree):
            self._checkpoint(run, item, "folder_" + str(index))
            file_id = destination.ensure_folder(path, lambda: self._checkpoint(run, item, "folder_" + str(index)))
            self._checkpoint(run, item, "folder_" + str(index), {"done": True, "file_id": file_id})
        self._checkpoint(run, item, "share")
        file_id = destination.folder(tree[0])
        require(file_id == run["steps"]["folder_0"]["file_id"], "dossier_remplace_a_verifier")
        share = destination.find_share(tree[0], spec["share_group"], file_id)
        effect_key = fingerprint({"application": connections["nextcloud"]["config"]["url"],
                                  "account": connections["nextcloud"]["config"]["account"],
                                  "path": tree[0], "group": spec["share_group"]})
        if share is None:
            previous = self._effect(run, effect_key)
            require(previous is None, "partage_incertain_a_verifier")
            self._checkpoint(run, item, "share")
            share = destination.create_share(tree[0], spec["share_group"], file_id)
        self._effect(run, effect_key, {"state": "done", "share_id": share["share_id"]})
        self._checkpoint(run, item, "share", {"done": True, "share_id": share["share_id"]})
        self._checkpoint(run, item, "ksaar", {"state": "not_applicable", "reason": "connector_not_delivered"})
        self._checkpoint(run, item, "dolibarr")
        require(project_status(source.read(run["project"]), spec["status_field"]) == run["to_status"], "transition_devenue_ineligible")
        project_effect = fingerprint({"application": connections["dolibarr"]["config"]["url"],
                                      "project": run["project"], "field": spec["link_field"], "link": share["link"]})
        if source.link(run["project"], spec["link_field"]) != share["link"]:
            require(self._effect(run, project_effect) is None, "ecriture_projet_incertaine_a_verifier")
            self._checkpoint(run, item, "dolibarr")
            source.update_link(run["project"], spec["link_field"], share["link"], run["id"],
                               lambda: self._checkpoint(run, item, "dolibarr"))
        self._effect(run, project_effect, {"state": "done"})
        self._checkpoint(run, item, "dolibarr", {"done": True})
        with self.store.transaction("automation") as db:
            self._authorized(db, item)
            current = self.store._read(db, "automation_run", run["id"])
            require(current["lease"] == run["lease"], "bail_perdu")
            run.update(state="done", lease_until=0, updated=self.store.clock(), error=None)
            self.store._write(db, "automation_run", run["id"], run)
            self.store._audit(db, "automate_execution_reussie", "automation", request_id=run["id"])

    def retry(self, actor, run_id, confirmed=False):
        require(confirmed is True, "validation_humaine_requise")
        with self.store.transaction(actor) as db:
            run = self.store._read(db, "automation_run", run_id)
            require(run and run["state"] in ("failed", "needs_review"), "execution_non_reprenable")
            item = self.store._read(db, "automation", run["automation"])
            require(item["owner"] == actor, "proprietaire_requis")
            self._authorized(db, item)
            require(run["epoch"] == item["epoch"], "version_execution_obsolete")
            run.update(state="queued", retry_at=0, lease_until=0)
            self.store._write(db, "automation_run", run_id, run)
        return {"ok": True}

    def tick(self):
        if not self.tick_lock.acquire(blocking=False):
            return
        try:
            self._tick()
        finally:
            self.tick_lock.release()

    def _tick(self):
        with self.store.transaction("scheduler") as db:
            items = [item for _, item in self.store._items(db, "automation") if item["enabled"]]
        for item in items:
            if item.get("next_poll", 0) <= self.store.clock():
                try:
                    with self.store.transaction("scheduler") as db:
                        connections = self._authorized(db, item)
                        connections["dolibarr"]["last_used"] = self.store.clock()
                        self.store._write(db, "connector", "dolibarr", connections["dolibarr"])
                        item["next_poll"] = self.store.clock() + item["spec"]["interval"]
                        self.store._write(db, "automation", item["id"], item)
                    source = DolibarrProjects(self.store.plugins["dolibarr"], connections["dolibarr"])
                    for project in item["spec"]["projects"]:
                        self._observe(item, project, project_status(source.read(project), item["spec"]["status_field"]))
                    with self.store.transaction("scheduler") as db:
                        db.execute("delete from items where kind='automation_poll_error' and id=?", (item["id"],))
                except Denied as error:
                    with self.store.transaction("scheduler") as db:
                        self.store._write(db, "automation_poll_error", item["id"], {"code": error.code, "time": self.store.clock()})
                        self.store._audit(db, "automate_observation_echec", "scheduler", request_id=item["id"])
            with self.store.transaction("scheduler") as db:
                candidates = [r for _, r in self.store._items(db, "automation_run") if r["automation"] == item["id"]
                              and r["epoch"] == item["epoch"] and r.get("retry_at", 0) <= self.store.clock()
                              and (r["state"] == "queued" or r["state"] == "running" and r["lease_until"] < self.store.clock())]
            for run in candidates:
                try:
                    with self.store.transaction("scheduler") as db:
                        self._authorized(db, item)
                        current = self.store._read(db, "automation_run", run["id"])
                        require(current["state"] == "queued" or
                                current["state"] == "running" and current["lease_until"] < self.store.clock(), "execution_deja_reservee")
                        run = current | {"state": "running", "lease": uuid.uuid4().hex,
                                         "lease_until": self.store.clock() + 120, "attempt": current["attempt"] + 1}
                        self.store._write(db, "automation_run", run["id"], run)
                    self._execute(run, item)
                except Exception as error:
                    code = error.code if isinstance(error, Denied) else "service_indisponible"
                    with self.store.transaction("scheduler") as db:
                        current = self.store._read(db, "automation_run", run["id"])
                        if current.get("lease") != run.get("lease"):
                            continue
                        review = code in ("partage_incertain_a_verifier", "partages_multiples_a_verifier", "lien_projet_conflit", "dossier_remplace_a_verifier", "ecriture_projet_incertaine_a_verifier")
                        retryable = code in ("connexion_impossible", "delai_connexion_depasse", "service_indisponible") and run["attempt"] < 5
                        current.update(state="needs_review" if review else "queued" if retryable else "failed",
                                       error=code, lease_until=0, retry_at=self.store.clock() + 60 * run["attempt"], updated=self.store.clock())
                        self.store._write(db, "automation_run", run["id"], current)
                        self.store._audit(db, "automate_execution_echec_" + current["step"], "scheduler", request_id=run["id"])
