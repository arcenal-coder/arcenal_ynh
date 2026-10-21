# Administration YunoHost native dans Hermes

Évolution locale OP-01 : le plan approuvé peut utiliser les commandes officielles
réellement déclarées par l'hôte, au-delà des raccourcis ci-dessous. Une confirmation
couvre l'opération entière et ses vérifications. Voir `AUTORITE_OPERATIONNELLE.md`.

Candidate `0.22.2~ynh5`, publication Preview autorisée ; non installée sur le serveur.
Les versions précédentes, dont l'assistance Matos `~ynh4`, n'incluent pas cette fonction.

## Fonction fournie

Le plugin natif `arcenal-yunohost` enregistre directement l'outil
`arcenal_yunohost` auprès d'Hermes. Il ne dépend ni d'un MCP, ni d'un navigateur,
ni d'un compte administrateur personnel. L'autorité centrale et le helper
YunoHost existants restent les seules voies d'exécution privilégiée.

Hermes reçoit également une section d'instructions par son API officielle
`register_system_prompt_section`. Elle explique les opérations, le suivi de
validation et les erreurs possibles. Le texte est constant et figé par session :
aucune reconstruction de contexte ou modification de prompt en cours d'échange.

Les jeux d'outils des plugins récemment activés sont intégrés par le résolveur
natif Hermes. Une désactivation explicite déjà enregistrée reste respectée.
Après installation/mise à jour, **ouvrir une nouvelle conversation** pour
prendre en compte les capacités et instructions nouvelles.

## Utilisation depuis le chat

Exemples de demandes naturelles :

- « Donne-moi l'inventaire des applications, services et domaines autorisés. »
- « Vérifie l'état du service PHP indiqué par l'inventaire. »
- « Redémarre ce service après ma validation dans Connecteurs. »
- « Prépare une sauvegarde de Nextcloud et attends ma validation. »
- « Vérifie si ma demande a été exécutée. »

Contrat de l'outil :

| `operation` | `target` | `data` | Validation |
| --- | --- | --- | --- |
| `server.inventory` | `server` | `{}` | Lecture autorisée |
| `service.status` | Nom exact du service | `{}` | Lecture autorisée |
| `service.start` | Nom exact du service | `{}` | Humaine unique |
| `service.stop` | Nom exact du service | `{}` | Humaine unique |
| `service.restart` | Nom exact du service | `{}` | Humaine unique |
| `backup.create` | Identifiant d'application | `{}` | Humaine unique |
| `action.status` | ID opaque de la demande | `{}` | Lecture, profil propriétaire |

Une réponse `pending` ne signifie jamais que l'action a été exécutée. Une fois
la carte validée/refusée dans la console, Hermes peut consulter `action.status`
sans envoyer à nouveau la mutation. Un refus, une expiration ou une erreur ne
provoque aucune exécution supplémentaire.
Une réservation interrompue par un redémarrage de l'autorité devient `unknown` :
vérifier la cible avant toute nouvelle demande, sans rejeu automatique.

## Initialisation à l'installation

L'installateur root collecte l'inventaire par les commandes officielles :
`yunohost app list`, `yunohost service status`, `yunohost domain list`, en JSON.
Seuls les identifiants sont conservés ; réglages, clés et réponses brutes sont
ignorés. L'enrôlement est borné à 50 identifiants par catégorie.

Pour le profil serveur initial, il crée le connecteur YunoHost sans secret
réutilisable. L'identité est celle du pair Unix, vérifiée par le noyau. Au premier
usage, le serveur teste la connexion par une lecture de l'état d'`arcenal`.
Un test en échec bloque les opérations ; il n'accorde jamais de droits en secours.

Le plafond système initial comprend les services/applications enrôlés. Les
mutations sont disponibles mais **aucune n'est autorisée sans validation humaine**.
Les plafonds et désactivations existants ne sont pas élargis lors d'une relance.
Un client supplémentaire ne reçoit pas implicitement l'administration du serveur.

L'arrêt du proxy, du SSH, de LDAP, du portail d'authentification et de l'autorité
est protégé. L'agent ne peut pas redémarrer/arrêter ses propres services ni faire
sa propre sauvegarde via ce helper : utiliser YunoHost directement pour cela.
Les contrôles de service passent par `yunohost service start/stop/restart`, avec
un nom unique, sans shell ni argument libre. Les journaux des services et les
réglages susceptibles de contenir des secrets ne sont pas renvoyés au modèle.

## État de vérification

Les tests isolés couvrent l'inventaire, l'initialisation sans secret, les services
avec points dans le nom, les demandes validées et leur suivi, les refus, la
conservation des restrictions, et la découverte par le vrai résolveur/schema
d'outils Hermes. Les commandes privilégiées ne sont pas exécutées sur le serveur.

La recette YunoHost réelle et celle des API/SSO restent à effectuer avant une
publication ou installation. Procédure complète : `CONNECTEURS.md` ; résultats
du dernier contrôle : `TEST_REPORT.md`.
