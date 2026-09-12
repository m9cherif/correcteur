'use strict';
// resultat.js — standalone page for a single student's result. Deliberately
// independent of app.js: it must never load or reveal classmates' data, so
// it only ever calls the /eleve/ endpoint scoped to one name server-side.

function el(tag, attrs, children) {
  const e = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === 'text') e.textContent = v; else e.setAttribute(k, v);
  });
  (children || []).forEach((c) => e.appendChild(c));
  return e;
}

function afficherErreur(msg) {
  document.getElementById('box').innerHTML = '';
  document.getElementById('box').appendChild(el('p', { text: '⛔ ' + msg }));
}

function scoreBar(tuiles) {
  return el('div', { class: 'score-bar' }, tuiles.map(([n, l]) =>
    el('div', { class: 'score-tile' }, [el('div', { class: 'n', text: String(n) }), el('div', { class: 'l', text: l })])));
}

function renderClasseEleve(box, rap) {
  box.appendChild(scoreBar([
    [rap.note + ' / 20', 'Note finale'], [rap.qualite, 'Qualité /6'],
    [rap.tests, 'Tests /10'], [rap.structure, 'Structure /4'],
  ]));
  if ((rap.resultats || []).length) {
    box.appendChild(el('h3', { text: 'Tests' }));
    const tbl = el('table', {}, [el('thead', {}, [el('tr', {}, [
      el('th', { text: 'Test' }), el('th', { text: 'Résultat' }), el('th', { text: 'Attendu' }), el('th', { text: 'Obtenu' }),
    ])])]);
    const tbody = el('tbody');
    rap.resultats.forEach((t) => tbody.appendChild(el('tr', {}, [
      el('td', { text: t.nom }),
      el('td', { html: t.reussi ? '<span class="badge ok">OK</span>' : '<span class="badge bad">échec</span>' }),
      el('td', { text: String(t.attendu) }),
      el('td', { text: String(t.obtenu) }),
    ])));
    tbl.appendChild(tbody);
    box.appendChild(tbl);
  }
  if ((rap.remarques || []).length) {
    box.appendChild(el('h3', { text: 'Structure' }));
    rap.remarques.forEach((m) => box.appendChild(el('div', { class: 'meta', text: m })));
  }
  box.appendChild(el('h3', { text: 'Qualité du code' }));
  const problemes = rap.problemes || [];
  if (!problemes.length) box.appendChild(el('p', { class: 'muted', text: '✅ Aucun problème détecté.' }));
  problemes.slice().sort((a, b) => a.ligne - b.ligne).forEach((p) => {
    const div = el('div', { class: 'problem' + (p.gravite !== 'erreur' ? ' avert' : '') });
    div.appendChild(el('div', { class: 'head', text: `${p.icone} Ligne ${p.ligne} [${p.code}] ${p.message}` }));
    div.appendChild(el('div', { class: 'meta', text: `💡 Cause : ${p.explication}\n✅ Correction : ${p.correction}` +
      (p.ligne_corrigee ? `\n➜ Suggestion : ${p.ligne_corrigee.trim()}` : '') }));
    box.appendChild(div);
  });
}

function renderBdEleve(box, rap) {
  box.appendChild(scoreBar([[rap.note + ' / 20', rap.mention || '']]));
  const ecarts = rap.ecarts || [];
  if (!ecarts.length) box.appendChild(el('p', { class: 'muted', text: '✅ Aucun écart détecté.' }));
  ecarts.forEach((ec) => {
    const div = el('div', { class: 'problem' + (ec.gravite !== 'erreur' ? ' avert' : '') });
    div.appendChild(el('div', { class: 'head', text: `${ec.icone} [${ec.code}] ${ec.message}` }));
    div.appendChild(el('div', { class: 'meta', text: `💡 ${ec.cause}\n✅ ${ec.correction}` }));
    box.appendChild(div);
  });
}

(async () => {
  const params = new URLSearchParams(location.search);
  const cat = params.get('cat'), id = params.get('id'), nom = params.get('nom');
  if (!cat || !id || !nom) { afficherErreur('Lien invalide : paramètres manquants.'); return; }
  let data;
  try {
    const r = await fetch(`/api/gallery/${encodeURIComponent(cat)}/${encodeURIComponent(id)}/eleve/${encodeURIComponent(nom)}`);
    data = await r.json();
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  } catch (e) {
    afficherErreur(e.message || 'Ce lien ne correspond à aucun résultat.');
    return;
  }
  const box = document.getElementById('box');
  box.innerHTML = '';
  box.appendChild(el('h2', { text: data.eleve.nom }));
  if (!data.eleve.ok) { box.appendChild(el('p', { text: '⛔ ' + data.eleve.erreur })); return; }
  const rap = data.eleve.rapport || {};
  if (data.categorie === 'bd') renderBdEleve(box, rap); else renderClasseEleve(box, rap);
  box.appendChild(el('p', { class: 'muted', text: 'Résultat généré le ' + new Date(data.uploadedAt).toLocaleString() }));
})();
