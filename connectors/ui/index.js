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
      const refresh = () => api('state', profile).then(value => { if (live) { setState(value); setError(''); } })
        .catch(() => { if (live) setError('Impossible de charger les connecteurs de ce profil.'); });
      void refresh();
      const timer = setInterval(refresh, 5000);
      return () => { live = false; clearInterval(timer); };
    }, [profile]);

    async function run(action) {
      setBusy(true); setError('');
      try { await action(); setState(await api('state', profile)); }
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
    const [scope, setScope] = React.useState(Object.fromEntries(Object.keys(catalog).map(name => [name, (connector.config?.scope[name] || []).join(', ')])));
    const secret = React.useRef(null);
    const input = (label, value, change, props = {}) => h('label', null, label,
      h('input', { value, onChange: event => change(event.target.value), ...props }));
    return h('form', { className: 'ac-card', onSubmit: event => {
      event.preventDefault();
      const value = { url, account, scope: Object.fromEntries(Object.entries(scope).filter(([, text]) => text.trim())
        .map(([name, text]) => [name, text.split(',').map(target => target.trim()).filter(Boolean)])) };
      if (entity) value.entity = Number(entity);
      if (secret.current?.value) { value.secret = secret.current.value; secret.current.value = ''; }
      void submit(value);
    } }, h('h2', null, 'Configurer ' + connector.label),
      input(connector.id === 'dolibarr' ? 'URL API HTTPS (terminant par /api/index.php)' : 'URL du service HTTPS', url, setUrl, { type: 'url', required: true }),
      input('Compte technique dédié (préfixe arcenal- ou arcenal_)', account, setAccount, { required: true, readOnly: connector.id === 'yunohost' }),
      connector.id === 'dolibarr' && input('Entité Dolibarr (facultative)', entity, setEntity, { type: 'number', min: 1 }),
      connector.id !== 'yunohost' && h('label', null, connector.id === 'dolibarr' ? 'Nouveau jeton API (jamais relu)' : 'Nouveau mot de passe d’application / jeton dédié (jamais relu)',
        h('input', { ref: secret, type: 'password', autoComplete: 'new-password', spellCheck: false, required: !connector.has_secret })),
      connector.id === 'yunohost' && h('p', null, 'Identité système gérée par le serveur ; aucune identité administrateur personnelle. Le périmètre système peut être plus restrictif que le formulaire.'),
      ...Object.entries(catalog).map(([name, op]) => h('div', { key: name }, input(op.label + ' — cibles séparées par des virgules', scope[name],
        value => setScope(old => ({ ...old, [name]: value }))), h('small', null,
        connector.id === 'dolibarr' ? 'Exemples : company:123 pour créer, contact:45 pour supprimer.'
          : connector.id === 'nextcloud' ? 'Sous-arbres DAV sans / initial, par exemple ARCenal/Client-A.' : 'Noms exacts autorisés par la politique système, par exemple arcenal.'))),
      h('div', { className: 'ac-actions' }, h('button', { type: 'submit', disabled: busy }, 'Vérifier et préparer la validation'), button('Annuler', cancel, busy)));
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
