// engine.js — spawns web/engine/cli.py and returns parsed JSON.
// Thin bridge only: all grading logic lives in the existing Python modules.
'use strict';
const { spawn } = require('child_process');
const path = require('path');

const PYTHON_BIN = process.env.PYTHON_BIN || (process.platform === 'win32' ? 'python' : 'python3');
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
    child.on('error', (e) => reject(new Error(`Impossible de lancer ${PYTHON_BIN}: ${e.message}`)));
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
