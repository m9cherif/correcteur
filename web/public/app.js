'use strict';
// Minimal vanilla-JS SPA driving the correcteur-web REST API. No build step.

const state = {
  lang: 'fr',
  theme: localStorage.getItem('theme') || 'light',
  solutionSource: '', solutionName: 'solution.py',
  testsSource: '', testsName: '',
  baremeName: '',
  classeResultats: [],
};

// ---------------------------------------------------------------------------
function $(sel) { return document.querySelector(sel); }
function $all(sel) { return Array.from(document.querySelectorAll(sel)); }
function el(tag, attrs, children) {
  const e = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === 'text') e.textContent = v; else if (k === 'html') e.innerHTML = v; else e.setAttribute(k, v);
  });
  (children || []).forEach((c) => e.appendChild(c));
  return e;
}
async function api(method, url, body, isForm) {
  const opts = { method };
  if (body !== undefined) {
    if (isForm) { opts.body = body; } else { opts.headers = { 'Content-Type': 'application/json' }; opts.body = JSON.stringify(body); }
  }
  const r = await fetch(url, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

// ---------------------------------------------------------------------------
// Tabs
$all('nav.tabs button').forEach((btn) => {
  btn.addEventListener('click', () => {
    $all('nav.tabs button').forEach((b) => b.classList.remove('active'));
    $all('.tabpane').forEach((p) => p.classList.remove('active'));
    btn.classList.add('active');
    $(`#tab-${btn.dataset.tab}`).classList.add('active');
    if (btn.dataset.tab === 'interp') loadInterpreteurs();
    if (btn.dataset.tab === 'galerie') loadGallery('classe');
    if (btn.dataset.tab === 'bareme') loadBaremes();
  });
});

// Theme + lang
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('theme', t);
  $('#selTheme').value = t; $('#selTheme2').value = t;
}
applyTheme(state.theme);
$('#selTheme').addEventListener('change', (e) => applyTheme(e.target.value));
$('#selTheme2').addEventListener('change', (e) => applyTheme(e.target.value));
$('#selLang').addEventListener('change', (e) => { state.lang = e.target.value; $('#selLang2').value = e.target.value; });
$('#selLang2').addEventListener('change', (e) => { state.lang = e.target.value; $('#selLang').value = e.target.value; });
$('#fontSize').addEventListener('input', (e) => { $('#copieSource').style.fontSize = e.target.value + 'px'; });

// ---------------------------------------------------------------------------
// TP tab
$('#btnDemo').addEventListener('click', async () => {
  try {
    const d = await api('GET', '/api/demo');
    state.solutionSource = d.solution.source || '';
    state.solutionName = 'solution.py';
    state.testsSource = d.tests.source || '';
    state.testsName = 'tests.json';
    $('#tpInfo').innerHTML =
      `<b>Solution:</b> ${d.solution.path}<br><b>Tests:</b> ${d.tests.path}<br>` +
      `<b>Classe (démo):</b> ${d.classe.fichiers.length} fichier(s) — ${d.classe.dir}<br>` +
      `<b>BD (démo):</b> ${d.bd.fichiers.length} fichier(s) — ${d.bd.dir}`;
    if (!$('#copieSource').value) {
      $('#copieSource').value = '# Collez ici le code de l\'élève, ou utilisez "Ouvrir un fichier…"\n';
    }
  } catch (e) { alert(e.message); }
});

$('#btnUploadTp').addEventListener('click', async () => {
  const fd = new FormData();
  const s = $('#fileSolution').files[0], t = $('#fileTests').files[0], b = $('#fileBareme').files[0];
  if (!s && !t && !b) return alert('Choisissez au moins un fichier.');
  if (s) fd.append('solution', s);
  if (t) fd.append('tests', t);
  if (b) fd.append('bareme', b);
  try {
    const r = await api('POST', '/api/tp/upload', fd, true);
    if (s) { state.solutionSource = await s.text(); state.solutionName = s.name; }
    if (t) { state.testsSource = await t.text(); state.testsName = t.name; }
    alert('Envoyé et publié dans la Galerie (id ' + r.entry.id + ').');
  } catch (e) { alert(e.message); }
});

// ---------------------------------------------------------------------------
// Copie tab
$('#btnOpenFile').addEventListener('click', () => $('#fileCopie').click());
$('#fileCopie').addEventListener('change', async (e) => {
  const f = e.target.files[0]; if (!f) return;
  $('#copieSource').value = await f.text();
  $('#copieNom').value = f.name;
});

function renderProblemes(container, problemes, note, mention, bloc) {
  container.innerHTML = '';
  if (note !== undefined) {
    container.appendChild(el('div', { class: 'score-bar' }, [
      el('div', { class: 'score-tile' }, [el('div', { class: 'n', text: note + ' / 20' }), el('div', { class: 'l', text: mention || '' })]),
      el('div', { class: 'score-tile' }, [el('div', { class: 'n', text: problemes.length }), el('div', { class: 'l', text: 'remarques' })]),
    ]));
  }
  if (!problemes.length) {
    container.appendChild(el('p', { class: 'muted', text: '✅ Aucun problème détecté.' }));
  }
  problemes.slice().sort((a, b) => a.ligne - b.ligne).forEach((p) => {
    const div = el('div', { class: 'problem' + (p.gravite !== 'erreur' ? ' avert' : '') });
    div.appendChild(el('div', { class: 'head', text: `${p.icone} Ligne ${p.ligne} [${p.code}] ${p.message}` }));
    div.appendChild(el('div', { class: 'meta', text: `💡 Cause: ${p.explication}\n✅ Correction: ${p.correction}` +
      (p.ligne_corrigee ? `\n➜ Suggestion: ${p.ligne_corrigee.trim()}` : '') }));
    container.appendChild(div);
  });
}

$('#btnAnalyser').addEventListener('click', async () => {
  try {
    const d = await api('POST', '/api/analyser', {
      source: $('#copieSource').value, filename: $('#copieNom').value, lang: state.lang,
      bareme: state.baremeName,
    });
    renderProblemes($('#copieResultat'), d.problemes, d.note, d.mention, d.bloc);
    window._lastAnnote = d.annote;
  } catch (e) { alert(e.message); }
});

$('#btnExportAnnote').addEventListener('click', () => {
  if (!window._lastAnnote) return alert('Cliquez d\'abord sur Analyser.');
  const blob = new Blob([window._lastAnnote], { type: 'text/x-python' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = ($('#copieNom').value || 'copie').replace(/\.py$/, '') + '_annote.py';
  a.click();
});

$('#btnExecuter').addEventListener('click', async () => {
  try {
    const d = await api('POST', '/api/executer', { source: $('#copieSource').value, stdin: $('#copieStdin').value });
    $('#sortieExec').textContent = d.ok
      ? `✅ OK\nSortie:\n${d.sortie || ''}\nValeur: ${d.valeur ?? ''}`
      : `⛔ Erreur: ${d.erreur}\nSortie:\n${d.sortie || ''}`;
  } catch (e) { $('#sortieExec').textContent = '⛔ ' + e.message; }
});

$('#btnPrint').addEventListener('click', () => window.print());

// ---------------------------------------------------------------------------
// Correction tab
function renderCorrection(container, r) {
  container.innerHTML = '';
  container.appendChild(el('div', { class: 'score-bar' }, [
    el('div', { class: 'score-tile' }, [el('div', { class: 'n', text: r.note + ' / 20' }), el('div', { class: 'l', text: 'Note finale' })]),
    el('div', { class: 'score-tile' }, [el('div', { class: 'n', text: r.qualite }), el('div', { class: 'l', text: 'Qualité /6' })]),
    el('div', { class: 'score-tile' }, [el('div', { class: 'n', text: r.tests }), el('div', { class: 'l', text: 'Tests /10' })]),
    el('div', { class: 'score-tile' }, [el('div', { class: 'n', text: r.structure }), el('div', { class: 'l', text: 'Structure /4' })]),
  ]));
  container.appendChild(el('h3', { text: 'Tests' }));
  const tbl = el('table', {}, [el('thead', {}, [el('tr', {}, [el('th', { text: 'Test' }), el('th', { text: 'Résultat' }), el('th', { text: 'Attendu' }), el('th', { text: 'Obtenu' })])])]);
  const tbody = el('tbody');
  (r.resultats || []).forEach((t) => {
    tbody.appendChild(el('tr', {}, [
      el('td', { text: t.nom }),
      el('td', { html: t.reussi ? '<span class="badge ok">OK</span>' : '<span class="badge bad">échec</span>' }),
      el('td', { text: String(t.attendu) }),
      el('td', { text: String(t.obtenu) }),
    ]));
  });
  tbl.appendChild(tbody);
  container.appendChild(tbl);
  if ((r.remarques || []).length) {
    container.appendChild(el('h3', { text: 'Structure' }));
    r.remarques.forEach((m) => container.appendChild(el('div', { class: 'meta', text: m })));
  }
  container.appendChild(el('h3', { text: 'Qualité du code' }));
  renderProblemes(el('div'), r.problemes || [], undefined, undefined, undefined);
  const pcontainer = el('div');
  renderProblemes(pcontainer, r.problemes || []);
  container.appendChild(pcontainer);
}

$('#btnCorriger').addEventListener('click', async () => {
  if (!state.solutionSource) return alert('Chargez d\'abord une solution (onglet TP).');
  try {
    const d = await api('POST', '/api/corriger', {
      eleve_source: $('#copieSource').value,
      solution_source: state.solutionSource,
      tests_source: state.testsSource || undefined,
      lang: state.lang, bareme: state.baremeName,
    });
    window._lastCorrection = d;
    renderCorrection($('#correctionResultat'), d);
  } catch (e) { alert(e.message); }
});

$('#btnVoirSolution').addEventListener('click', () => {
  if (!window._lastCorrection) return alert('Corrigez d\'abord.');
  const w = window.open('', '_blank');
  w.document.write('<pre style="white-space:pre-wrap;font-family:monospace">' +
    (window._lastCorrection.solution || '').replace(/</g, '&lt;') + '</pre>');
});

$('#btnCompat').addEventListener('click', async () => {
  try {
    const d = await api('POST', '/api/compat', { source: $('#copieSource').value, stdin: $('#copieStdin').value });
    const box = $('#compatResultat'); box.style.display = 'block'; box.innerHTML = '<h3>Compatibilité interpréteurs</h3>';
    const tbl = el('table', {}, [el('thead', {}, [el('tr', {}, [el('th', { text: 'Interpréteur' }), el('th', { text: 'Compile' }), el('th', { text: 'Exécute' }), el('th', { text: 'ms' }), el('th', { text: 'Erreur' })])])]);
    const tbody = el('tbody');
    d.resultats.forEach((r) => tbody.appendChild(el('tr', {}, [
      el('td', { text: r.etiquette }),
      el('td', { html: r.compile ? '✅' : '❌' }),
      el('td', { html: r.execute ? '✅' : '❌' }),
      el('td', { text: String(r.ms || 0) }),
      el('td', { text: r.erreur || '' }),
    ])));
    tbl.appendChild(tbody); box.appendChild(tbl);
  } catch (e) { alert(e.message); }
});

// ---------------------------------------------------------------------------
// Barème tab
async function loadBaremes() {
  try {
    const d = await api('GET', '/api/bareme');
    const box = $('#baremeListe'); box.innerHTML = '';
    d.profils.forEach((p) => {
      const b = el('button', { text: p.nom });
      b.style.marginRight = '6px'; b.style.marginBottom = '6px';
      b.addEventListener('click', async () => {
        state.baremeName = p.chemin || '';
        const one = await api('GET', '/api/bareme/one?chemin=' + encodeURIComponent(p.chemin || ''));
        $('#baremeJson').value = JSON.stringify(one.data, null, 2);
        $('#baremeNom').value = (p.nom || 'bareme').replace(/[^a-zA-Z0-9_-]+/g, '_');
      });
      box.appendChild(b);
    });
  } catch (e) { alert(e.message); }
}
$('#btnBaremeCharger').addEventListener('click', loadBaremes);
$('#btnBaremeSauver').addEventListener('click', async () => {
  try {
    const data = JSON.parse($('#baremeJson').value);
    const r = await api('POST', '/api/bareme', { nom: $('#baremeNom').value, data });
    alert('Sauvé: ' + r.chemin);
    loadBaremes();
  } catch (e) { alert(e.message); }
});

// ---------------------------------------------------------------------------
// Classe tab
$('#btnClasseDemo').addEventListener('click', async () => {
  alert('Utilisez "Charger la démo du projet" dans l\'onglet TP pour la solution/tests ; ' +
    'pour les copies de démo, sélectionnez le dossier classe/ du projet manuellement via le sélecteur de fichiers ' +
    '(le navigateur ne peut pas parcourir le disque serveur automatiquement pour des raisons de sécurité).');
});

$('#btnClasseCorriger').addEventListener('click', async () => {
  const files = $('#classeFichiers').files;
  if (!files.length) return alert('Choisissez les copies des élèves.');
  const fd = new FormData();
  Array.from(files).forEach((f) => fd.append('fichiers', f));
  const solF = $('#classeSolution').files[0];
  const testsF = $('#classeTests').files[0];
  if (solF) fd.append('solution', solF);
  else if (state.solutionSource) fd.append('solution', new Blob([state.solutionSource]), state.solutionName || 'solution.py');
  if (testsF) fd.append('tests', testsF);
  else if (state.testsSource) fd.append('tests', new Blob([state.testsSource]), state.testsName || 'tests.json');
  fd.append('lang', state.lang);
  if (state.baremeName) fd.append('bareme', state.baremeName);
  try {
    const d = await api('POST', '/api/classe', fd, true);
    state.classeResultats = d.resultats;
    renderClasse(d);
  } catch (e) { alert(e.message); }
});

function renderClasse(d) {
  $('#classeStats').innerHTML = `<div class="score-bar">
    <div class="score-tile"><div class="n">${d.stats.n}</div><div class="l">copies</div></div>
    <div class="score-tile"><div class="n">${d.stats.moyenne}</div><div class="l">moyenne /20</div></div>
    <div class="score-tile"><div class="n">${d.stats.min}</div><div class="l">min</div></div>
    <div class="score-tile"><div class="n">${d.stats.max}</div><div class="l">max</div></div>
  </div><p class="muted">Publié dans la Galerie — id ${d.id || ''}</p>`;
  const tbody = $('#classeTable tbody'); tbody.innerHTML = '';
  d.resultats.forEach((r, i) => {
    const rap = r.rapport || {};
    const tr = el('tr', {}, [
      el('td', { text: r.nom }),
      el('td', { text: r.ok ? rap.note : '—' }),
      el('td', { text: r.ok ? rap.qualite : '' }),
      el('td', { text: r.ok ? rap.tests : '' }),
      el('td', { text: r.ok ? rap.structure : '' }),
    ]);
    tr.style.cursor = 'pointer';
    tr.addEventListener('click', () => {
      const box = $('#classeDetail'); box.innerHTML = `<h2>${r.nom}</h2>`;
      if (!r.ok) { box.innerHTML += `<p>⛔ ${r.erreur}</p>`; return; }
      renderCorrection(box, rap);
    });
    tbody.appendChild(tr);
  });
}

$all('#classeTable th').forEach((th) => th.addEventListener('click', () => {
  const k = th.dataset.k;
  state.classeResultats.sort((a, b) => {
    const av = k === 'nom' ? a.nom : (a.rapport || {})[k] || 0;
    const bv = k === 'nom' ? b.nom : (b.rapport || {})[k] || 0;
    return av > bv ? -1 : av < bv ? 1 : 0;
  });
  renderClasse({ resultats: state.classeResultats, stats: { n: state.classeResultats.length, moyenne: '', min: '', max: '' } });
}));

$('#btnExportCsv').addEventListener('click', async () => {
  const r = await fetch('/api/export/csv', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resultats: state.classeResultats }) });
  const blob = await r.blob();
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'notes.csv'; a.click();
});

async function exportClasseFile(url, extraFields) {
  const files = $('#classeFichiers').files;
  if (!files.length) return alert('Corrigez d\'abord la classe.');
  const fd = new FormData();
  Array.from(files).forEach((f) => fd.append('fichiers', f));
  const solF = $('#classeSolution').files[0];
  const testsF = $('#classeTests').files[0];
  if (solF) fd.append('solution', solF); else if (state.solutionSource) fd.append('solution', new Blob([state.solutionSource]), 'solution.py');
  if (testsF) fd.append('tests', testsF); else if (state.testsSource) fd.append('tests', new Blob([state.testsSource]), 'tests.json');
  fd.append('lang', state.lang);
  Object.entries(extraFields || {}).forEach(([k, v]) => fd.append(k, v));
  const r = await fetch(url, { method: 'POST', body: fd });
  if (!r.ok) { const j = await r.json().catch(() => ({})); return alert(j.error || 'Erreur export'); }
  const blob = await r.blob();
  const cd = r.headers.get('Content-Disposition') || '';
  const m = /filename="([^"]+)"/.exec(cd);
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = m ? m[1] : 'export'; a.click();
}
$('#btnExportExcel').addEventListener('click', () => exportClasseFile('/api/export/excel'));
$('#btnExportAccess').addEventListener('click', () => exportClasseFile('/api/export/access', { mode: 'sqlite' }));

// ---------------------------------------------------------------------------
// BD tab
$('#btnBdDemo').addEventListener('click', () => {
  alert('Sélectionnez manuellement bd/eleve1_sami.db, bd/eleve2_rania.db… comme "base(s) élève" ' +
    'et bd/solution.db comme "base solution" via les sélecteurs de fichiers ci-dessus.');
});
$('#btnBdComparer').addEventListener('click', async () => {
  const files = $('#bdFichiers').files, sol = $('#bdSolution').files[0];
  if (!files.length || !sol) return alert('Choisissez base(s) élève et base solution.');
  const fd = new FormData();
  Array.from(files).forEach((f) => fd.append('fichiers', f));
  fd.append('solution', sol); fd.append('lang', state.lang);
  try {
    const d = await api('POST', '/api/bd/comparer', fd, true);
    renderBd(d);
  } catch (e) { alert(e.message); }
});
function renderBd(d) {
  $('#bdStats').innerHTML = `<div class="score-bar">
    <div class="score-tile"><div class="n">${d.stats.n}</div><div class="l">bases</div></div>
    <div class="score-tile"><div class="n">${d.stats.moyenne}</div><div class="l">moyenne /20</div></div>
  </div><p class="muted">Publié dans la Galerie — id ${d.id || ''}</p>`;
  const box = $('#bdDetail'); box.innerHTML = '';
  d.resultats.forEach((r) => {
    const card = el('div', { class: 'card' });
    card.appendChild(el('h3', { text: r.nom + (r.ok ? ` — ${r.rapport.note} / 20 (${r.rapport.mention})` : ' — erreur') }));
    if (!r.ok) { card.appendChild(el('p', { text: '⛔ ' + r.erreur })); box.appendChild(card); return; }
    (r.rapport.ecarts || []).forEach((ec) => {
      const div = el('div', { class: 'problem' + (ec.gravite !== 'erreur' ? ' avert' : '') });
      div.appendChild(el('div', { class: 'head', text: `${ec.icone} [${ec.code}] ${ec.message}` }));
      div.appendChild(el('div', { class: 'meta', text: `💡 ${ec.cause}\n✅ ${ec.correction}` }));
      card.appendChild(div);
    });
    box.appendChild(card);
  });
}
$('#btnBdDiagnostic').addEventListener('click', async () => {
  const d = await api('GET', '/api/bd/diagnostic');
  const box = $('#bdDiag'); box.style.display = 'block';
  box.innerHTML = '<h3>Diagnostic pilotes</h3><pre class="diff">' + d.diagnostic + '</pre>';
});
$('#btnBdExportExcel').addEventListener('click', async () => {
  const files = $('#bdFichiers').files, sol = $('#bdSolution').files[0];
  if (!files.length || !sol) return alert('Choisissez base(s) élève et base solution.');
  const fd = new FormData();
  Array.from(files).forEach((f) => fd.append('fichiers', f));
  fd.append('solution', sol);
  const r = await fetch('/api/bd/export/excel', { method: 'POST', body: fd });
  if (!r.ok) { const j = await r.json().catch(() => ({})); return alert(j.error || 'Erreur export'); }
  const blob = await r.blob();
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'rapport_bd.xlsx'; a.click();
});

// ---------------------------------------------------------------------------
// Interpréteurs tab
async function loadInterpreteurs() {
  try {
    const d = await api('GET', '/api/interpreteurs');
    const tbody = $('#interpTable tbody'); tbody.innerHTML = '';
    d.interpretes.forEach((i) => tbody.appendChild(el('tr', {}, [
      el('td', { text: i.etiquette }), el('td', { text: i.chemin }),
      el('td', { html: i.pip ? '✅' : '—' }), el('td', { html: i.pyqt5 ? '✅' : '—' }),
    ])));
  } catch (e) { alert(e.message); }
}
$('#btnScanInterp').addEventListener('click', loadInterpreteurs);

// ---------------------------------------------------------------------------
// Galerie tab (public, no auth)
let galCat = 'classe';
$all('.galBtn').forEach((b) => b.addEventListener('click', () => {
  $all('.galBtn').forEach((x) => x.classList.remove('active'));
  b.classList.add('active'); galCat = b.dataset.gcat; loadGallery(galCat);
}));
async function loadGallery(cat) {
  try {
    const d = await api('GET', `/api/gallery/${cat}?limit=50`);
    const box = $('#galerieListe'); box.innerHTML = `<h3>${cat} — ${d.total} envoi(s)</h3>`;
    $('#galerieDetail').innerHTML = '';
    d.items.forEach((item) => {
      const div = el('div', { class: 'gallery-item' });
      div.appendChild(el('div', {}, [el('b', { text: new Date(item.uploadedAt).toLocaleString() })]));
      div.appendChild(el('div', { class: 'fname', text: item.files.map((f) => f.nom).join(', ') }));
      const btn = el('button', { text: 'Voir le résultat' });
      btn.addEventListener('click', () => showGalleryDetail(cat, item.id));
      div.appendChild(btn);
      box.appendChild(div);
    });
  } catch (e) { alert(e.message); }
}
async function showGalleryDetail(cat, id) {
  try {
    const entry = await api('GET', `/api/gallery/${cat}/${id}`);
    const box = $('#galerieDetail');
    box.innerHTML = `<h2>${cat} — ${new Date(entry.uploadedAt).toLocaleString()}</h2>`;
    box.innerHTML += '<p class="muted">Fichiers: ' + entry.files.map((f) => {
      const rel = f.savedAs.startsWith(id + '/') ? f.savedAs.slice(id.length + 1) : f.savedAs;
      return `<a href="/api/gallery/${cat}/${id}/file/${encodeURIComponent(rel)}">${f.nom}</a>`;
    }).join(', ') + '</p>';
    if (cat === 'classe' && entry.result) {
      const st = entry.result.stats || {};
      box.innerHTML += `<div class="score-bar">
        <div class="score-tile"><div class="n">${st.n ?? ''}</div><div class="l">copies</div></div>
        <div class="score-tile"><div class="n">${st.moyenne ?? ''}</div><div class="l">moyenne /20</div></div>
        <div class="score-tile"><div class="n">${st.min ?? ''}</div><div class="l">min</div></div>
        <div class="score-tile"><div class="n">${st.max ?? ''}</div><div class="l">max</div></div></div>`;
      const tbl = el('table', {}, [el('thead', {}, [el('tr', {}, [el('th', { text: 'Fichier' }), el('th', { text: 'Note /20' }), el('th', { text: 'Qualité' }), el('th', { text: 'Tests' }), el('th', { text: 'Structure' })])])]);
      const tbody = el('tbody');
      (entry.result.resultats || []).forEach((r) => {
        const rap = r.rapport || {};
        tbody.appendChild(el('tr', {}, [el('td', { text: r.nom }), el('td', { text: r.ok ? rap.note : '—' }),
          el('td', { text: r.ok ? rap.qualite : '' }), el('td', { text: r.ok ? rap.tests : '' }), el('td', { text: r.ok ? rap.structure : '' })]));
      });
      tbl.appendChild(tbody); box.appendChild(tbl);
    } else if (cat === 'bd' && entry.result) {
      const st = entry.result.stats || {};
      box.innerHTML += `<div class="score-bar">
        <div class="score-tile"><div class="n">${st.n ?? ''}</div><div class="l">bases</div></div>
        <div class="score-tile"><div class="n">${st.moyenne ?? ''}</div><div class="l">moyenne /20</div></div></div>`;
      (entry.result.resultats || []).forEach((r) => {
        const card = el('div', { class: 'card' });
        card.appendChild(el('h3', { text: r.nom + (r.ok ? ` — ${r.rapport.note} / 20 (${r.rapport.mention})` : ' — erreur') }));
        if (!r.ok) { card.appendChild(el('p', { text: '⛔ ' + r.erreur })); box.appendChild(card); return; }
        (r.rapport.ecarts || []).forEach((ec) => {
          const div = el('div', { class: 'problem' + (ec.gravite !== 'erreur' ? ' avert' : '') });
          div.appendChild(el('div', { class: 'head', text: `${ec.icone} [${ec.code}] ${ec.message}` }));
          div.appendChild(el('div', { class: 'meta', text: `💡 ${ec.cause}\n✅ ${ec.correction}` }));
          card.appendChild(div);
        });
        box.appendChild(card);
      });
    } else {
      box.appendChild(el('pre', { class: 'diff', text: JSON.stringify(entry.result || entry.meta, null, 2) }));
    }
  } catch (e) { alert(e.message); }
}

// Initial load
loadGallery('classe');
