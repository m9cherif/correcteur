// store.js — simple persistent JSON-index store for the public gallery.
// No database: one folder + one index.json per category under web/data/.
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const DATA_DIR = path.join(__dirname, 'data');
const CATEGORIES = ['classe', 'bd', 'tp'];

for (const cat of CATEGORIES) {
  const dir = path.join(DATA_DIR, cat, 'files');
  fs.mkdirSync(dir, { recursive: true });
  const idx = path.join(DATA_DIR, cat, 'index.json');
  if (!fs.existsSync(idx)) fs.writeFileSync(idx, '[]', 'utf-8');
}

function indexPath(cat) {
  return path.join(DATA_DIR, cat, 'index.json');
}

function filesDir(cat) {
  return path.join(DATA_DIR, cat, 'files');
}

function readIndex(cat) {
  try {
    return JSON.parse(fs.readFileSync(indexPath(cat), 'utf-8'));
  } catch (e) {
    return [];
  }
}

function writeIndex(cat, arr) {
  fs.writeFileSync(indexPath(cat), JSON.stringify(arr, null, 2), 'utf-8');
}

// Sanitize an original filename to something safe to keep on disk long-term.
function safeName(name) {
  const base = path.basename(String(name || 'fichier')).replace(/[^A-Za-z0-9._-]+/g, '_');
  return base.slice(0, 150) || 'fichier';
}

function newId() {
  return Date.now().toString(36) + '_' + crypto.randomBytes(4).toString('hex');
}

// Persist a batch entry: copies each uploaded file's buffer/tmp path into the
// category's permanent folder under a unique run id, then appends a record
// (with the caller-supplied JSON-safe `result` and `meta`) to the index.
function addEntry(cat, { files = [], result = null, meta = {} }) {
  const id = newId();
  const runDir = path.join(filesDir(cat), id);
  fs.mkdirSync(runDir, { recursive: true });
  const savedFiles = [];
  for (const f of files) {
    const clean = safeName(f.originalName);
    const dest = path.join(runDir, clean);
    if (f.buffer) {
      fs.writeFileSync(dest, f.buffer);
    } else if (f.srcPath) {
      fs.copyFileSync(f.srcPath, dest);
    }
    savedFiles.push({ nom: f.originalName, savedAs: `${id}/${clean}` });
  }
  const entry = {
    id,
    uploadedAt: new Date().toISOString(),
    files: savedFiles,
    meta,
    result,
  };
  const idx = readIndex(cat);
  idx.unshift(entry); // newest first
  writeIndex(cat, idx);
  return entry;
}

function listEntries(cat, { limit = 50, offset = 0 } = {}) {
  const idx = readIndex(cat);
  const page = idx.slice(offset, offset + limit);
  // Lightweight listing: strip the (possibly large) result payload.
  return {
    total: idx.length,
    items: page.map((e) => ({
      id: e.id, uploadedAt: e.uploadedAt, files: e.files, meta: e.meta,
      hasResult: !!e.result,
    })),
  };
}

function getEntry(cat, id) {
  const idx = readIndex(cat);
  return idx.find((e) => e.id === id) || null;
}

function fileOnDisk(cat, relPath) {
  const resolved = path.resolve(filesDir(cat), relPath);
  if (!resolved.startsWith(path.resolve(filesDir(cat)))) return null; // path traversal guard
  return fs.existsSync(resolved) ? resolved : null;
}

module.exports = { addEntry, listEntries, getEntry, fileOnDisk, safeName, DATA_DIR };
