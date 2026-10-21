"""Administration et lecture native des automatismes ; aucune activation modèle."""

import json


def register(ctx):
    from arcenal_connectors.edge import call
    from arcenal_connectors.authority_policy import CONTENT

    def operation(args, **kwargs):
        if args.get("action") == "describe" and set(args) == {"action", "argv"}:
            return json.dumps(call("/v1/operations/describe", {"argv": args["argv"]}))
        if args.get("action") == "prepare" and set(args) == {"action", "plan"}:
            return json.dumps(call("/v1/operations", {"plan": args["plan"]}))
        if args.get("action") == "status" and set(args) == {"action", "id"}:
            return json.dumps(call("/v1/operations/status", {"id": args["id"]}))
        return json.dumps({"error": "arguments_non_autorises"})

    ctx.register_system_prompt_section("arcenal.authority", CONTENT, max_chars=3000)
    ctx.register_tool(name="arcenal_operation", toolset="arcenal_operations",
        schema={"name": "arcenal_operation", "description": "Préparer une opération complète à autoriser une fois, puis consulter ses résultats vérifiés. Ne fournit jamais l'accord humain.",
                "parameters": {"type": "object", "properties": {"action": {"type": "string", "enum": ["describe", "prepare", "status"]},
                    "argv": {"type": "array", "items": {"type": "string"}, "description": "Action CLI à examiner sur l'hôte avant de préparer l'opération, par exemple [user,create]."},
                    "id": {"type": "string"}, "plan": {"type": "object", "description": "summary, consequences[], rollback et steps[]. kind=connector : connector/operation/target/data, verify={action,expected}. kind=yunohost_cli : argv[], verify={argv[],expected}, generate_secrets[] facultatif. kind=automation : definition, accord couvrant création ET activation. Aucun secret en clair."}},
                    "required": ["action"], "additionalProperties": False}}, handler=operation)

    def status(args, **kwargs):
        if args != {"operation": "status"}:
            return json.dumps({"error": "arguments_non_autorises"})
        return json.dumps(call("/v1/automations/status", {}))

    ctx.register_tool(name="arcenal_automations", toolset="arcenal_automations",
        schema={"name": "arcenal_automations", "description": "Consulter les automatismes autorisés et leurs exécutions : identifiants, étapes et erreurs. Aucune création ni activation.",
                "parameters": {"type": "object", "additionalProperties": False,
                               "properties": {"operation": {"type": "string", "enum": ["status"]}}, "required": ["operation"]}},
        handler=status)
    ctx.register_system_prompt_section("arcenal.automations", """ARCenal est un administrateur technique avec un exécuteur central durable.
Un automatisme métier doit faire l'objet d'une seule autorisation couvrant sa
création ET son activation, selon la politique arcenal.authority. Une fois autorisé, le worker exécute son périmètre
sans confirmation à chaque répétition. Consulte arcenal_automations si cet outil
est disponible pour connaître les états, étapes et erreurs. N'invente ni flux
actif ni intégration Ksaar : seuls les adaptateurs et automatismes déclarés font
foi. Ne contourne pas un refus par terminal ou navigateur. Les actions sensibles
et l'administration YunoHost restent des capacités séparées à validation unique.
""", max_chars=1200)
