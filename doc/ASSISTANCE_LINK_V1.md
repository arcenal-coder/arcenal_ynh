# ARCenal Agent 0.22.2~ynh3 — liaison Matos en lecture seule

Le client autorise le portage depuis l’ancien prototype puis la publication
des deux paquets GitHub en preview. Base : `8324eed`, Hermes stable v0.22.2,
source amont et empreinte inchangées. Aucun ancien plugin de supervision, broker,
socket de contrôle ou service supplémentaire n’est réintroduit.

## Contrat et intégration

L’overlay de distribution `conf/arcenal_assistance` tourne dans le processus
du dashboard natif. `prepare_assistance.py` ajoute un unique montage explicite
dans sa façade, avant démarrage, au même titre que les adaptations de marque.
Il ne modifie aucun outil modèle, prompt, conversation ou permission du dashboard.

- `/assistance/service` : POST JSON borné, clé applicative dédiée ; opérations
  fermées `pair`, `status`, `revoke`, `request`. Toute action métier est refusée.
- `/assistance/` : SSO YunoHost, preuve Nginx privée et identité concordante.
  Les validations exigent aussi le groupe système `admins` et un nonce unique
  de 5 minutes lié à l’utilisateur ; la demande expire après 10 minutes.
- Accord valable 90 jours, révocable dans les deux applications. Matos n’affiche
  l’état actif qu’après contrôle central et présence de son consentement local.
- Référence aléatoire 256 bits, 60 secondes, unique ; contexte conservé entre
  serveurs. À réception, callback HTTPS authentifié vers Matos revérifiant
  activité du compte, rôle et activation du module.
- Contexte : application, utilisateur SSO, `read_only_help`, `module`, identifiant
  `materiel`, `epi` ou `dosimetres`. Aucun dossier, fiche ou document transmis.
- Nginx ne transmet jamais une identité navigateur au service machine. Les
  accès locaux qui forgent simplement `Remote-User` sont refusés sans preuve.
- Les pages d’assistance ne délivrent aucun jeton du dashboard natif et ne
  donnent pas accès au chat administratif. L’accueil n’exécute pas d’inférence.
- Audit de catégories seulement ; accès Nginx et uvicorn d’assistance filtrés.
  États temporaires nettoyés à chaque transaction ; secrets root:app 0640,
  état SQLite dans le dossier privé de données, sauvegardé avec celui-ci.

Le processus et son utilisateur système restent la même frontière que le
dashboard natif et ses outils existants ; ce lien ne crée pas de confinement
contre une exécution de code déjà autorisée sous cet utilisateur.

## Cycle de vie

Le provisionneur root s’exécute depuis les deux paquets, donc dans les deux
ordres d’installation/restauration. Il dérive les URLs des paramètres YunoHost,
préserve la clé applicative et refuse un ancien Agent sans contrat compatible.
Les restaurations sauvegardent le registre et le reconstruisent ; Matos remet
les permissions privées avant de redémarrer. Les données et conversations
Hermes ne sont jamais réinitialisées par cette fonction.

## Installation

Mettre à jour l’Agent vers ce paquet puis Matos vers `0.2.1~ynh1`. Dans Matos,
Paramètres → Agent & MCP → confirmer la lecture seule → Lier ARCenal Agent →
valider dans l’Agent → revenir et Vérifier la liaison.

Le déploiement sur le serveur client reste une action distincte. Sauvegarde
YunoHost complète requise pour revenir au code et aux données précédents.
