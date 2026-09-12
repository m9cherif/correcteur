// engine.js — spawns web/engine/cli.py and returns parsed JSON.
// Thin bridge only: all grading logic lives in the existing Python modules.
'use strict';
const { spawnSync, spawn } = require('child_process');
const path = require('path');

// Some restricted hosting panels (e.g. Hostinger's Node.js app manager) run
// Node with a PATH that doesn't include python3, and don't persist custom
// env vars (PYTHON_BIN) across app restarts/redeploys. Rather than relying
// on that config surviving, probe a short list of known-good locations once
// at startup and cache whichever one actually runs.
const CANDIDATS_PYTHON = [
  process.env.PYTHON_BIN,
  process.platform === 'win32' ? 'python' : null,
  'python3',
  'python',
  '/usr/bin/python3',
  '/usr/local/bin/python3',
  '/opt/alt/python311/bin/python3',
  '/opt/alt/python312/bin/python3',
].filter(Boolean);

function detecterPythonBin() {
  for (const candidat of CANDIDATS_PYTHON) {
    try {
      const r = spawnSync(candidat, ['--version']);
      if (!r.error && r.status === 0) return candidat;
    } catch (e) { /* candidat suivant */ }
  }
  return CANDIDATS_PYTHON[0] || 'python3';
}

const PYTHON_BIN = detecterPythonBin();
const CLI = path.join(__dirname, 'engine', 'cli.py');

function callEngine(command, payload) {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON_BIN, [CLI, command], {
      cwd: __dirname,
      env: Object.assign({}, process.env, { PYTHONIOENCODING: 'utf-8' }),
    });
    let out = '';
    let err = '';
    child.stdout.on('data', (d) => { out += d.toString('utf-8'); });
    child.stderr.on('data', (d) => { err += d.toString('utf-8'); });
    child.on('error', (e) => reject(new Error(
      `Impossible de lancer ${PYTHON_BIN}: ${e.message}. ` +
      `Interpréteurs testés au démarrage : ${CANDIDATS_PYTHON.join(', ')}. ` +
      `Définissez PYTHON_BIN avec le chemin exact (ex: /opt/alt/python311/bin/python3) si aucun ne convient.`
    )));
    child.on('close', () => {
      const text = out.trim();
      if (!text) {
        reject(new Error(`Aucune sortie de l'engine Python (${command}). stderr: ${err.slice(-800)}`));
        return;
      }
      let data;
      try {
        data = JSON.parse(text);
      } catch (e) {
        reject(new Error(`Réponse JSON invalide de l'engine (${command}): ${text.slice(0, 400)}`));
        return;
      }
      if (data && data.error) {
        const e = new Error(data.error);
        e.trace = data.trace;
        reject(e);
        return;
      }
      resolve(data);
    });
    child.stdin.write(JSON.stringify(payload || {}));
    child.stdin.end();
  });
}

module.exports = { callEngine, PYTHON_BIN };
