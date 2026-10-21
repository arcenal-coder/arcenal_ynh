# AUT-01 — diagnostic et automatisation autorisée

Candidate locale `0.22.2~ynh6`, base `~ynh5` `f582c31`. Aucun commit,
publication, déploiement, changement de privilèges ou opération métier réelle.

## État des lieux AVANT modification (20 octobre 2026)

Lecture seule effectuée avant ce document : états `.arcenal/`, statuts Git des
trois dépôts, services, manifeste, proxys SSO, helper et adaptateurs réellement
présents. L'historique `/Users/compteonyx/Downloads/arcenal-agent.json` contient
839 messages (52 utilisateur). Extraction structurée en lecture seule, sans
exécution des anciens ordres ni reprise de journaux/secrets dans ce rapport.

| Élément | Constat prouvé par le code / état local |
| --- | --- |
| Dépôt historique `arcenal-agent` | branche `arcenal`, `07eb97715e`, superviseur et trois réparations ; changement contributeur préexistant préservé |
| Paquet historique `arcenal_ynh` | `~ynh69`, travail ADM non publié dans service/scripts/profil ; aucune réécriture de ce travail |
| Paquet courant publié | worktree `arcenal_ynh-hermes-0.22.2`, `f582c31`, `~ynh5`, propre au début du diagnostic |
| Runtime Hermes | UID `arcenal`, données persistantes, NoNewPrivileges, pas de shell root accordé au modèle |
| Autorité centrale existante | UID distinct, coffre Fernet/SQLite par profil, audit HMAC, API admin SSO isolée et socket agent contrôlée par UID |
| Autorisations actuelles | demandes uniques, session et délégation limitée ; pas d'autorisation durable de flux métier versionné |
| Adaptateurs actuels | contacts Dolibarr, dossiers/fichiers Nextcloud, contrôles YunoHost ; pas de projet Dolibarr ni de partage dans le flux |
| Hermes cron | jobs persistants et mode `no_agent` réellement présents ; ne garantissent pas à eux seuls l'idempotence des effets métier |
| Ksaar | prévu dans l'historique, aucun adaptateur/contrat opérationnel trouvé dans les composants inspectés |
| n8n / installation réelle | non inspectés à distance, aucune suppression ni modification autorisée |

L'historique montre la simplification vers Hermes natif, puis les demandes
d'administration et de connecteurs (messages utilisateur 431 et 619). Les
instructions antérieures ne sont pas des ordres pour cette reprise.

**Ce qui manque** : définition/propriétaire/activation d'un automate, observation
durable des transitions, registre d'effets idempotents, reprise par étape et
adaptateurs du flux projet. Les tests/CI de `~ynh5` sont des preuves locales,
pas une preuve que le serveur client ou le flux métier fonctionnent réellement.

## Architecture retenue

Étendre l'autorité centrale et son coffre existants ; aucun nouveau service,
aucun changement du cœur Hermes ni de YunoHost, aucun privilège supplémentaire.
Un worker déterministe dans `arcenal-connectors.service` observe les projets
déclarés par appels API authentifiés, avec état, bail et journal persistants.
Il n'a besoin ni d'une conversation active ni d'un appel LLM pour chaque étape.
Les bibliothèques SQLite, Fernet, HTTP/TLS et XML sont déjà présentes : aucune
nouvelle dépendance applicative n'est prévue.

Une définition est proposée, versionnée, puis explicitement activée par son
propriétaire administrateur SSO. L'autorisation porte sur la version exacte,
les projets, le statut source/destination, les dossiers, le groupe Nextcloud,
les opérations et les révisions de connecteurs. Elle est vérifiée avant chaque
effet. Modifier, désactiver ou révoquer invalide les exécutions futures ; aucune
autorisation globale permanente ni autorisation YunoHost n'est créée.

Le premier déclencheur est **planifié**, en lecture authentifiée des projets
explicitement autorisés. Aucun faux webhook Dolibarr n'est inventé. La première
observation établit une référence, sans déclencher une transition historique.
Un webhook futur devra avoir un contrat d'authentification et d'événement réel.

Le statut « Prospection » doit être mappé explicitement au champ/à la valeur de
l'instance : ne pas supposer qu'il s'agit de `statut=0` ou d'un libellé standard.

## Contrat métier initial

Projet Dolibarr éligible → dossiers Nextcloud déterministes `project-<id>` et
sous-dossiers déclarés → partage **groupe authentifié, lecture seule** → lien
interne `/index.php/f/<id>` → extrachamp Dolibarr déclaré.
Ce lien n'est pas un lien public porteur de secret. Les liens publics à jeton,
les droits globaux et les suppressions ne font pas partie de cette autorisation.

API vérifiée dans le code amont Dolibarr 20 : `GET /projects/{id}` et
`PUT /projects/{id}` ; `array_options` est fusionné champ par champ. La version
de l'instance reste à qualifier. Nextcloud utilise DAV/OCS documentés.
Ksaar obligatoire sans contrat réel bloque l'activation ; Ksaar facultatif doit
être explicitement omis dans la définition et apparaître comme non applicable.

## Limite fondamentale de reprise

Pas de promesse d'exactly-once distribuée entre deux produits indépendants.
MKCOL utilise des chemins stables ; partage et mise à jour sont réconciliés
avant répétition. Un POST de partage ambigu sans résultat retrouvable est
signalé à l'étape exacte et n'est pas retenté aveuglément.

## État initial des vérifications

NON VÉRIFIÉ : statut réel Dolibarr, groupes/droits Nextcloud, contrat Ksaar,
déploiement, SSO, déclenchement et effets sur les instances clientes. n8n reste
en place ; sa suppression n'appartient pas à cette mission.

## Implémentation et modèle d'autorisation

- `automation_contract.py` : registre fermé, lecture et opérations métier bornées.
  Aucune action YunoHost, suppression, gestion de comptes, secret ou commande
  arbitraire ne peut figurer dans le flux.
- `automations.py` : définitions immuables par version, consentements persistants
  liés au propriétaire, empreintes de définition/registre et révisions de connecteurs.
- Le propriétaire confirme création/modification, puis activation de la version
  exacte. Une modification désactive le flux. Un arrêt/révocation change l'époque
  d'autorisation et empêche les étapes suivantes. Une opération déjà sur le réseau
  ne peut pas être annulée rétroactivement.
- Le worker du service central existant se réveille toutes les 5 secondes ; chaque
  définition limite ses observations à son intervalle de 30 à 3600 secondes.
  Aucun cron/script modifiable par le modèle n'est lancé avec un privilège accru.
- L'outil natif `arcenal_automations` permet à Hermes de lire les résultats et
  l'étape en échec. Il ne permet pas au modèle de créer ou activer un automate.
- L'administration est ajoutée à la console existante : formulaires, version,
  propriétaire, activation, arrêt, test en lecture et reprise/réconciliation.

Les anciennes demandes manuelles et leurs validations restent inchangées.
Le partage groupe reste à validation unique dans l'outil manuel, mais appartient
aux actions métier bornées autorisables par un manifeste de flux. Ce n'est pas
une délégation globale de gestion des droits ni une autorisation système.

Chaque observation persistante porte un compteur. La clé d'exécution est dérivée
de l'automate/version/époque/projet/compteur : une observation répétée ne recrée
pas une exécution. Une nouvelle activation établit une nouvelle référence,
sans traiter automatiquement des changements survenus pendant la désactivation.

Les baux d'exécution sont transactionnels et renouvelés par étape (120 secondes).
Après redémarrage, un bail expiré peut être repris ; les effets existants sont
vérifiés avant poursuite. Les intentions de partage et de mise à jour sont
persistées avant l'appel externe. Une réponse perdue est relue côté produit.
Si l'effet n'est pas retrouvable après un appel ambigu, le flux reste
`needs_review` à l'étape précise. Le bouton de reprise ne force aucun POST.

Les dossiers sont déterministes (`base/project-<id>/<sous-dossier>`). Une seconde
transition du même projet retrouve les mêmes dossiers, partage et lien. Les
effets sont référencés par ressource, pas seulement par identifiant d'événement.

Le polling ne garantit pas de voir des transitions intermédiaires entre deux
lectures ni celles produites pendant une panne longue. Un outbox/trigger Dolibarr
réel et authentifié reste nécessaire si la recette exige cette exhaustivité.
Aucun endpoint webhook factice n'est exposé pour masquer cette limite.

## Configuration de recette

Dans la console **Connecteurs**, avec un compte administrateur affecté au profil :

1. Dolibarr : URL API réelle, compte technique dédié, jeton au coffre ; scopes
   `project.read` et `project.update_link` limités aux IDs des projets de recette.
   Déclarer l'extrachamp réellement créé, par exemple `options_nextcloud_url`.
2. Nextcloud : compte technique dédié, mot de passe d'application au coffre ;
   scopes `file.mkdir` et `file.share_group` limités au dossier racine de recette.
   Déclarer le groupe autorisé dans `share_groups`, avec les droits minimaux source.
3. Tester les deux connexions. Aucun identifiant n'est copié dans un prompt,
   une URL ou un fichier de versionnement.
4. Créer la définition dans **Automatismes métier autorisés** : IDs explicites,
   champ réel (`statut`, `opp_status` ou extrachamp), valeur correspondant à
   Prospection, destinations autorisées, dossier racine préexistant, sous-dossiers,
   groupe, extrachamp de retour, fréquence. Le serveur dérive le propriétaire SSO.
5. « Tester sans écrire » affiche l'état lu et le plan. Confirmer la définition
   puis l'activation ; ces confirmations ne valent que pour ce flux/version.
6. Avec `ksaar_required=true`, l'activation est refusée tant qu'un véritable
   adaptateur central n'est pas livré. Avec `false`, l'étape est explicitement
   `not_applicable`. Aucun appel fictif Ksaar et aucune fiche déclarée créée.

Les IDs, noms et valeurs des tests unitaires sont des **fixtures**, pas des
réglages convenant automatiquement au serveur client. Le modèle d'arborescence
et le choix d'un lien interne authentifié doivent être acceptés par le propriétaire.

## Recette fonctionnelle Dolibarr → Nextcloud → Ksaar → Dolibarr

À exécuter uniquement après validation distincte sur des instances de recette :

1. Conserver n8n, sa configuration et ses journaux. Établir la liste des effets
   attendus et le mapping exact des états de projet sur la version Dolibarr réelle.
2. Préparer projet, dossier racine et groupe de test ; créer les comptes
   techniques minimaux. Écarter ces ressources des flux de production existants
   par une procédure validée, sans modifier n8n implicitement.
3. Installer la candidate sur YunoHost jetable. Vérifier UID, coffre, sockets,
   SSO, propriétaire et séparation des privilèges ; confirmer que le worker
   continue sans conversation Hermes ni fournisseur LLM disponible.
4. Créer une définition désactivée. Sans activation, modifier le projet de
   recette : aucun effet. Faire le test en lecture et relever la version exacte.
5. Remettre le projet en Prospection, activer et laisser établir la référence.
   Quitter Prospection vers une destination éligible. Relever l'ID d'exécution.
6. Vérifier l'arborescence exacte, les droits du groupe et l'unicité du partage.
   Contrôler le lien authentifié inscrit dans le seul extrachamp Dolibarr déclaré.
7. Ksaar : si obligatoire, le test doit rester bloqué jusqu'à fourniture de son
   contrat, authentification, modèle de fiche et clé d'idempotence réels. Si
   facultatif et omis, enregistrer ce résultat comme NON APPLICABLE, jamais réussi.
8. Répéter les mêmes observations : aucun doublon. Revenir en Prospection puis
   quitter à nouveau : nouvelle exécution tracée, mêmes ressources sans duplication.
9. Couper réseau/API après MKCOL, après POST partage et après PUT projet ;
   redémarrer l'autorité. Vérifier reprise/réconciliation et l'étape exacte en
   échec. Un effet inconnu impose une vérification, pas un second appel aveugle.
10. Révoquer pendant une lecture : aucune écriture suivante. Tester propriétaire
    retiré, connecteur modifié, scope invalide, autre profil et audit indisponible.
11. Modifier la définition : ancienne autorisation invalide, nouvelle activation
    requise. Tester backup/restore : secrets conservés, automatismes désactivés
    jusqu'à nouvelle validation du propriétaire.
12. Inspecter URL, réponses API, DOM après saisie et journaux avec sentinelles :
    aucun mot de passe, jeton ou réponse brute sensible. Vérifier les IDs de bout
    en bout, les consentements archivés, versions et étapes.
13. Produire le procès-verbal de recette. Ensuite seulement, proposer au
    propriétaire une bascule contrôlée du flux n8n (pas sa suppression). Prévoir
    drainage des événements et fenêtre de bascule pour éviter un trou entre
    dernière observation n8n et première référence ARCenal.

## Rollback

1. Arrêter/révoquer les automatismes dans la console et attendre la fin des
   appels déjà admis ; relever les résultats incertains avant toute répétition.
2. Sauvegarder l'application et le coffre avec les helpers YunoHost ; conserver
   les journaux et le manifeste de version, sans exporter de secret au navigateur.
3. Restaurer la sauvegarde `~ynh5` selon la procédure validée sur instance jetable.
   Les nouvelles données restent récupérables ; aucun retour de schéma destructif
   sur les conversations ou profils Hermes n'est nécessaire.
4. Si les définitions restent dans un coffre récent avec l'ancien code, elles
   sont inertes mais doivent rester désactivées avant toute réinstallation future.
5. Les effets externes ne sont **pas** supprimés automatiquement : identifier
   dossiers, partages et liens via le journal avant une éventuelle compensation,
   avec validation humaine distincte. Réactiver le flux n8n conservé uniquement
   après validation de la bascule et contrôle des doublons/événements en attente.

## Résultats locaux et NON VÉRIFIÉ

Les 16 tests nouveaux exécutent le vrai moteur et les adaptateurs HTTP sur des
serveurs simulant Dolibarr/Nextcloud avec authentification vérifiée : activation,
flux complet sans validation par exécution, absence de doublon, réponses perdues,
redémarrage, arrêt, isolation, audit indisponible et restauration. Ce n'est pas
une recette des produits réels ni une preuve de remplacement de n8n.

NON VÉRIFIÉ : versions et droits clients, statut Prospection réel, réseau/TLS,
SSO YunoHost, continuité du worker en production, persistance après cycle YunoHost,
contrat/fiche Ksaar, transitions rapides manquées par polling, alertes externes
(seuls console, outil de lecture et journal sont livrés), bascule/retour n8n.

**L'autonomie métier de production n'est pas déclarée atteinte.** Le moteur peut
déclencher et exécuter le flux autorisé de bout en bout sur les simulateurs HTTP ;
sa qualification réelle et le composant Ksaar restent à fournir/recetter.

## Fichiers livrés

Tous les chemins suivants sont relatifs au worktree du paquet existant :

- Nouveaux : `connectors/arcenal_connectors/automation_contract.py`,
  `automations.py`, `workflow_adapters.py`, `tests/test_automations.py`,
  `doc/AUTOMATISMES.md`.
- Autorité/contrats : `connectors/arcenal_connectors/server.py`, `contracts.py`,
  `network.py`, `backup.py`, `edge.py`.
- Adaptateurs : `connectors/arcenal_connectors/plugins/dolibarr.py`, `nextcloud.py`.
- Interface : `connectors/ui/index.js`, artefact régénéré
  `connectors/arcenal_connectors/ui/app.js`.
- Plugin natif : `connectors/hermes-plugins/arcenal-connectors/__init__.py`.
- Métadonnées/documentation : `manifest.toml`, `scripts/_common.sh` (version
  uniquement), `connectors/README.md`, `doc/ADMIN.md`, `TEST_REPORT.md`.
- Mémoire compacte : états `.arcenal/` et fiche `AUT-01.md`, sans secret ni journal brut.

Le helper privilégié, les permissions système/SSO et les unités systemd ne sont
pas élargis par ce lot. Les travaux antérieurs du paquet historique et le fichier
contributeur modifié sont préservés.
