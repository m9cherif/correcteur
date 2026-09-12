// server.js — REST API for the correcteur web app.
// Spawns the Python engine (engine/cli.py) which imports the existing pure
// grading modules (analyseur.py, correcteur.py, bareme.py, langues.py,
// interpreteurs.py, correcteur_access.py, rapport_excel.py, rapport_access.py)
// directly — no grading logic is duplicated here.
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const express = require('express');
const cors = require('cors');
const multer = require('multer');

const { callEngine } = require('./engine');
const store = require('./store');

const PORT = process.env.PORT || 3000;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.dirname(__dirname);

const app = express();
app.use(cors());
app.use(express.json({ limit: '15mb' }));
app.use(express.static(path.join(__dirname, 'public')));

const TMP_DIR = path.join(__dirname, 'tmp');
fs.mkdirSync(TMP_DIR, { recursive: true });
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 20 * 1024 * 1024, files: 200 },
});

function sendErr(res, e, code = 400) {
  // eslint-disable-next-line no-console
  console.error(e);
  res.status(code).json({ error: e.message || String(e), trace: e.trace });
}

function tmpFile(buffer, suffix) {
  const p = path.join(TMP_DIR, `up_${Date.now()}_${Math.random().toString(36).slice(2)}${suffix}`);
  fs.writeFileSync(p, buffer);
  return p;
}

function cleanup(paths) {
  for (const p of paths) {
    try { fs.unlinkSync(p); } catch (e) { /* ignore */ }
  }
}

// ---------------------------------------------------------------------------
// Demo (server's own solution.py / tests.json / classe / bd folders)
// ---------------------------------------------------------------------------
app.get('/api/demo', async (req, res) => {
  try {
    res.json(await callEngine('demo', {}));
  } catch (e) { sendErr(res, e); }
});

// ---------------------------------------------------------------------------
// Langues (centralized UI strings)
// ---------------------------------------------------------------------------
app.get('/api/langues', async (req, res) => {
  try {
    res.json(await callEngine('langues', { lang: req.query.lang || 'fr' }));
  } catch (e) { sendErr(res, e); }
});

// ---------------------------------------------------------------------------
// Copie: analyser (not persisted — per-request only)
// ---------------------------------------------------------------------------
app.post('/api/analyser', async (req, res) => {
  try {
    const { source, filename, lang, bareme, python, compiler } = req.body;
    res.json(await callEngine('analyser', { source, filename, lang, bareme, python, compiler }));
  } catch (e) { sendErr(res, e); }
});

// ---------------------------------------------------------------------------
// Correction: corriger one copy against one solution (not persisted)
// ---------------------------------------------------------------------------
app.post('/api/corriger', async (req, res) => {
  try {
    const { eleve_source, solution_source, tests_source, lang, bareme, python } = req.body;
    res.json(await callEngine('corriger', {
      eleve_source, solution_source, tests_source, lang, bareme, python,
    }));
  } catch (e) { sendErr(res, e); }
});

app.post('/api/executer', async (req, res) => {
  try {
    const { source, fonction, args, stdin, python } = req.body;
    res.json(await callEngine('executer', { source, fonction, args, stdin, python }));
  } catch (e) { sendErr(res, e); }
});

app.post('/api/compat', async (req, res) => {
  try {
    const { source, stdin, pythons } = req.body;
    res.json(await callEngine('compat', { source, stdin, pythons }));
  } catch (e) { sendErr(res, e); }
});

// ---------------------------------------------------------------------------
// Interpréteurs
// ---------------------------------------------------------------------------
app.get('/api/interpreteurs', async (req, res) => {
  try {
    res.json(await callEngine('interpreteurs-scanner', { forcer: req.query.forcer === '1' }));
  } catch (e) { sendErr(res, e); }
});
app.post('/api/interpreteurs/info', async (req, res) => {
  try { res.json(await callEngine('interpreteurs-info', req.body)); } catch (e) { sendErr(res, e); }
});
app.post('/api/interpreteurs/valider', async (req, res) => {
  try { res.json(await callEngine('interpreteurs-valider', req.body)); } catch (e) { sendErr(res, e); }
});

// ---------------------------------------------------------------------------
// Barème
// ---------------------------------------------------------------------------
app.get('/api/bareme', async (req, res) => {
  try { res.json(await callEngine('bareme-list', {})); } catch (e) { sendErr(res, e); }
});
app.get('/api/bareme/one', async (req, res) => {
  try { res.json(await callEngine('bareme-get', { chemin: req.query.chemin || '' })); } catch (e) { sendErr(res, e); }
});
app.get('/api/bareme/resolved', async (req, res) => {
  try { res.json(await callEngine('bareme-resolved', { bareme: req.query.bareme || '' })); } catch (e) { sendErr(res, e); }
});
app.post('/api/bareme', async (req, res) => {
  try { res.json(await callEngine('bareme-save', req.body)); } catch (e) { sendErr(res, e); }
});
app.delete('/api/bareme', async (req, res) => {
  try { res.json(await callEngine('bareme-delete', { chemin: req.query.chemin })); } catch (e) { sendErr(res, e); }
});

// TP upload: solution.py / tests.json / barème JSON supplied by the teacher.
// Per the public-gallery requirement, uploaded TP config files are persisted
// and listed publicly (no login) alongside classe/bd uploads.
app.post('/api/tp/upload', upload.fields([
  { name: 'solution', maxCount: 1 },
  { name: 'tests', maxCount: 1 },
  { name: 'bareme', maxCount: 1 },
]), async (req, res) => {
  try {
    const files = [];
    for (const key of ['solution', 'tests', 'bareme']) {
      const f = (req.files && req.files[key] && req.files[key][0]) || null;
      if (f) files.push({ originalName: f.originalname, buffer: f.buffer, kind: key });
    }
    if (!files.length) return res.status(400).json({ error: 'Aucun fichier reçu (solution/tests/bareme).' });
    const entry = store.addEntry('tp', {
      files: files.map((f) => ({ originalName: f.originalName, buffer: f.buffer })),
      result: null,
      meta: { kinds: files.map((f) => ({ nom: f.originalName, type: f.kind })) },
    });
    res.json({ ok: true, entry });
  } catch (e) { sendErr(res, e); }
});

// ---------------------------------------------------------------------------
// Classe: batch grade an uploaded set of .py files against a solution/tests.
// Persisted + made public per the gallery requirement.
// ---------------------------------------------------------------------------
app.post('/api/classe', upload.fields([
  { name: 'fichiers', maxCount: 200 },
  { name: 'solution', maxCount: 1 },
  { name: 'tests', maxCount: 1 },
]), async (req, res) => {
  const tmps = [];
  try {
    const body = req.body || {};
    let solutionPath = body.solution_path || null;
    let testsPath = body.tests_path || null;
    const solutionFile = req.files && req.files.solution && req.files.solution[0];
    const testsFile = req.files && req.files.tests && req.files.tests[0];
    if (solutionFile) { solutionPath = tmpFile(solutionFile.buffer, '.py'); tmps.push(solutionPath); }
    if (testsFile) { testsPath = tmpFile(testsFile.buffer, '.json'); tmps.push(testsPath); }

    const copies = (req.files && req.files.fichiers) || [];
    if (!copies.length) return res.status(400).json({ error: 'Aucune copie envoyée (champ "fichiers").' });

    const fichiers = copies.map((f) => {
      const p = tmpFile(f.buffer, '.py');
      tmps.push(p);
      return { nom: f.originalname, path: p };
    });

    const payload = {
      fichiers,
      solution_path: solutionPath,
      tests_path: testsPath,
      lang: body.lang, bareme: body.bareme, python: body.python,
    };
    const result = await callEngine('classe', payload);

    // Persist: student copies + solution/tests + the grading result, public.
    const persistFiles = copies.map((f) => ({ originalName: f.originalname, buffer: f.buffer }));
    if (solutionFile) persistFiles.push({ originalName: 'solution__' + solutionFile.originalname, buffer: solutionFile.buffer });
    if (testsFile) persistFiles.push({ originalName: 'tests__' + testsFile.originalname, buffer: testsFile.buffer });
    const entry = store.addEntry('classe', {
      files: persistFiles,
      result,
      meta: { nbCopies: copies.length, lang: body.lang || 'fr', bareme: body.bareme || null },
    });

    res.json({ ok: true, id: entry.id, uploadedAt: entry.uploadedAt, ...result });
  } catch (e) { sendErr(res, e); } finally { cleanup(tmps); }
});

// ---------------------------------------------------------------------------
// BD: compare uploaded student database file(s) against a reference DB.
// ---------------------------------------------------------------------------
app.post('/api/bd/comparer', upload.fields([
  { name: 'fichiers', maxCount: 100 },
  { name: 'solution', maxCount: 1 },
]), async (req, res) => {
  const tmps = [];
  try {
    const body = req.body || {};
    const solutionFile = req.files && req.files.solution && req.files.solution[0];
    let solutionPath = body.solution_path || null;
    if (solutionFile) {
      solutionPath = tmpFile(solutionFile.buffer, path.extname(solutionFile.originalname) || '.db');
      tmps.push(solutionPath);
    }
    if (!solutionPath) return res.status(400).json({ error: 'Base solution manquante.' });

    const dbFiles = (req.files && req.files.fichiers) || [];
    if (!dbFiles.length) return res.status(400).json({ error: 'Aucune base élève envoyée.' });

    const fichiers = dbFiles.map((f) => {
      const p = tmpFile(f.buffer, path.extname(f.originalname) || '.db');
      tmps.push(p);
      return { nom: f.originalname, path: p };
    });

    const result = await callEngine('bd-comparer', {
      fichiers, solution_path: solutionPath, lang: body.lang, bareme: body.bareme,
    });

    const persistFiles = dbFiles.map((f) => ({ originalName: f.originalname, buffer: f.buffer }));
    if (solutionFile) persistFiles.push({ originalName: 'solution__' + solutionFile.originalname, buffer: solutionFile.buffer });
    const entry = store.addEntry('bd', {
      files: persistFiles,
      result,
      meta: { nbBases: dbFiles.length, lang: body.lang || 'fr' },
    });

    res.json({ ok: true, id: entry.id, uploadedAt: entry.uploadedAt, ...result });
  } catch (e) { sendErr(res, e); } finally { cleanup(tmps); }
});

app.get('/api/bd/diagnostic', async (req, res) => {
  try { res.json(await callEngine('bd-diagnostic', {})); } catch (e) { sendErr(res, e); }
});

// ---------------------------------------------------------------------------
// Public gallery — everything ever uploaded through classe/bd/tp, visible to
// any visitor with no login (per explicit scope confirmed with the user).
// ---------------------------------------------------------------------------
for (const cat of ['classe', 'bd', 'tp']) {
  app.get(`/api/gallery/${cat}`, (req, res) => {
    const limit = Math.min(parseInt(req.query.limit, 10) || 50, 200);
    const offset = parseInt(req.query.offset, 10) || 0;
    res.json(store.listEntries(cat, { limit, offset }));
  });
  app.get(`/api/gallery/${cat}/:id`, (req, res) => {
    const entry = store.getEntry(cat, req.params.id);
    if (!entry) return res.status(404).json({ error: 'introuvable' });
    res.json(entry);
  });
  // Scoped to one student's row within a batch run — unlike the route above,
  // the response never includes classmates' notes/errors, so this is the
  // link a teacher can safely hand to a single student.
  app.get(`/api/gallery/${cat}/:id/eleve/:nom`, (req, res) => {
    const entry = store.getEntry(cat, req.params.id);
    const resultats = entry && entry.result && entry.result.resultats;
    const r = Array.isArray(resultats) && resultats.find((x) => x.nom === req.params.nom);
    if (!r) return res.status(404).json({ error: "Résultat introuvable pour cet élève." });
    res.json({ id: entry.id, uploadedAt: entry.uploadedAt, categorie: cat, eleve: r });
  });
  app.get(`/api/gallery/${cat}/:id/file/:relPath(*)`, (req, res) => {
    const full = store.fileOnDisk(cat, path.join(req.params.id, req.params.relPath));
    if (!full) return res.status(404).json({ error: 'fichier introuvable' });
    res.download(full);
  });
}

// ---------------------------------------------------------------------------
// Exports: Excel / Access-SQLite-CSV for a class batch, and Excel for BD runs.
// These recompute against uploaded files (or a stored gallery run) and stream
// the resulting file back as a download.
// ---------------------------------------------------------------------------
app.post('/api/export/csv', async (req, res) => {
  // Zero-dependency CSV export of a classe "resultats" array already held by
  // the client (from /api/classe's response) — no need to call Python again.
  try {
    const rows = req.body.resultats || [];
    const header = 'nom;note;qualite;tests;structure\n';
    const body = rows.map((r) => {
      const rap = r.rapport || {};
      return [r.nom, rap.note, rap.qualite, rap.tests, rap.structure].join(';');
    }).join('\n');
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', 'attachment; filename="notes.csv"');
    res.send('﻿' + header + body);
  } catch (e) { sendErr(res, e); }
});

app.post('/api/export/excel', upload.fields([
  { name: 'fichiers', maxCount: 200 }, { name: 'solution', maxCount: 1 }, { name: 'tests', maxCount: 1 },
]), async (req, res) => {
  const tmps = [];
  try {
    const body = req.body || {};
    const solutionFile = req.files && req.files.solution && req.files.solution[0];
    const testsFile = req.files && req.files.tests && req.files.tests[0];
    let solutionPath = body.solution_path || null;
    let testsPath = body.tests_path || null;
    if (solutionFile) { solutionPath = tmpFile(solutionFile.buffer, '.py'); tmps.push(solutionPath); }
    if (testsFile) { testsPath = tmpFile(testsFile.buffer, '.json'); tmps.push(testsPath); }
    const copies = (req.files && req.files.fichiers) || [];
    const fichiers = copies.map((f) => {
      const p = tmpFile(f.buffer, '.py'); tmps.push(p);
      return { nom: f.originalname, path: p };
    });
    const outPath = tmpFile(Buffer.alloc(0), '.xlsx'); tmps.push(outPath);
    await callEngine('export-excel', {
      fichiers, solution_path: solutionPath, tests_path: testsPath,
      lang: body.lang, bareme: body.bareme, python: body.python, out_path: outPath,
    });
    res.download(outPath, 'rapport_classe.xlsx');
  } catch (e) { sendErr(res, e); } finally { setTimeout(() => cleanup(tmps), 3000); }
});

app.post('/api/export/access', upload.fields([
  { name: 'fichiers', maxCount: 200 }, { name: 'solution', maxCount: 1 }, { name: 'tests', maxCount: 1 },
]), async (req, res) => {
  const tmps = [];
  try {
    const body = req.body || {};
    const mode = body.mode || 'sqlite'; // access | sqlite | csv
    const solutionFile = req.files && req.files.solution && req.files.solution[0];
    const testsFile = req.files && req.files.tests && req.files.tests[0];
    let solutionPath = body.solution_path || null;
    let testsPath = body.tests_path || null;
    if (solutionFile) { solutionPath = tmpFile(solutionFile.buffer, '.py'); tmps.push(solutionPath); }
    if (testsFile) { testsPath = tmpFile(testsFile.buffer, '.json'); tmps.push(testsPath); }
    const copies = (req.files && req.files.fichiers) || [];
    const fichiers = copies.map((f) => {
      const p = tmpFile(f.buffer, '.py'); tmps.push(p);
      return { nom: f.originalname, path: p };
    });
    const ext = mode === 'access' ? '.accdb' : mode === 'csv' ? '' : '.db';
    const outPath = mode === 'csv'
      ? fs.mkdtempSync(path.join(TMP_DIR, 'csv_'))
      : tmpFile(Buffer.alloc(0), ext);
    tmps.push(outPath);
    const out = await callEngine('export-access', {
      fichiers, solution_path: solutionPath, tests_path: testsPath, mode,
      lang: body.lang, bareme: body.bareme, python: body.python, out_path: outPath,
    });
    if (out && out.error) return res.status(400).json(out);
    if (mode === 'csv') {
      res.status(200).json({ note: 'Export CSV écrit côté serveur (dossier temporaire) ; ' +
        'utilisez /api/export/access?mode=sqlite pour un fichier téléchargeable unique.' });
    } else {
      res.download(outPath, mode === 'access' ? 'rapport_classe.accdb' : 'rapport_classe.db');
    }
  } catch (e) { sendErr(res, e); } finally { setTimeout(() => cleanup(tmps), 3000); }
});

app.post('/api/bd/export/excel', upload.fields([
  { name: 'fichiers', maxCount: 100 }, { name: 'solution', maxCount: 1 },
]), async (req, res) => {
  const tmps = [];
  try {
    const body = req.body || {};
    const solutionFile = req.files && req.files.solution && req.files.solution[0];
    let solutionPath = body.solution_path || null;
    if (solutionFile) {
      solutionPath = tmpFile(solutionFile.buffer, path.extname(solutionFile.originalname) || '.db');
      tmps.push(solutionPath);
    }
    const dbFiles = (req.files && req.files.fichiers) || [];
    const fichiers = dbFiles.map((f) => {
      const p = tmpFile(f.buffer, path.extname(f.originalname) || '.db'); tmps.push(p);
      return { nom: f.originalname, path: p };
    });
    const outPath = tmpFile(Buffer.alloc(0), '.xlsx'); tmps.push(outPath);
    await callEngine('bd-export-excel', { fichiers, solution_path: solutionPath, out_path: outPath });
    res.download(outPath, 'rapport_bd.xlsx');
  } catch (e) { sendErr(res, e); } finally { setTimeout(() => cleanup(tmps), 3000); }
});

// ---------------------------------------------------------------------------
app.get('/api/health', (req, res) => res.json({ ok: true, projectRoot: PROJECT_ROOT }));

app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`correcteur-web listening on http://localhost:${PORT}`);
  // eslint-disable-next-line no-console
  console.log(`PROJECT_ROOT=${PROJECT_ROOT}`);
});
