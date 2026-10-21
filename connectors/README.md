# ARCenal Connecteurs — contrats centraux v1

Extension AUT-01 locale : définitions d'automatismes validées par leur propriétaire,
worker déterministe, journal et effets persistants dans le coffre existant. Les
actions métier approuvées sont exécutées sans validation à chaque répétition.
Contrat et limites : `../doc/AUTOMATISMES.md`. Aucun adaptateur Ksaar fictif.

Ces composants appartiennent à la distribution ARCenal, pas au cœur Hermes.
Le service central est l'autorité de secrets, d'autorisations et d'audit. Les
plugins Hermes ne disposent que d'une identité OS liée à un profil et du droit de
demander une action. Les routes de validation ne sont pas servies sur leur socket.

## Contrats initiaux autorisés

| Plugin central | Opérations | Périmètre |
| --- | --- | --- |
| arcenal-dolibarr | contact.create, contact.delete | sociétés/contact IDs explicites, entité éventuelle |
| arcenal-nextcloud | file.mkdir, file.write, file.delete | sous-arbres DAV explicites du compte technique |
| arcenal-yunohost | server.inventory, service.status/start/stop/restart, backup.create | ressources enrôlées par l'installateur ; mutations toujours validées humainement |

Tout autre nom, paramètre, application ou opération est refusé. Les suppressions
et toutes les mutations YunoHost exigent une nouvelle validation unique. Aucune
permission permanente globale. L'API serveur ne renvoie jamais un secret.

Le client natif fournit aussi `action.status`, lecture du résultat d'une demande
du profil, sans création ni validation d'une autre action. Les consignes YunoHost
sont enregistrées par l'API native Hermes et figées au début de chaque session.

Propriétaire : administrateur de la distribution ARCenal. Point d'entrée :
socket Unix agent `/run/arcenal-connectors/agent.sock`, contrat JSON `/v1/actions`.
Authentification : UID du pair vérifié par le noyau, associé à un seul profil.
Un UID distinct par client est obligatoire ; aucun nouveau jeton dans `.env`.
Administration : socket Unix séparé réservé au proxy Nginx/SSOwat, utilisateur
SSO et affectation explicite profil/administrateur. Erreurs publiques normalisées,
sans corps ni exception provenant des services externes.

## Conditions préalables à toute exécution

Compte technique dédié, URL HTTPS sans identifiant/query/fragment, secret écrit
une seule fois au coffre, opération et cible autorisées, connexion testée,
demande non expirée, révision du connecteur inchangée, audit intègre et écrit
avant l'appel. Les redirections HTTP et les cibles réseau non autorisées sont
refusées. Les adresses privées requièrent une autorisation système explicite.

Une autorisation unique est consommée avant l'appel, même en cas d'erreur réseau :
une erreur ne provoque jamais de nouvelle tentative automatique. Les événements
d'audit n'incluent ni payload métier, ni secret, ni réponse brute du service.

## État de qualification

Contrats nouvellement créés conformément à la mission client. Aucune exécution
réelle, compatibilité SSOwat ou qualification YunoHost n'est affirmée par ce document.
