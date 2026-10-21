# OP-01 — autorité opérationnelle, une confirmation par opération

## Diagnostic avant modification

- Le prompt natif `yunohost_prompt.py` exigeait une validation par mutation et
  présentait six opérations comme périmètre définitif de l'agent.
- `edge.py` exposait seulement ces énumérations ; le modèle ne pouvait pas
  transformer un accord général en capacité absente du schéma.
- `Store.propose/decide` consommait une autorisation pour chaque action : pas de
  consentement attaché à une opération composée de plusieurs étapes.
- Le helper YunoHost vérifie une liste de commandes et de cibles ; comptes,
  groupes, applications et configurations non déclarés restent techniquement
  absents. Modifier seulement le prompt n'en ferait pas un administrateur complet.
- L'ancien superviseur emploie un booléen `confirmed` écrit par le modèle : ce
  booléen n'est pas une preuve indépendante de l'accord de l'utilisateur.
- Le service principal `arcenal` n'est pas root et ne peut écrire que dans son
  répertoire de données. Le coffre et l'exécuteur sont sous une autre identité.
- Des travaux AUT-01 existent déjà, non publiés : conservés, aucune définition
  ni automatisation concrète créée ou activée dans ce lot.

## Contrat retenu

Demande analysée → plan exact et conséquences → « Est-ce que je peux le faire ? »
→ accord humain enregistré côté application → exécution de toutes les étapes
déclarées → vérifications réelles → bilan factuel et rollback.

L'autorisation couvre l'opération, pas une seule sous-étape. Le plan est figé et
empreinté avant confirmation. Un refus ou une modification ne permet aucune
exécution. Un statut approuvé n'est jamais un statut terminé.

Les opérations sur les intégrations utilisent les adaptateurs centraux existants.
L'administration YunoHost approuvée doit utiliser sa CLI officielle et la syntaxe
réellement installée, sans shell interactif accordé au modèle. Les capacités non
installées doivent être signalées précisément, et leur mise en place proposée
comme opération autorisée. Aucun faux connecteur ni succès supposé.

Les consignes ne désactivent pas globalement les validations Hermes (`yolo/off`),
ne changent pas son cache au milieu d'une conversation et ne transmettent pas
les sessions SSO humaines au processus agent.

## Limite explicite de transport

L'accord de l'utilisateur doit provenir de l'interface authentifiée, pas d'une
affirmation du modèle. La console d'opération porte la question exacte et les
boutons d'accord/refus ; le chat affiche le plan et sa référence. Un simple
« oui » libre n'est pas actuellement relié de façon vérifiable à cette autorité
séparée. Cette limite doit être annoncée, pas contournée par un booléen.

## Changements réalisés

- `authority_policy.py` est le cadrage commun, chargé par l'API native de prompts
  Hermes et figé à la création de session. Il annonce la question exacte, couvre
  les prérequis identifiés dans le même plan, et exige un bilan prouvé.
- `arcenal_operation` prépare le plan, décrit la CLI installée et lit le résultat.
  Il n'a aucune action `approve` : le modèle ne peut pas fournir son propre accord.
- `Operations` conserve le plan chiffré, son empreinte, les révisions des
  connecteurs, le valideur et les preuves par étape. Une décision unique couvre
  toutes les étapes déclarées. Pas de nouvelle question entre deux étapes.
- L'opération attend l'accord explicite sans délai politique arbitraire ; un
  changement de connecteur ou de plan impose en revanche une nouvelle annonce.
- Une étape `kind=automation` réutilise la création/activation existantes avec
  le même consentement. Aucun flux métier concret n'est créé par ce lot.
- Le helper accepte le plan CLI approuvé sous l'identité centrale uniquement.
  Il valide le chemin d'action sur l'`actionsmap.yml` de YunoHost réellement
  installé, pas sur l'ancienne liste de six raccourcis. Les comptes/groupes,
  applications et configurations peuvent ainsi employer leurs commandes officielles.
- Chaque étape CLI comporte une vérification en lecture, avec résultat JSON
  attendu. Un code de sortie de mutation ne suffit pas à annoncer le succès.
- Les paramètres secrets sont générés côté serveur si demandés par le plan,
  conservés dans le coffre et injectés en mémoire dans l'entrée Python officielle
  de YunoHost. Aucun secret ne figure dans l'argv OS d'un enfant ou dans le bilan.
- Après interruption, une opération inachevée devient `unknown`, jamais rejouée.
  Après restauration, les opérations en attente/en cours sont invalidées.
- Le prompt YunoHost et l'identité du superviseur historique emploient ce même
  cadrage. Les règles globales OpenCode et le cœur Hermes restent inchangés.

## Contrat de l'outil

`action=describe, argv=["user","create"]` retourne uniquement les métadonnées
de la commande et de ses arguments : pas de réglages, mot de passe ou exécution.

`action=prepare, plan={summary, consequences[], steps[], rollback}` produit
l'identifiant, l'empreinte et la question. `rollback` peut être nul si non applicable.
Le plan ne contient aucun secret en clair.

Une étape de connecteur utilise `kind=connector`, `connector`, `operation`,
`target`, `data` et `verify={action,expected}`. Une création de fichier/dossier
est vérifiée sur cette même cible ; sa seule acceptation HTTP n'est pas une preuve.

Une étape YunoHost utilise `kind=yunohost_cli`, `argv`,
`verify={argv,expected}` et éventuellement `generate_secrets=["--password"]`
avec la valeur symbolique `@server-secret`. Le vrai mot de passe n'est jamais
transmis au modèle. La CLI de vérification est lue en JSON et son résultat brut
n'est pas exposé : seule la correspondance attendue est conservée.

`action=status, id=<identifiant>` donne le bilan vérifié, l'étape échouée, les
effets partiels/incertains et le rollback annoncé. Ne pas recréer une opération
pour obtenir son statut.

## Contrôles exécutés

Les tests exercent : accord unique pour deux écritures/vérifications, refus,
acteur incorrect, tentative `confirmed=true`, empreinte modifiée, secret généré
inaccessible au modèle, vérification négative bloquant la suite, changement de
connecteur, interruption sans rejeu, question commune historique et actuelle,
CLI déclarée sur l'hôte et création+activation avec un seul consentement.
Les commandes privilégiées et leur syntaxe réelle restent à recetter sur YunoHost.

## Limites réelles restantes

- Changement local non installé : les comptes/privilèges du serveur ne sont pas
  modifiés par la rédaction de ces politiques. L'installation doit être autorisée.
- Le raccordement d'un « oui » libre dans le chat à la preuve SSO de la console
  n'est pas livré. L'accord effectif est celui de la carte authentifiée du plan.
- La CLI exige les paramètres non interactifs complets de l'hôte. Un shell
  interactif général et le client DB interactif ne sont pas un transport RPC.
  Les tâches SQL/fichiers nécessitant un autre exécuteur doivent être identifiées
  comme capacité à mettre en place, pas annoncées comme déjà possibles.
- Les adaptateurs applicatifs ont leurs vrais contrats ; Ksaar n'est pas inventé.
  Les droits métier et portées explicites des comptes de connecteurs restent réels.
- Une opération qui arrête/met à jour son propre exécuteur peut couper son
  transport et sa vérification ; son résultat est alors inconnu et nécessite
  une vérification hors bande. Pas de promesse de maintenance auto-réparatrice.
- Une génération de secret n'implique pas un écran de restitution du secret.
  La saisie d'un secret personnel imposé nécessite un canal serveur dédié.
- Ni la CLI YunoHost via son entrée Python, ni ses journaux/redactions, sudo,
  SSO ou le scénario sur serveur réel ne sont présentés comme testés ici.

Ce cadrage fait agir l'agent avec ses moyens vérifiés ; il ne transforme pas un
prompt en privilège root et ne présente pas un adaptateur manquant comme livré.

## Fichiers de ce recadrage

Chemins relatifs au paquet courant :

- Nouveaux : `connectors/arcenal_connectors/authority_policy.py`,
  `connectors/arcenal_connectors/cli_authority.py`,
  `connectors/arcenal_connectors/operations.py`,
  `tests/test_operation_authority.py`, `doc/AUTORITE_OPERATIONNELLE.md`.
- Autorité : `connectors/arcenal_connectors/server.py`,
  `connectors/arcenal_connectors/backup.py`,
  `connectors/arcenal_connectors/provision.py`.
- Outils/politiques : `connectors/arcenal_connectors/yunohost_prompt.py`,
  `connectors/arcenal_connectors/contracts.py`,
  `connectors/hermes-plugins/arcenal-connectors/__init__.py`.
- Exécution/vérification : `connectors/yunohost-helper`,
  `connectors/arcenal_connectors/plugins/yunohost.py`,
  `connectors/arcenal_connectors/plugins/nextcloud.py`, `scripts/_connectors.sh`.
- Interface : `connectors/ui/index.js`,
  `connectors/arcenal_connectors/ui/app.js` (artefact régénéré).
- Contrôles : `tests/test_connectors_hermes.py`, `tests/test_automations.py`
  (test de consentement création+activation, aucun automate réel).
- Documentation et mémoire : `TEST_REPORT.md`, états `.arcenal/`, lot `OP-01.md`.

Dans le dépôt historique, seul
`arcenal-agent/plugins/arcenal-supervisor/__init__.py` est aligné sur le même cadrage.
Les travaux AUT-01 antérieurs sont conservés ; aucun automatisme de production
ou nouvelle architecture métier n'est ajouté dans ce recadrage.
