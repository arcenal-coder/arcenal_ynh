import React from 'react';
import { createRoot } from 'react-dom/client';

(function () {
  'use strict';
  const h = React.createElement;
  const states = { non_configure: 'Non configuré', a_tester: 'À tester', connecte: 'Connecté', erreur: 'Erreur', desactive: 'Désactivé' };
  const date = value => value ? new Date(value * 1000).toLocaleString('fr-FR') : 'Jamais';
  const button = (label, run, disabled) => h('button', { type: 'button', onClick: () => void run(), disabled }, label);
  const card = (title, children, key) => h('section', { className: 'ac-card', key }, h('h2', null, title), ...children);
  const detail = (label, value) => h(React.Fragment, { key: label }, h('dt', null, label), h('dd', null, value));

  async function api(path, profile, body) {
    const base = new URL('.', document.baseURI).pathname.replace(/\/$/, '');
    const query = profile ? '?profile=' + encodeURIComponent(profile) : '';
    const response = await fetch(base + '/api/arcenal-connectors/v1/' + path + query, {
      method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-ARCenal-Intent': 'manage' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) throw new Error('La demande a été refusée. Vérifiez vos droits, le périmètre et la disponibilité du service.');
    return response.json();
  }

  function Page() {
    const [identity, setIdentity] = React.useState(null);
    const [profile, setProfile] = React.useState('');
    const [state, setState] = React.useState(null);
    const [error, setError] = React.useState('');
    const [busy, setBusy] = React.useState(false);
    const [editing, setEditing] = React.useState(null);
    const [review, setReview] = React.useState(null);
    const [audit, setAudit] = React.useState(null);
    const [automations, setAutomations] = React.useState({ automations: [], runs: [], poll_errors: {} });
    const [automationForm, setAutomationForm] = React.useState(false);
    const [operations, setOperations] = React.useState([]);

    React.useEffect(() => {
      let live = true;
      api('identity').then(value => { if (live) { setIdentity(value); setProfile(value.profiles[0] || ''); } })
        .catch(() => { if (live) setError('Administration réservée aux comptes SSO autorisés.'); });
      return () => { live = false; };
    }, []);
    React.useEffect(() => {
      if (!profile) return;
      let live = true;
      setState(null); setEditing(null); setReview(null); setAudit(null);
      const refresh = () => Promise.all([api('state', profile), api('automations', profile), api('operations', profile)]).then(([value, flows, requested]) => {
        if (live) { setState(value); setAutomations(flows); setOperations(requested.operations); setError(''); } })
        .catch(() => { if (live) setError('Impossible de charger les connecteurs de ce profil.'); });
      void refresh();
      const timer = setInterval(refresh, 5000);
      return () => { live = false; clearInterval(timer); };
    }, [profile]);

    async function run(action) {
      setBusy(true); setError('');
      try { await action(); setState(await api('state', profile)); setAutomations(await api('automations', profile)); setOperations((await api('operations', profile)).operations); }
      catch (_) { setError('Opération refusée ou indisponible. Aucune nouvelle tentative automatique.'); }
      finally { setBusy(false); }
    }
    function confirm(title, summary, action, reject) {
      setReview({ title, summary, action, reject });
    }
    function manage(connector, action, message) {
      confirm(message, { application: connector.label, cible: connector.config?.url, valideur: identity.actor },
        () => api('connectors/' + connector.id + '/' + action, profile, { confirmed: true }));
    }
    if (!identity) return h('section', { className: 'arcenal-connectors' }, h('h1', null, 'Connecteurs'),
      h('p', { role: error ? 'alert' : 'status' }, error || 'Vérification de l’accès administrateur…'));
    return h('div', { className: 'arcenal-connectors' },
      h('header', null, h('h1', null, 'Connecteurs'), h('p', null, 'Administration centrale · secrets à écriture seule · actions tracées'),
        h('label', null, 'Profil client', h('select', { value: profile, onChange: event => setProfile(event.target.value) },
          identity.profiles.map(name => h('option', { key: name, value: name }, name))))),
      error && h('p', { role: 'alert' }, error),
      review && h('section', { className: 'ac-card ac-review', role: 'region', 'aria-label': 'Validation humaine' },
        h('h2', null, review.title), h('pre', null, JSON.stringify(review.summary, null, 2)),
        h('p', null, 'Valideur : ' + identity.actor),
        h('div', { className: 'ac-actions' }, button('Valider', () => run(async () => {
          const current = review; setReview(null); await current.action();
        }), busy), button('Refuser', () => run(async () => {
          const current = review; setReview(null); if (current.reject) await current.reject();
        }), busy))),
      state && h('div', { className: 'ac-grid' }, ...state.connectors.map(connector => card(connector.label, [
        h('p', { key: 'state', role: 'status' }, states[connector.state]),
        h('dl', { key: 'details' }, detail('URL du service', connector.config?.url || '—'),
          detail('Compte technique', connector.config?.account || '—'),
          detail('Périmètre autorisé', connector.config ? JSON.stringify(connector.config.scope) : 'Aucun'),
          detail('Dernier test', connector.last_test ? date(connector.last_test.time) + (connector.last_test.ok ? ' · Réussi' : ' · Échec') : 'Jamais'),
          detail('Dernière utilisation', date(connector.last_used))),
        h('div', { className: 'ac-actions', key: 'actions' },
          button('Configurer ' + connector.label, () => { setEditing(connector); setReview(null); }, busy),
          button('Tester la connexion', () => run(() => api('connectors/' + connector.id + '/test', profile, {})), busy || !connector.config || connector.state === 'desactive'),
          button('Désactiver', () => manage(connector, 'disable', 'Désactiver ce connecteur'), busy || !connector.config),
          button('Révoquer le secret local', () => manage(connector, 'revoke_secret', 'Révoquer le secret local et désactiver le connecteur'), busy || !connector.has_secret),
          button('Journal d’audit', () => run(async () => setAudit({ label: connector.label, ...await api('audit/' + connector.id, profile) })), busy)),
      ], connector.id))),
      editing && state && h(Wizard, { key: profile + editing.id, connector: editing, catalog: state.catalog[editing.id], busy,
        cancel: () => setEditing(null), submit: value => run(async () => {
          const plan = await api('configuration', profile, { connector: editing.id, config: value });
          setEditing(null);
          confirm('Valider la configuration de ' + editing.label,
            { application: editing.label, cible: plan.config.url, donnees: plan.config, secret: 'Jamais affiché', consequence: plan.consequence },
            () => api('configuration/' + plan.id + '/decision', profile, { accept: true }),
            () => api('configuration/' + plan.id + '/decision', profile, { accept: false }));
        }) }),
      state && card('Demandes de validation', state.requests.length ? state.requests.map(request => h(Approval, {
        key: request.id, request, actor: identity.actor, busy,
        decide: (accept, mode, expires) => run(() => api('actions/' + request.id + '/decision', profile, { accept, mode, ...(expires ? { expires } : {}) })),
      })) : [h('p', { key: 'empty' }, 'Aucune action en attente.')]),
      card('Opérations complètes', operations.length ? operations.map(item => h('article', { key: item.id, className: 'ac-card ac-review' },
        h('h2', null, item.state === 'pending' ? 'Est-ce que je peux le faire ?' : item.plan.summary),
        h('p', null, item.plan.summary + ' · ' + item.id + ' · ' + item.state),
        h('h3', null, 'Conséquences importantes'), h('ul', null, ...item.plan.consequences.map((text, i) => h('li', { key: i }, text))),
        h('pre', null, JSON.stringify(item.plan.steps, null, 2)), h('p', null, 'Rollback : ' + (item.plan.rollback || 'Non applicable, conséquences à accepter explicitement.')),
        h('p', null, 'Valideur : ' + (item.validator || identity.actor)),
        item.state === 'pending' && h('div', { className: 'ac-actions' },
          button('Oui, exécuter l’opération complète', () => run(() => api('operations/' + item.id + '/decision', profile, { digest: item.digest, accept: true })), busy),
          button('Non, refuser', () => run(() => api('operations/' + item.id + '/decision', profile, { digest: item.digest, accept: false })), busy)),
        h('pre', null, JSON.stringify(item.results, null, 2)), item.error && h('p', { role: 'alert' }, item.error + ' · étape ' + item.failed_step)))
        : [h('p', { key: 'empty' }, 'Aucune opération préparée.')]),
      card('Automatismes métier autorisés', [
        h('p', { key: 'policy' }, 'Le propriétaire valide la définition puis son activation. Le worker réalise ensuite ce flux sans demander une confirmation à chaque répétition. YunoHost et les actions sensibles restent séparés.'),
        button('Définir un automatisme', () => setAutomationForm(true), busy),
        ...automations.automations.map(item => h('article', { className: 'ac-card', key: item.id },
          h('h2', null, item.id + ' · version ' + item.version + (item.enabled ? ' · Activé' : ' · Désactivé')),
          h('p', null, 'Propriétaire : ' + item.owner), h('pre', null, JSON.stringify(item.spec, null, 2)),
          h('div', { className: 'ac-actions' },
            button('Activer cette version', () => confirm('Autoriser et activer le flux version ' + item.version,
              { proprietaire: item.owner, operations: item.actions, perimetre: item.spec, consequence: 'Les exécutions nominales seront autonomes jusqu’à révocation. Aucun droit système global.' },
              () => api('automations/' + item.id + '/activate', profile, { version: item.version, confirmed: true })), busy || item.enabled || item.owner !== identity.actor),
            button('Arrêter / révoquer', () => confirm('Arrêter cet automatisme', { id: item.id, consequence: 'Aucune étape suivante ne sera autorisée ; les appels déjà partis ne sont pas annulables.' },
              () => api('automations/' + item.id + '/disable', profile, { confirmed: true })), busy || !item.enabled),
            button('Tester sans écrire', () => run(async () => confirm('Résultat du test en lecture seule',
              await api('automations/' + item.id + '/preview', profile, { project: item.spec.projects[0] }), async () => {})), busy),
            button('Préparer une nouvelle version', () => setAutomationForm(item.spec), busy || item.owner !== identity.actor)))),
        ...Object.entries(automations.poll_errors).map(([id, value]) => h('p', { key: 'error-' + id, role: 'alert' }, id + ' · observation : ' + value.code + ' · ' + date(value.time))),
      ]),
      automationForm && state && h(AutomationWizard, { key: profile + (automationForm.id || 'new'), value: automationForm === true ? null : automationForm,
        actor: identity.actor, busy, cancel: () => setAutomationForm(false), submit: spec => confirm('Valider la définition versionnée',
          { proprietaire: identity.actor, definition: spec, consequence: 'Une nouvelle version désactive le flux et exige une activation séparée. Une définition identique reste inchangée.' },
          async () => { await api('automations', profile, { definition: spec, confirmed: true }); setAutomationForm(false); }) }),
      card('Journal des exécutions métier', automations.runs.length ? automations.runs.map(flow => h('article', { className: 'ac-card', key: flow.id },
        h('p', null, flow.id + ' · ' + flow.automation + ' v' + flow.version + ' · projet ' + flow.project),
        h('p', { role: 'status' }, flow.state + ' · étape ' + flow.step + (flow.error ? ' · ' + flow.error : '')),
        h('pre', null, JSON.stringify(flow.steps, null, 2)),
        button('Réconcilier / reprendre', () => confirm('Reprendre sans rejouer aveuglément', { execution: flow.id, etape: flow.step, erreur: flow.error },
          () => api('automations/' + flow.id + '/retry', profile, { confirmed: true })), busy || !['failed', 'needs_review'].includes(flow.state))))
        : [h('p', { key: 'empty' }, 'Aucune exécution métier.')]),
      state && card('Délégations', state.grants.length ? state.grants.map(grant => h('div', { key: grant.id },
        h('p', null, grant.connector + ' · ' + grant.operation + ' · ' + grant.target + ' · ' + grant.mode + ' · expiration ' + date(grant.expires)
          + (grant.revoked ? ' · Révoquée' : ' · Valideur : ' + grant.validator)),
        button('Révoquer la délégation', () => confirm('Révoquer cette délégation',
          { application: grant.connector, action: grant.operation, cible: grant.target, consequence: 'Toute exécution future devra être à nouveau validée.' },
          () => api('grants/' + grant.id + '/revoke', profile, { confirmed: true })), busy || grant.revoked)))
        : [h('p', { key: 'empty' }, 'Aucune délégation.')]),
      audit && card('Journal · ' + audit.label, [h('table', { key: 'table' },
        h('thead', null, h('tr', null, ...['Date', 'Événement', 'Acteur', 'Opération', 'Demande'].map(label => h('th', { key: label }, label)))),
        h('tbody', null, ...audit.events.map((event, index) => h('tr', { key: index },
          ...[date(event.time), event.event, event.actor, event.operation || '—', event.request_id || '—'].map((value, i) => h('td', { key: i }, value))))))]),
      card('Autres applications', [h('p', { key: 'notice' }, 'Disponibles uniquement après livraison et autorisation d’un plugin central ARCenal. Aucun connecteur générique.')]),
      h('p', null, 'La révocation locale supprime l’accès de l’agent. Révoquez aussi le jeton auprès de l’application source. Une délégation révoquée ne peut pas annuler un appel déjà parti.'),
    );
  }

  function Wizard({ connector, catalog, busy, cancel, submit }) {
    const [url, setUrl] = React.useState(connector.config?.url || (connector.id === 'yunohost' ? 'https://' + window.location.hostname : ''));
    const [account, setAccount] = React.useState(connector.config?.account || (connector.id === 'yunohost' ? 'arcenal-connectors' : 'arcenal-'));
    const [entity, setEntity] = React.useState(connector.config?.entity || '');
    const [groups, setGroups] = React.useState((connector.config?.share_groups || []).join(', '));
    const [projectFields, setProjectFields] = React.useState((connector.config?.project_link_fields || []).join(', '));
    const [scope, setScope] = React.useState(Object.fromEntries(Object.keys(catalog).map(name => [name, (connector.config?.scope[name] || []).join(', ')])));
    const secret = React.useRef(null);
    const input = (label, value, change, props = {}) => h('label', null, label,
      h('input', { value, onChange: event => change(event.target.value), ...props }));
    return h('form', { className: 'ac-card', onSubmit: event => {
      event.preventDefault();
      const value = { url, account, scope: Object.fromEntries(Object.entries(scope).filter(([, text]) => text.trim())
        .map(([name, text]) => [name, text.split(',').map(target => target.trim()).filter(Boolean)])) };
      if (entity) value.entity = Number(entity);
      if (connector.id === 'nextcloud') value.share_groups = groups.split(',').map(s => s.trim()).filter(Boolean);
      if (connector.id === 'dolibarr') value.project_link_fields = projectFields.split(',').map(s => s.trim()).filter(Boolean);
      if (secret.current?.value) { value.secret = secret.current.value; secret.current.value = ''; }
      void submit(value);
    } }, h('h2', null, 'Configurer ' + connector.label),
      input(connector.id === 'dolibarr' ? 'URL API HTTPS (terminant par /api/index.php)' : 'URL du service HTTPS', url, setUrl, { type: 'url', required: true }),
      input('Compte technique dédié (préfixe arcenal- ou arcenal_)', account, setAccount, { required: true, readOnly: connector.id === 'yunohost' }),
      connector.id === 'dolibarr' && input('Entité Dolibarr (facultative)', entity, setEntity, { type: 'number', min: 1 }),
      connector.id === 'dolibarr' && input('Extrachamps lien autorisés (ex. options_nextcloud_url)', projectFields, setProjectFields),
      connector.id === 'nextcloud' && input('Groupes de partage en lecture autorisés', groups, setGroups),
      connector.id !== 'yunohost' && h('label', null, connector.id === 'dolibarr' ? 'Nouveau jeton API (jamais relu)' : 'Nouveau mot de passe d’application / jeton dédié (jamais relu)',
        h('input', { ref: secret, type: 'password', autoComplete: 'new-password', spellCheck: false, required: !connector.has_secret })),
      connector.id === 'yunohost' && h('p', null, 'Identité système gérée par le serveur ; aucune identité administrateur personnelle. Le périmètre système peut être plus restrictif que le formulaire.'),
      ...Object.entries(catalog).map(([name, op]) => h('div', { key: name }, input(op.label + ' — cibles séparées par des virgules', scope[name],
        value => setScope(old => ({ ...old, [name]: value }))), h('small', null,
        connector.id === 'dolibarr' ? 'Exemples : company:123, contact:45, project:42 selon l’opération.'
          : connector.id === 'nextcloud' ? 'Sous-arbres DAV sans / initial, par exemple ARCenal/Client-A.' : 'Noms exacts autorisés par la politique système, par exemple arcenal.'))),
      h('div', { className: 'ac-actions' }, h('button', { type: 'submit', disabled: busy }, 'Vérifier et préparer la validation'), button('Annuler', cancel, busy)));
  }

  function AutomationWizard({ value, actor, busy, cancel, submit }) {
    const [form, setForm] = React.useState(value || { id: '', projects: [], status_field: 'opp_status', from_status: '',
      to_statuses: [], base_folder: '', folders: [], share_group: '', link_field: '', interval: 60, ksaar_required: false });
    const change = (key, value) => setForm(old => ({ ...old, [key]: value }));
    const field = (label, key, list = false) => h('label', { key }, label, h('input', { required: !['folders'].includes(key), readOnly: key === 'id' && Boolean(value),
      value: list ? form[key].join(', ') : form[key], onChange: event => change(key, list ? event.target.value.split(',').map(s => s.trim()) : event.target.value) }));
    return h('form', { className: 'ac-card', onSubmit: event => { event.preventDefault();
      submit({ ...form, projects: form.projects.filter(Boolean), to_statuses: form.to_statuses.filter(Boolean), folders: form.folders.filter(Boolean) }); } },
      h('h2', null, 'Définition du flux projet · propriétaire ' + actor),
      h('p', null, 'La première observation sert de référence. Configurez la valeur réelle de Prospection sur votre Dolibarr ; aucun statut numérique n’est supposé.'),
      field('Identifiant de l’automatisme', 'id'), field('Identifiants des projets, séparés par virgules', 'projects', true),
      field('Champ de statut (statut, opp_status ou array_options.options_...)', 'status_field'), field('Valeur source « Prospection »', 'from_status'),
      field('Valeurs de destination éligibles', 'to_statuses', true), field('Dossier racine Nextcloud préexistant', 'base_folder'),
      field('Sous-dossiers à créer dans project-<id>', 'folders', true), field('Groupe Nextcloud autorisé (lecture seule)', 'share_group'),
      field('Extrachamp Dolibarr du lien', 'link_field'),
      h('label', null, 'Intervalle de lecture (30 à 3600 secondes)', h('input', { type: 'number', min: 30, max: 3600, value: form.interval,
        onChange: event => change('interval', Number(event.target.value)) })),
      h('label', null, h('input', { type: 'checkbox', checked: form.ksaar_required, onChange: event => change('ksaar_required', event.target.checked) }),
        'Ksaar obligatoire — activation refusée tant que son connecteur réel n’est pas livré'),
      h('div', { className: 'ac-actions' }, h('button', { type: 'submit', disabled: busy }, 'Préparer la validation de la définition'), button('Annuler', cancel, busy)));
  }

  function Approval({ request, actor, decide, busy }) {
    const [mode, setMode] = React.useState('once');
    const [expiry, setExpiry] = React.useState('');
    return h('article', { className: 'ac-card ac-review', 'aria-label': 'Action à valider' },
      h('h2', null, request.label), h('dl', null, detail('Application', request.connector), detail('Cible', request.target),
        detail('Données concernées', JSON.stringify(request.data)), detail('Conséquence attendue', request.consequence),
        detail('Valideur', actor), detail('Expiration de la demande', date(request.expires))),
      h('label', null, 'Mode de validation', h('select', { value: mode, onChange: event => setMode(event.target.value) },
        h('option', { value: 'once' }, request.always_required ? 'Toujours valider — cette opération uniquement' : 'Une fois'),
        !request.always_required && h('option', { value: 'session' }, 'Session — même opération et cible, au maximum 8 heures'),
        !request.always_required && h('option', { value: 'limited' }, 'Délégation limitée — même action, données et cible'),
        !request.always_required && h('option', { value: 'always' }, 'Toujours valider'))),
      mode === 'limited' && h('label', null, 'Expiration (7 jours maximum)', h('input', { type: 'datetime-local', value: expiry, onChange: event => setExpiry(event.target.value) })),
      h('div', { className: 'ac-actions' }, button('Valider l’action', () => decide(true, mode, mode === 'limited' ? new Date(expiry).getTime() / 1000 : null),
        busy || (mode === 'limited' && !expiry)), button('Refuser l’action', () => decide(false, 'once'), busy)));
  }
  createRoot(document.getElementById('root')).render(h(Page));
})();
