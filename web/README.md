# Correcteur — Web

A browser front-end for the PyQt5 desktop app `correcteur_app.py`: paste or
upload a student's Python file, analyze/correct it against a reference
`solution.py` + `tests.json` + a JSON barème, batch-grade a whole class
folder, compare student SQLite/Access databases against a reference
database, and export CSV/Excel/SQLite reports.

**No grading logic was reimplemented.** `web/engine/cli.py` is a thin
JSON-in/JSON-out dispatcher that `sys.path.insert`s the parent project
directory and calls the *exact* existing pure-Python functions:
`analyseur.py`, `correcteur.py`, `bareme.py`, `langues.py`,
`interpreteurs.py`, `correcteur_access.py`, `rapport_excel.py`,
`rapport_access.py`. `web/server.js` (Express) spawns that CLI per request
and returns its JSON to the vanilla-JS single-page frontend in `web/public/`.

## Public gallery (important — read before deploying)

Every file uploaded through **Classe** (student copies), **BD** (student/
reference database files) and **TP** (solution.py / tests.json / barème)
is now **persisted on disk** under `web/data/<classe|bd|tp>/` and listed in
a **public "Galerie" tab with no login and no access control** — anyone who
can reach the server can browse every student's name, code, grade and
database contents ever uploaded. This was an explicit scope decision made
for this deployment; it is **not** how student grading data is normally
handled (comparable to a FERPA/GDPR concern for a real school), so treat
`web/data/` as sensitive if you enable it on a real server: put it behind
your own auth/reverse-proxy rule if the public gallery is not actually
wanted, or simply don't point a public URL at this app. Pasting code into
the **Copie** tab and one-off **Analyser/Corriger** calls are *not*
persisted or public — only actual file uploads through Classe/BD/TP are.

`web/data/` layout: `data/<cat>/index.json` (newest-first array of
`{id, uploadedAt, files, meta, result}`) plus `data/<cat>/files/<id>/...`
holding copies of the uploaded files. Filenames are sanitized
(`[A-Za-z0-9._-]` only) before being written to disk.

## Run locally

```
cd web
npm install
npm start                 # http://localhost:3000
```

Requires Python 3 on PATH (or set `PYTHON_BIN`) with the packages the
parent project already needs:

- **openpyxl** — required for `/api/export/excel` and the BD Excel export
  (`pip install openpyxl`). Without it those two endpoints return a clear
  JSON error; everything else still works.
- **pyodbc** + Microsoft Access Database Engine (ACE) — optional, Windows
  only, needed to *read* `.accdb` student/reference databases. Without it,
  `.accdb` comparison returns a clear JSON error and SQLite (`.db`)
  comparison keeps working everywhere (Windows, Linux, macOS).
- **pywin32** — optional, Windows only, improves Access relationship/key
  detection via ADOX (used automatically if present).
- **access_parser** — optional, pure-Python best-effort `.accdb` reader
  used as a last resort when neither pyodbc nor mdbtools are available.

There is no top-level `requirements.txt` in the parent project; the above
is the complete optional-dependency list actually imported by
`correcteur_access.py` / `rapport_excel.py`.

## Environment variables

| Variable       | Default                          | Purpose |
|----------------|-----------------------------------|---------|
| `PORT`         | `3000`                            | HTTP port for the Express server |
| `PYTHON_BIN`   | `python` (win) / `python3` (unix) | Interpreter used to run `engine/cli.py` |
| `PROJECT_ROOT` | parent of `web/`                  | Where `solution.py`, `baremes/`, `classe/`, `bd/` etc. live — set this if you deploy `web/` separately from the rest of the project |

## REST API

All endpoints return JSON except the file-download exports.

- `GET /api/demo` — the project's own bundled `solution.py`/`tests.json`/`enonce.txt`/`classe/`/`bd/`/`essais/`.
- `GET /api/langues?lang=fr` — centralized UI strings + mention thresholds from `langues.py` (fr/ar/en).
- `POST /api/analyser` — `{source, filename, lang, bareme, python}` → problems + note (Copie tab; not persisted).
- `POST /api/corriger` — `{eleve_source, solution_source, tests_source, lang, bareme, python}` → full correction report (not persisted).
- `POST /api/executer` — run student code, capture stdout/return value.
- `POST /api/compat` — run the same source across every interpreter `interpreteurs.scanner()` finds.
- `GET /api/interpreteurs`, `POST /api/interpreteurs/info`, `POST /api/interpreteurs/valider`.
- `GET/POST/DELETE /api/bareme`, `GET /api/bareme/one`, `GET /api/bareme/resolved` — rubric profile CRUD (`baremes/*.json`).
- `POST /api/tp/upload` (multipart: `solution`,`tests`,`bareme`) — **persisted + public**.
- `POST /api/classe` (multipart: `fichiers[]`,`solution`,`tests`) — batch-grade a class folder — **persisted + public**.
- `POST /api/bd/comparer` (multipart: `fichiers[]`,`solution`) — compare student DB files to a reference DB — **persisted + public**. `.accdb` on a non-Windows host returns a graceful per-file error instead of crashing; `.db`/`.sqlite` always works.
- `GET /api/bd/diagnostic` — which Access drivers (pyodbc/mdbtools/pywin32/access_parser) are available on this server.
- `GET /api/gallery/:cat` (`classe`|`bd`|`tp`), `GET /api/gallery/:cat/:id`, `GET /api/gallery/:cat/:id/file/:relPath` — the public gallery described above.
- `POST /api/export/csv` — zero-dependency CSV of a class's results (built in Node from data already in hand).
- `POST /api/export/excel`, `POST /api/export/access` (`mode=access|sqlite|csv`) — reuse `rapport_excel.py`/`rapport_access.py` and stream the resulting file back.
- `POST /api/bd/export/excel` — reuses `correcteur_access.exporter_excel`.

PDF export deliberately has no server-side dependency: the **Copie** tab's
"Imprimer / PDF" button uses the browser's native `window.print()` with
print-specific CSS (`@media print` in `styles.css`).

## Verified end-to-end (this environment: Windows, Python 3.12.4, Node 24)

- `GET /api/demo` → returns the project's real `solution.py`/`tests.json` content.
- `POST /api/analyser` on a snippet with a missing `:` → one `E001` problem, note 12/20.
- `POST /api/corriger` on `classe/01_ahmed.py` vs. `solution.py` + `tests.json` → note 16.27/20 (qualite 4.05, tests 8.89, structure 3.33).
- `POST /api/classe` with 3 files from the project's real `classe/` folder → graded, persisted, and immediately visible via `GET /api/gallery/classe`.
- `POST /api/bd/comparer` with `bd/eleve1_sami.db` vs `bd/solution.db` → note 18.67/20, one missing-query écart, persisted to the BD gallery.
- `POST /api/tp/upload` with `solution.py`+`tests.json` → persisted to the TP gallery.
- `GET /api/bareme` → lists all 6 profiles in `baremes/*.json`.
- `GET /api/interpreteurs` → detects the local `python.exe`/`py.exe` installs.
- `POST /api/export/excel` → downloads a valid `.xlsx` (verified as "Microsoft Excel 2007+").
- `POST /api/export/access?mode=sqlite` → downloads a valid SQLite `.db` report.
- `GET /api/bd/diagnostic` → reports pyodbc + Access drivers present on this Windows box (pywin32 also available here, so ADOX relationships are used).

## Deploying on Hostinger

Hostinger's Node.js application hosting runs the Express server fine, but
`engine/cli.py` needs a **Python 3 runtime reachable on PATH** — this is
available on a **Hostinger VPS** (install Python 3 + `pip install
openpyxl` there) but is typically **not available on shared/shared-Node
hosting plans**, which only provision Node. If you deploy on shared
hosting without a Python runtime, every `/api/*` endpoint that calls the
engine will fail with a clear "impossible de lancer python" JSON error;
the static frontend will still load.

Steps on a VPS:
1. Install Node.js and Python 3 (`apt install python3 python3-pip`).
2. `pip3 install openpyxl` (required); optionally `pip3 install
   access-parser` and `apt install mdbtools` for best-effort `.accdb`
   reading on Linux (still no write support, and no real ACE engine —
   `.accdb` remains best-effort/Windows-quality only there).
3. Copy the whole `exemples/` project (not just `web/`) to the server, or
   set `PROJECT_ROOT` to wherever it lives.
4. `cd web && npm install && PORT=3000 PYTHON_BIN=python3 PROJECT_ROOT=/path/to/exemples node server.js`
   (or run it under `pm2`/systemd).
5. Point Hostinger's reverse proxy / the Node app config at that port.
6. `.accdb` comparison stays Windows-only in practice (needs the real ACE
   engine or pywin32 for full fidelity) — document this for your users and
   steer them to SQLite (`.db`) for cross-platform grading, which works
   identically on Linux.
7. Because uploads are now public (see "Public gallery" above), decide
   before going live whether you actually want that — there is no
   authentication layer in this build.
