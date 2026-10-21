"""Une autorisation humaine, un plan exact, plusieurs étapes et leurs preuves."""

import secrets
import uuid

from .authority_policy import QUESTION
from .cli_authority import action as cli_action, validate as validate_cli
from .contracts import fields, in_scope, operation, require, validate_action
from .store import fingerprint


class Operations:
    def __init__(self, store, validator_allowed, cli_actions):
        self.store, self.validator_allowed, self.cli_actions = store, validator_allowed, cli_actions

    def describe_cli(self, argv):
        descriptor = cli_action(argv, self.cli_actions())
        return {"help": descriptor.get("action_help", ""), "api": descriptor.get("api"),
                "arguments": {name: {"help": value.get("help", ""), "full": value.get("full", name),
                                     "required": bool((value.get("extra") or {}).get("required", False))}
                              for name, value in descriptor.get("arguments", {}).items() if isinstance(value, dict)}}

    def _names(self, step):
        if step["kind"] == "automation":
            return {"dolibarr", "nextcloud"}
        if step["kind"] == "connector":
            names = {step["connector"]}
            if "verify" in step:
                names.add(step["verify"]["action"]["connector"])
            return names
        return set()

    def _check_revisions(self, db, item, step):
        for name in self._names(step):
            current = self.store._active_connector(db, name)
            require(current["revision"] == item["revisions"].get(name), "connecteur_modifie_nouveau_plan_requis")

    def _connector(self, db, step, verification=False):
        fields(step, ("kind", "connector", "operation", "target", "data"), () if verification else ("verify",))
        require(step["kind"] == "connector")
        validate_action(step["connector"], step["operation"], step["target"], step["data"])
        descriptor = operation(step["connector"], step["operation"])
        require(not verification or not descriptor.writes, "verification_non_lecture")
        connection = self.store._active_connector(db, step["connector"])
        scope = connection["config"]["scope"]
        permitted = in_scope(step["connector"], step["operation"], step["target"], scope)
        if verification and step["connector"] == "nextcloud" and step["operation"] == "file.exists":
            permitted = permitted or any(in_scope("nextcloud", name, step["target"], scope)
                                        for name in ("file.mkdir", "file.write", "file.delete"))
        require(permitted, "cible_hors_perimetre_du_connecteur")
        return connection

    def _validate(self, db, step):
        require(isinstance(step, dict))
        if step.get("kind") == "automation":
            from .automation_contract import definition
            from .automations import Automations
            fields(step, ("kind", "definition"))
            spec = definition(step["definition"])
            Automations(self.store, self.validator_allowed)._connections(db, {"spec": spec})
            return
        if step.get("kind") == "yunohost_cli":
            fields(step, ("kind", "argv", "verify"), ("generate_secrets",))
            require(isinstance(step["argv"], list), "arguments_cli_invalides")
            generated = step.get("generate_secrets", [])
            require(isinstance(generated, list) and len(generated) <= 5 and
                    all(isinstance(flag, str) and flag.startswith("--") for flag in generated))
            require(all(step["argv"].count(flag) == 1 and step["argv"].index(flag) + 1 < len(step["argv"])
                        and step["argv"][step["argv"].index(flag) + 1] == "@server-secret" for flag in generated), "emplacement_secret_invalide")
            actions = self.cli_actions()
            validate_cli(step["argv"], actions, generated=generated)
            fields(step["verify"], ("argv", "expected"))
            require(isinstance(step["verify"]["expected"], dict) and bool(step["verify"]["expected"]), "preuve_attendue_requise")
            validate_cli(step["verify"]["argv"], actions, verification=True)
            return
        connection = self._connector(db, step)
        descriptor = operation(step["connector"], step["operation"])
        if descriptor.writes:
            fields(step["verify"], ("action", "expected"))
            self._connector(db, step["verify"]["action"], verification=True)
            require(isinstance(step["verify"]["expected"], dict) and bool(step["verify"]["expected"]), "preuve_attendue_requise")
            if step["connector"] == "nextcloud" and step["operation"] in ("file.mkdir", "file.write", "file.delete"):
                proof = step["verify"]["action"]
                require(proof["connector"] == "nextcloud" and proof["operation"] == "file.exists"
                        and proof["target"] == step["target"]
                        and step["verify"]["expected"].get("exists") is (step["operation"] != "file.delete"),
                        "preuve_de_la_cible_requise")
        return connection

    def prepare(self, value):
        fields(value, ("summary", "consequences", "steps", "rollback"))
        require(isinstance(value["summary"], str) and 1 <= len(value["summary"]) <= 500)
        require(value["rollback"] is None or isinstance(value["rollback"], str) and 1 <= len(value["rollback"]) <= 2000)
        require(isinstance(value["consequences"], list) and 0 < len(value["consequences"]) <= 10
                and all(isinstance(v, str) and 0 < len(v) <= 500 for v in value["consequences"]))
        require(isinstance(value["steps"], list) and bool(value["steps"]))
        with self.store.transaction("agent") as db:
            self.store._no_secret(db, value)
            for step in value["steps"]:
                self._validate(db, step)
            item = {"id": uuid.uuid4().hex, "plan": value, "digest": fingerprint(value),
                    "state": "pending", "created_at": self.store.clock(), "results": [],
                    "revisions": {name: self.store._active_connector(db, name)["revision"]
                                  for step in value["steps"] for name in self._names(step)}}
            self.store._write(db, "operation", item["id"], item)
            self.store._audit(db, "operation_demandee", "agent", request_id=item["id"])
        return {"id": item["id"], "question": QUESTION, "approval_required": True, "digest": item["digest"], "state": "pending"}

    def state(self, actor):
        with self.store.transaction(actor) as db:
            return {"operations": [value for _, value in self.store._items(db, "operation")]}

    def status(self, operation_id):
        with self.store.transaction("agent") as db:
            item = self.store._read(db, "operation", operation_id)
            require(item is not None, "operation_absente")
            return {key: item.get(key) for key in ("id", "state", "results", "failed_step", "error", "rollback", "validator")}

    def decide(self, actor, operation_id, digest, accept):
        require(type(accept) is bool)
        with self.store.transaction(actor) as db:
            item = self.store._read(db, "operation", operation_id)
            require(item and item["state"] == "pending", "operation_inactive")
            require(digest == item["digest"] == fingerprint(item["plan"]), "plan_modifie")
            require(self.validator_allowed(actor), "validateur_non_autorise")
            if not accept:
                item.update(state="denied", validator=actor)
                self.store._write(db, "operation", operation_id, item)
                self.store._audit(db, "operation_refusee", actor, request_id=operation_id)
                return {"id": operation_id, "state": "denied"}
            for step in item["plan"]["steps"]:
                self._validate(db, step)
                self._check_revisions(db, item, step)
            item.update(state="executing", validator=actor, rollback=item["plan"]["rollback"],
                        approved_at=self.store.clock())
            self.store._write(db, "operation", operation_id, item)
            self.store._audit(db, "operation_validee", actor, request_id=operation_id)
        return self._execute(item)

    def _invoke(self, step, connection, operation_id):
        return self.store.plugins[step["connector"]].execute(connection["config"], connection["secret"],
                    step["operation"], step["target"], step["data"], self.store.profile, request_id=operation_id)

    def _execute(self, item):
        from .cli_authority import subset
        for index, step in enumerate(item["plan"]["steps"]):
            attempted = False
            try:
                with self.store.transaction(item["validator"]) as db:
                    current = self.store._read(db, "operation", item["id"])
                    require(current["state"] == "executing" and self.validator_allowed(item["validator"]), "autorisation_revoquee")
                    connection = self._validate(db, step)
                    self._check_revisions(db, item, step)
                    values = {flag: secrets.token_urlsafe(32) for flag in step.get("generate_secrets", [])}
                    if values:
                        self.store._write(db, "operation_secret", item["id"] + ":" + str(index), values)
                    self.store._audit(db, "operation_etape_reservee_" + str(index), item["validator"], request_id=item["id"])
                attempted = True
                if step["kind"] == "automation":
                    from .automations import Automations
                    engine = Automations(self.store, self.validator_allowed)
                    created = engine.save(item["validator"], step["definition"], True)
                    engine.activate(item["validator"], created["id"], created["version"], True)
                    state = next(value for value in engine.state(item["validator"])["automations"] if value["id"] == created["id"])
                    require(state["enabled"] and state["version"] == created["version"], "activation_non_confirmee")
                elif step["kind"] == "yunohost_cli":
                    result = self.store.plugins["yunohost"].helper.approved_cli(self.store.profile, step, values, item["id"])
                    require(result.get("ok") and result.get("verified"), "execution_ou_verification_echec")
                else:
                    result = self._invoke(step, connection, item["id"])
                    require(result.get("ok") is True, "execution_echec")
                    if "verify" in step:
                        with self.store.transaction(item["validator"]) as db:
                            verify_connection = self._connector(db, step["verify"]["action"], verification=True)
                            self._check_revisions(db, item, step)
                        proof = self._invoke(step["verify"]["action"], verify_connection, item["id"])
                        require(subset(proof, step["verify"]["expected"]), "verification_echec")
                item["results"].append({"step": index, "executed": True, "verified": True})
                with self.store.transaction(item["validator"]) as db:
                    self.store._write(db, "operation", item["id"], item)
                    self.store._audit(db, "operation_etape_verifiee_" + str(index), item["validator"], request_id=item["id"])
            except Exception:
                item["results"].append({"step": index, "execution": "unknown_or_partial" if attempted else "not_started", "verified": False})
                item.update(state="error", failed_step=index, error="execution_ou_verification_echec")
                break
        else:
            item["state"] = "done"
        with self.store.transaction(item["validator"]) as db:
            self.store._write(db, "operation", item["id"], item)
            self.store._audit(db, "operation_" + item["state"], item["validator"], request_id=item["id"])
        return self.status(item["id"])

    def recover_interrupted(self):
        with self.store.transaction("server") as db:
            for key, item in self.store._items(db, "operation"):
                if item["state"] == "executing":
                    item.update(state="unknown", error="verification_manuelle_requise")
                    self.store._write(db, "operation", key, item)
                    self.store._audit(db, "operation_interrompue", "server", request_id=key)
