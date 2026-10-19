# Connecteurs centraux — candidate `0.22.2~ynh5`

Statut : **candidate locale, non publiée, non déployée**. Base Hermes v0.22.2
et paquet précédent `8324eed`. Qualification YunoHost réelle encore requise.

Administration native YunoHost, initialisation et exemples dans le chat :
[YUNOHOST_NATIF.md](YUNOHOST_NATIF.md).

## 1. Parcours administrateur

1. Ouvrir ARCenal Agent avec le SSO YunoHost administrateur.
2. Choisir **Connecteurs** dans le menu latéral natif.
3. Ouvrir la **console sécurisée des connecteurs** dans le nouvel onglet.
4. Choisir le profil client explicitement affecté au compte SSO.
5. Configurer le compte technique, l'URL HTTPS et les seules cibles autorisées.
6. Vérifier la carte de configuration : application, cible, périmètre,
   conséquence et valideur ; **Valider** ou **Refuser**.
7. **Tester la connexion**. Seul un connecteur testé avec succès peut exécuter
   une opération. Un changement de configuration impose un nouveau test.

Si le profil Hermes possède une sélection explicite de jeux d'outils, autoriser
les jeux `arcenal_dolibarr`, `arcenal_nextcloud` et `arcenal_yunohost` via ses
réglages natifs. Les plugins ne remplacent pas cette sélection personnalisée.
Ouvrir une nouvelle session pour prendre en compte une activation d'outils ;
aucun préfixe de conversation ni jeu d'outils n'est modifié en cours de tour.

La console centrale a une **origine HTTPS distincte**, sur le port secondaire
déclaré au paquet (9443 par défaut, persisté par YunoHost). Elle utilise le
certificat du domaine et SSOwat, mais ne sert aucun code Hermes. Elle refuse
les iframes, les appels d'approbation depuis l'origine Hermes, et l'ouverture
avec un navigateur non authentifié/compte non affecté.

Ce choix est nécessaire : les plugins et outils d'Hermes peuvent écrire dans
son environnement utilisateur. Une approbation sur la même origine web que
ce JavaScript ne constituerait pas une barrière fiable contre l'agent.
Le menu reste une extension native du dashboard ; le chat/TUI n'est pas réécrit.

Si le SSO a expiré, se reconnecter au portail/dashboard puis rouvrir la console.
Le retour automatique du portail vers le port secondaire reste à qualifier.
Ne pas rendre cette URL publique ni désactiver la vérification TLS.

## 2. Architecture livrée

- `arcenal-dolibarr`, `arcenal-nextcloud`, `arcenal-yunohost` : plugins centraux
  à opérations fermées, plus leurs clients plugins natifs Hermes.
- `arcenal-connectors` : menu natif sans API d'approbation dans Hermes.
- `arcenal-connectors.service` : autorité indépendante, sous l'utilisateur
  système technique `arcenal-connectors`, sans shell de connexion.
- Code et console précompilée dans `/usr/local/lib/arcenal-connectors`, propriété
  de root, sans droit d'écriture pour Hermes ni pour le service central. Le
  service utilise le Python système isolé (`-I -B`) et le paquet Debian
  `python3-cryptography` ; il ne charge ni code ni dépendance de l'environnement
  construit par l'UID Hermes. Le réseau HTTPS utilise la bibliothèque standard.
- Socket `admin.sock` réservée au proxy `www-data`, socket `agent.sock` réservée
  aux clients autorisés. Le serveur contrôle **l'UID réel du pair** et refuse
  toute affectation ambiguë ; aucun jeton n'est à exposer ou à distribuer.
- SSOwat supprime les en-têtes `YNH_*` fournis par le client puis injecte
  `YNH_USER`. Nginx remplace `X-ARCenal-User` à partir de cette valeur et ne
  transmet ni cookie SSO ni en-tête Authorization à l'autorité centrale.
- Le proxy du dashboard retire également cookies SSO et authentification SSO
  avant d'atteindre Hermes. Le jeton de session natif Hermes et les tickets WS
  restent ses mécanismes propres. Un runtime agent ne doit pas recevoir la
  session humaine permettant de valider sur l'origine centrale.
- Politique système : `/etc/arcenal-connectors/policy.json`, root, groupe du
  service central, `0640`. L'agent ne peut pas l'écrire ni la lire.
- Coffre : `/var/lib/arcenal-connectors/profiles/<profil>/`, `0700`, clés et
  bases `0600`. Une clé Fernet distincte par profil ; SQLite chiffré pour les
  secrets, configurations, demandes, données de validation et délégations.
- Audit authentifié HMAC, transactionnel ; aucune donnée métier ni secret dans
  les événements. Identité validée, opération, ID opaque, empreinte de cible,
  demande/validation/refus/réservation/résultat sont corrélables.

Le runtime Hermes principal reste non root et conserve `NoNewPrivileges=true`.
Seul le compte du service central peut invoquer le helper YunoHost par sudo.
Le helper accepte du JSON sur stdin et **aucun argument de commande** ; il
revalide opération, profil et cible contre la politique root. Il n'exécute
jamais un shell. Il ne peut ni administrer les comptes ni modifier les droits,
secrets ou configurations système. Aucun ancien broker ARC n'est réactivé.

Il n'y a aucun MCP local, webhook ou automatisation par navigateur.
La politique de validation de ce lot protège ces plugins et leurs API centrales ;
elle ne remplace pas les permissions propres aux outils généraux d'Hermes.

## 3. Comptes techniques et périmètres

Les comptes humains/personnels ne doivent pas être utilisés. Les identités
Dolibarr et Nextcloud doivent commencer par `arcenal-` ou `arcenal_` ; le test
authentifié vérifie l'identité réellement renvoyée par le service. Ce préfixe
ne remplace pas l'administration des droits dans l'application source.

### Dolibarr

- Créer un compte technique et lui donner uniquement les droits contacts utiles.
- URL API HTTPS complète, par exemple `https://erp.example.test/api/index.php`.
- Entité entière facultative ; jeton API transmis uniquement par `DOLAPIKEY`.
- `contact.create` : cibles `company:123`, données `lastname`, `firstname` facultatif.
- `contact.delete` : cibles `contact:45`, données vides, toujours une validation unique.
- Le test utilise `/users/info` et vérifie le login. Les versions Dolibarr et
  permissions réelles doivent être qualifiées sur les instances clientes.

### Nextcloud

- Créer un compte technique, mot de passe d'application dédié et dossiers utiles.
- URL HTTPS de l'instance, avec son sous-chemin éventuel.
- `file.mkdir`, `file.write`, `file.delete` : sous-arbres DAV sans `/` initial,
  par exemple `ARCenal/Client-A`. La limite respecte les frontières de dossiers.
- `file.write` reçoit `content` (texte UTF-8, 8 Kio maximum).
- `file.delete` exige toujours une validation unique.
- Le test utilise OCS et vérifie l'ID utilisateur ; les actions utilisent le
  WebDAV de ce compte. Pas de gestion des groupes ni de partage dans ce contrat v1.

### YunoHost

- Cette version gère **le serveur hébergeant l'autorité**, avec l'identité OS
  limitée `arcenal-connectors`, sans mot de passe LDAP administrateur.
- L'URL est celle du domaine du serveur, pas celle d'un serveur distant arbitraire.
- `server.inventory`, `service.status/start/stop/restart`, `backup.create`.
- Le profil serveur nouvellement enrôlé est initialisé automatiquement depuis
  un inventaire minimal ; il n'a pas de secret à saisir pour YunoHost. Son premier
  usage déclenche un test en lecture. Les mutations sur les cibles enrôlées
  restent toujours soumises à une validation humaine unique.
- Les configurations, restrictions et désactivations existantes sont conservées.
  La saisie dans le formulaire ne peut pas élargir le plafond système root.
- Un opérateur root habilité peut autoriser les services/applications précis,
  **profil par profil**, dans `yunohost_targets`. Par exemple `nginx` pour un
  redémarrage, ou `nextcloud` pour sa sauvegarde. Chaque mutation attend encore
  sa validation humaine unique dans la console.
- L'auto-redémarrage et l'auto-sauvegarde d'ARCenal par son propre connecteur sont
  refusés : cela interromprait l'autorité pendant l'exécution. Utiliser YunoHost
  directement pour ces opérations.
- L'arrêt des services indispensables à l'accès au plan de contrôle est refusé,
  même si une politique a été mal configurée. Le modèle consulte le résultat
  d'une demande par `action.status` ; il ne la réexécute pas pour connaître son état.

Les droits Dolibarr, Nextcloud et YunoHost restent souverains : une validation
ARCenal n'accorde aucun droit supplémentaire au compte technique.

## 4. Validation humaine et révocation

- **Une fois** : réservation consommée et auditée avant l'appel ; aucun rejeu,
  même si le réseau échoue. Une erreur n'est jamais retentée automatiquement.
- **Session** : même profil, révision, opération et cible, jusqu'à la clôture ou
  réinitialisation native, avec une borne maximale de 8 heures. Le client crée
  un nonce de session distinct des arguments du modèle ; la reprise d'une
  conversation clôturée ne récupère pas son ancienne autorisation.
- **Délégation limitée** : même opération, cible et données exactes, expiration
  explicite au plus à 7 jours. Contrôle serveur à chaque nouvelle réservation.
- **Toujours valider** : impose des validations uniques futures ; obligatoire
  pour les suppressions et toutes les mutations YunoHost. Une délégation ne
  peut jamais contourner cette règle. Les opérations sensibles non déclarées
  (droits, comptes administrateurs, secrets et configuration distante) sont refusées.

Refus, expiration, changement de révision, connecteur désactivé, session clôturée,
audit absent/altéré/indisponible : aucune nouvelle exécution. Une révocation est
prise en compte sans attendre le réseau d'une action déjà acceptée. Elle ne peut
pas annuler une action déjà réservée/en vol.

**Révoquer le secret local** désactive le connecteur, retire son secret actif et
invalide ses autorisations. Révoquer également le jeton dans Dolibarr/Nextcloud
pour l'invalider chez le fournisseur. Aucune capacité de révocation distante
non documentée n'est simulée.

## 5. Cloisonnement client par client

Un profil logique Hermes partageant l'UID d'un autre client n'est pas une
frontière de sécurité : ses outils partagent les permissions de l'autre.
Le provisionnement central **refuse deux clients sous le même UID**.

Pour chaque nouveau client, un opérateur habilité doit :

1. Préparer une instance/runtime Hermes indépendant sous un utilisateur système
   distinct, non root, avec un home `0700` et son propre cycle de mise à jour.
2. Installer les quatre plugins de distribution, et rendre le module client
   `arcenal_connectors.edge` accessible à ce runtime, sans remplacer ses modules Hermes.
3. Donner à ce seul utilisateur le droit d'ouvrir la socket agent (groupe `arcenal`).
4. Lancer l'outil de provisionnement root sur le home de cette instance :

```sh
/usr/bin/python3 -I -B /usr/local/lib/arcenal-connectors/run.py provision \
  --hermes-home /var/lib/arcenal-clients/client-a/hermes \
  --profile client_a --users-json '["validateur-a"]' \
  --origin https://agent.example.test:9443 \
  --plugins-source /usr/local/lib/arcenal-connectors/hermes-plugins
```

L'outil utilise le Python système et le code central privé appartenant à root.
Il ne crée ni client Unix, ni domaine,
ni instance Hermes : il vérifie leur existence et leur UID. Arrêter ce runtime
avant provisionnement pour exclure une modification concurrente de ses plugins.
Configurer ensuite `plugins.enabled` dans **cette** instance et la redémarrer.

Les identités SSO sont explicitement affectées aux profils dans `principals`.
Les autres clients ne sont jamais ajoutés implicitement. Les révocations et
choix de plugins déjà enregistrés sont conservés lors d'un upgrade.
Avant de retirer un compte système client, révoquer son affectation UID et ses
affectations dans la politique ; ne pas réutiliser son UID pour un autre client.

Les adresses privées sont refusées par défaut. Les CIDR nécessaires aux services
internes doivent être explicitement autorisés dans `allowed_private_networks`
par l'opérateur système. Aucun proxy d'environnement, redirection HTTP ou
contournement TLS n'est utilisé ; DNS validé puis IP épinglée pour l'appel.

## 6. Conservation, migration et rollback

- Aucune base de conversations, profil, mémoire ou compétence Hermes n'est migrée.
- `.env` garde ses octets existants ; le provisionnement central ne le lit pas
  et n'y ajoute aucun identifiant ni secret.
- Les secrets métier restent dans le coffre séparé, pas dans `.env`, config.yaml,
  export du dashboard ou conversations. Les champs password ne sont pas préremplis ;
  le navigateur transmet la saisie une fois par HTTPS et ne reçoit jamais sa valeur
  après enregistrement. Aucun localStorage/sessionStorage n'est utilisé.
- Un changement d'URL nécessite un nouveau secret : l'ancien n'est pas réutilisé
  automatiquement vers une nouvelle destination.
- Schéma du coffre v1 additif et séparé ; schéma futur inconnu refusé.
- Le backup YunoHost arrête l'autorité et embarque un instantané privé `0600`
  appartenant à root, incluant coffre et clés. Cette **sauvegarde administrative**
  contient des secrets ; elle ne doit pas être diffusée comme export utilisateur.
- La restauration valide l'archive avant remplacement, refuse liens/traversées,
  garde une copie de l'état remplacé, invalide toutes les délégations et demandes
  anciennes, et impose un nouveau test de connexion.
- Les UID et identités agent archivés sont invalidés, pour éviter leur réemploi
  sur un autre hôte. Le profil par défaut est réaffecté par le paquet ; les clients
  supplémentaires doivent être reprovisionnés explicitement.

Pour revenir à `~ynh2` sur une instance de recette : sauvegarder l'état courant,
arrêter/désactiver `arcenal-connectors.service`, retirer son snippet Nginx et son
sudoers avec validation de la configuration Nginx, puis restaurer le backup
YunoHost `~ynh2`. Conserver `/var/lib/arcenal-connectors` et sa politique en privé
pour récupération : l'ancien paquet ne sait pas les interpréter. La simple
restauration d'une vieille archive ne prouve pas ce rollback : le scénario doit
être exécuté sur instance jetable avant toute livraison serveur.

## 7. Recette complète à exécuter sur YunoHost jetable

1. Installer `~ynh2`, créer conversations, compétences, profils, secrets et un
   choix de thème ; prendre une sauvegarde et relever des empreintes privées.
2. Mettre à jour vers la candidate locale `~ynh3`, vérifier la conservation de
   ces données et l'absence de mutation du cœur Hermes.
3. Vérifier services, UID/groupes, permissions, sockets, certificat et pare-feu.
   Tester SSO administrateur, anonyme, non-admin et compte non affecté à un profil.
4. Depuis Hermes, tenter une approbation directe vers l'origine centrale : refus
   Origin/CORS. Vérifier refus iframe et absence d'API admin sur la socket agent.
   Vérifier aussi l'absence de Cookie/Authorization SSO en amont d'Hermes et le
   fonctionnement des jetons REST/WS natifs, avec des sentinelles et sans logs de secrets.
5. Configurer/tester chaque application de recette avec ses comptes techniques,
   puis un mauvais jeton. Vérifier états, identité, dernier test et journal filtré.
6. Faire proposer les opérations autorisées. Sans validation, aucun effet externe.
   Tester valider/refuser, rejeu, expiration, session/reset/reprise et délégation.
7. Révoquer une délégation pendant un appel réseau lent : les nouvelles actions
   sont bloquées immédiatement ; l'appel déjà accepté est identifié dans l'audit.
8. Tester suppression et YunoHost sensibles : session/limité refusés, une seule
   exécution après validation unique. Tester une cible hors périmètre et une
   opération non déclarée : aucun appel externe.
9. Provisionner deux UID/clients et tenter un accès croisé aux demandes/secrets :
   refus. Les headers ne peuvent pas remplacer l'UID vérifié par le noyau.
   Vérifier refus de deux clients sur un UID.
10. Inspecter réponses API, URL, DOM après enregistrement, logs et export Hermes
    avec des secrets sentinelles : aucune valeur. Un POST de saisie HTTPS initial
    contient nécessairement la valeur entrée par l'administrateur.
11. Faire backup/restore, vérifier clés/secrets, nouvelles identités et permissions
    invalidées, puis tester rollback `~ynh2` et remise en place de la candidate.
12. Consigner les preuves et erreurs réelles avant autorisation de publication.

Les tests locaux couvrent les refus et invariants avec services externes simulés,
le chargement natif des plugins et Chrome. Ils ne remplacent pas cette recette.

## 8. Contrôles développeur et artefact livré

La console est compilée **avant livraison**, depuis `connectors/ui/` et les
dépendances verrouillées du checkout Hermes de référence. Le serveur cible
n'exécute pas ce build ; il reçoit l'artefact du paquet validé.

```sh
node connectors/build-ui.mjs /chemin/vers/source-hermes-verrouillee \
  connectors/arcenal_connectors/ui
node --check connectors/arcenal_connectors/ui/app.js
node --test tests/test_connectors_ui.mjs
```

Les licences React, React DOM et Scheduler sont livrées à côté du bundle. Les
tests du paquet s'exécutent avec `python -m unittest discover -s tests -v` dans
le runtime de contrôle et `PYTHONPATH` pointant vers la source Hermes adaptée.
La suite amont Hermes, si nécessaire, reste exécutée par `scripts/run_tests.sh`.
Ne pas publier une modification de la source UI sans régénérer son artefact et
rejouer le test navigateur. Rapports : `TEST_REPORT.md`.
