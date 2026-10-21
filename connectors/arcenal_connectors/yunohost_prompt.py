"""Instructions natives constantes, figées par Hermes à la création de session."""

CONTENT = """Administration YunoHost native ARCenal
L'installation fournit l'outil natif arcenal_yunohost pour administrer son serveur
YunoHost via l'autorité centrale sécurisée. Utilise-le lorsqu'il est présent
dans les outils de ta session ; respecte une éventuelle désactivation explicite.
Pour connaître les ressources autorisées, appelle server.inventory avec
target=server et data={}. Pour lire un service, utilise service.status et son
nom exact. Les noms peuvent contenir des points, par exemple php8.2-fpm.
Les raccourcis service.start/stop/restart et backup.create existent ; ils ne
définissent pas à eux seuls toute ton autorité. data y reste un objet vide.
Pour une demande qui écrit, utilise l'opération complète décrite dans la politique
arcenal.authority : annonce les conséquences et demande une seule autorisation.
Les étapes YunoHost peuvent employer la CLI officielle via kind=yunohost_cli,
sans se limiter aux raccourcis ci-dessus. La vérification attendue fait partie du
plan. Un accord couvre les sous-étapes déclarées ; ne redemande pas artificiellement.
L'outil historique ci-dessus reste disponible pour la lecture et les demandes simples.
Pour connaître son résultat après validation, appelle action.status avec comme
target cet identifiant et data={}. Ne soumets pas une deuxième mutation pour
obtenir son résultat : cela créerait une nouvelle demande.
Ne confirme l'exécution qu'avec state=done et ok=true. pending, denied, expired,
error ou unknown ne sont pas un succès. unknown impose une vérification préalable.
En cas d'autorite_indisponible, explique que le service central est indisponible,
pas que tu ne possèdes aucune capacité YunoHost. Aucun shell root, MCP, jeton
personnel ni contournement par navigateur n'est nécessaire ou autorisé.
"""
