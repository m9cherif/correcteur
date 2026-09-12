#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web/engine/cli.py — thin JSON-in/JSON-out dispatcher around the existing
pure-Python grading modules (analyseur.py, correcteur.py, bareme.py,
langues.py, interpreteurs.py, correcteur_access.py, rapport_excel.py,
rapport_access.py) so a Node/Express server can drive the exact same
grading logic used by the PyQt5 desktop app, without any GUI dependency.

Usage:
    python cli.py <commande> < payload.json
    python cli.py <commande> '{"...json..."}'

The JSON payload may be given as a single CLI argument (argv[2]) or piped
on stdin. Every command prints exactly one JSON object to stdout and
exits 0 on success. On failure it prints {"error": "..."} and exits 1.

This file must stay thin: it only marshals input/output around the real
functions in the parent project directory — no grading logic is
reimplemented here.
"""
import io
import json
import os
import sys
import tempfile
import traceback

# ---------------------------------------------------------------------------
# Make the parent project directory (with langues.py, analyseur.py, etc.)
# importable. PROJECT_ROOT env var lets a deployment point at a different
# checkout, but some hosts (e.g. Hostinger's Node app manager) redeploy
# web/ into a fresh "hbuilds/versions/<hash>/..." directory on every build
# and don't reliably persist custom env vars across that — so if the
# configured/default location doesn't actually contain the project, probe
# a short list of likely candidates instead of failing outright.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))


def _candidats_racine_projet():
    env = os.environ.get("PROJECT_ROOT")
    if env:
        yield env
    yield os.path.dirname(os.path.dirname(HERE))  # défaut : web/ et projet cousins

    # Hôtes type "hbuilds/versions/<hash>/nodejs/..." : le vrai checkout
    # (langues.py, bareme.py, ...) vit hors du dossier de build versionné,
    # au même niveau que "hbuilds" ou dans un sous-dossier "project".
    parties = HERE.replace("\\", "/").split("/")
    if "hbuilds" in parties:
        racine_domaine = "/".join(parties[:parties.index("hbuilds")])
        if racine_domaine:
            yield racine_domaine
            yield os.path.join(racine_domaine, "project")


def _resoudre_racine_projet():
    essais = []
    for c in _candidats_racine_projet():
        c = os.path.normpath(c)
        if c in essais:
            continue
        essais.append(c)
        if os.path.isfile(os.path.join(c, "langues.py")):
            return c, essais
    return essais[0], essais


PROJECT_ROOT, _RACINES_ESSAYEES = _resoudre_racine_projet()
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Force UTF-8 everywhere (Windows consoles default to cp1252 and choke on
# the emoji used throughout these modules).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

try:
    import langues            # noqa: E402
    import bareme              # noqa: E402
    import analyseur           # noqa: E402
    import correcteur          # noqa: E402
    import interpreteurs as itp  # noqa: E402
except ImportError as e:
    raise ImportError(
        f"{e}. PROJECT_ROOT résolu à {PROJECT_ROOT!r} (contient langues.py : "
        f"{os.path.isfile(os.path.join(PROJECT_ROOT, 'langues.py'))}). "
        f"Racines testées : {_RACINES_ESSAYEES}. Définissez PROJECT_ROOT vers "
        f"le dossier contenant langues.py/bareme.py/analyseur.py/... si aucune "
        f"ne convient."
    ) from e

try:
    import correcteur_access as ca
except Exception:
    ca = None

# Pure-Python .accdb -> .db fallback (access_parser, no Windows ACE/pyodbc
# needed) so Access comparison also works on a Linux server. Used only when
# not on Windows; on Windows correcteur_access already reads .accdb natively
# via pyodbc with full fidelity (including saved queries).
try:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "bd"))
    import convertir_accdb_en_db as accdb_conv
except Exception:
    accdb_conv = None

_ACCDB_DB_CACHE = {}


def _resolve_bd_path(path, tmp_dir):
    """Retourne un chemin .db utilisable par correcteur_access.comparer,
    convertissant un .accdb/.mdb à la volée (pure Python) si nécessaire."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".accdb", ".mdb") or os.name == "nt":
        return path
    if path in _ACCDB_DB_CACHE:
        return _ACCDB_DB_CACHE[path]
    if accdb_conv is None:
        raise RuntimeError(
            "Comparaison .accdb non disponible sur ce serveur (module "
            "access_parser manquant : pip install access_parser). "
            "Convertissez en SQLite (.db) pour une comparaison portable.")
    out, _tables = accdb_conv.convertir(path, tmp_dir)
    _ACCDB_DB_CACHE[path] = out
    return out


try:
    import rapport_excel
except Exception:
    rapport_excel = None

try:
    import rapport_access as ra
except Exception:
    ra = None


# ---------------------------------------------------------------------------
def _out(obj):
    json.dump(obj, sys.stdout, ensure_ascii=True, default=_default)
    sys.stdout.write("\n")


def _default(o):
    """Fallback JSON serializer for dataclasses / arbitrary objects
    (Probleme, Ecart, ...) coming out of the grading modules."""
    if hasattr(o, "__dict__"):
        d = dict(o.__dict__)
        # attach read-only properties commonly used by the GUI
        for prop in ("icone", "gravite_txt"):
            if hasattr(o, prop):
                try:
                    d[prop] = getattr(o, prop)
                except Exception:
                    pass
        return d
    return str(o)


def _payload():
    raw = None
    if len(sys.argv) > 2 and sys.argv[2].strip():
        raw = sys.argv[2]
    else:
        raw = sys.stdin.read()
    if not raw or not raw.strip():
        return {}
    return json.loads(raw)


def _tmp_write(source, suffix=".py"):
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(source)
    f.close()
    return f.name


def _apply_lang(p):
    lang = p.get("lang")
    if lang and lang in langues.LANGUES:
        langues.definir_langue(lang)


def _apply_bareme(p):
    b = p.get("bareme")
    if b:
        bareme.charger_profil(b) if not os.path.isfile(b) else bareme.charger(b)
    else:
        bareme.reinitialiser()


def _resolve_python(p):
    py = p.get("python")
    return py or analyseur.PYTHON


# ---------------------------------------------------------------------------
# demo : point at the project's own bundled example files
# ---------------------------------------------------------------------------
def cmd_demo(p):
    def rd(path):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def listdir(path, exts=None):
        if not os.path.isdir(path):
            return []
        out = []
        for f in sorted(os.listdir(path)):
            fp = os.path.join(path, f)
            if os.path.isfile(fp) and (not exts or f.lower().endswith(tuple(exts))):
                out.append(f)
        return out

    solution = os.path.join(PROJECT_ROOT, "solution.py")
    tests = os.path.join(PROJECT_ROOT, "tests.json")
    enonce = os.path.join(PROJECT_ROOT, "enonce.txt")
    classe_dir = os.path.join(PROJECT_ROOT, "classe")
    bd_dir = os.path.join(PROJECT_ROOT, "bd")
    essais_dir = os.path.join(PROJECT_ROOT, "essais")

    _out({
        "project_root": PROJECT_ROOT,
        "solution": {"path": solution, "source": rd(solution)},
        "tests": {"path": tests, "source": rd(tests)},
        "enonce": {"path": enonce, "source": rd(enonce)},
        "classe": {"dir": classe_dir, "fichiers": listdir(classe_dir, [".py"])},
        "bd": {
            "dir": bd_dir,
            "solution_db": os.path.join(bd_dir, "solution.db")
            if os.path.isfile(os.path.join(bd_dir, "solution.db")) else None,
            "fichiers": listdir(bd_dir, [".db", ".sqlite", ".accdb"]),
        },
        "essais": {"dir": essais_dir, "fichiers": listdir(essais_dir, [".py"])},
    })


# ---------------------------------------------------------------------------
# langues : centralize UI strings for the frontend
# ---------------------------------------------------------------------------
UI_KEYS = [
    "titre_app", "tab_config", "tab_lot", "note_finale", "note", "sur", "axe",
    "ax_qualite", "ax_tests", "ax_structure", "total", "tests", "structure",
    "sur_code", "solution", "diff", "attendu", "obtenu", "fichier", "erreur",
    "avertissement", "c_regle", "c_code", "c_nb", "c_unite", "c_deduit",
    "c_plafond", "bareme_titre", "aucun_deduit", "total_deduit", "note_bas",
    "rapport", "nb_err", "nb_warn", "legende", "ligne", "cause", "fix",
    "corrige", "original", "aucun", "remarques", "suggestion", "interpreteur",
    "exec_complet", "exception", "fn_manquante", "fn_args", "fn_noms",
    "fn_extra", "timeout", "c_interp", "sous_interp", "langue_expl",
    "sous_langue", "bt_corriger", "col_q", "col_r", "col_s", "c_mention",
]


def cmd_langues(p):
    _apply_lang(p)
    strings = {}
    for k in UI_KEYS:
        try:
            strings[k] = langues.U(k)
        except Exception:
            pass
    _out({
        "langues": langues.LANGUES,
        "courante": langues.langue(),
        "mentions": langues.mentions(),
        "strings": strings,
    })


# ---------------------------------------------------------------------------
# analyser : analyseur.analyser_source + calculer_note
# ---------------------------------------------------------------------------
def cmd_analyser(p):
    _apply_lang(p)
    _apply_bareme(p)
    source = p.get("source", "")
    filename = p.get("filename") or "copie.py"
    py = p.get("python") if p.get("compiler", True) else None
    problemes = analyseur.analyser_source(source, filename, py=py)
    note, mention, detail = analyseur.calculer_note(problemes)
    bloc = analyseur.bloc_note(note, mention, detail)
    annote = analyseur.annoter(source.splitlines(), problemes, filename)
    _out({
        "problemes": problemes,
        "note": note, "mention": mention,
        "detail": detail, "bloc": bloc,
        "annote": annote,
        "nb_erreurs": sum(1 for x in problemes if x.gravite == analyseur.ERREUR),
        "nb_avert": sum(1 for x in problemes if x.gravite == analyseur.AVERT),
    })


# ---------------------------------------------------------------------------
# corriger : correcteur.corriger (student vs. reference solution)
# ---------------------------------------------------------------------------
def cmd_corriger(p):
    _apply_lang(p)
    _apply_bareme(p)
    if p.get("python"):
        correcteur.PYTHON = p["python"]
        analyseur.PYTHON = p["python"]

    f_eleve = p.get("eleve_path") or _tmp_write(p.get("eleve_source", ""))
    f_solution = p.get("solution_path") or _tmp_write(p.get("solution_source", ""))
    f_tests = p.get("tests_path")
    tmp_tests = None
    if not f_tests and p.get("tests_source"):
        tmp_tests = _tmp_write(p["tests_source"], ".json")
        f_tests = tmp_tests

    try:
        r = correcteur.corriger(f_eleve, f_solution, f_tests)
        r["axes_pts"] = bareme.axes()
        r["note_max"] = bareme.note_max()
        _out(r)
    finally:
        for tmp, given in ((f_eleve, p.get("eleve_path")),
                           (f_solution, p.get("solution_path"))):
            if not given:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        if tmp_tests:
            try:
                os.unlink(tmp_tests)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# classe : batch-grade many student files against one solution/tests
# ---------------------------------------------------------------------------
def cmd_classe(p):
    _apply_lang(p)
    _apply_bareme(p)
    if p.get("python"):
        correcteur.PYTHON = p["python"]
        analyseur.PYTHON = p["python"]

    f_solution = p.get("solution_path") or _tmp_write(p.get("solution_source", ""))
    f_tests = p.get("tests_path")
    tmp_tests = None
    if not f_tests and p.get("tests_source"):
        tmp_tests = _tmp_write(p["tests_source"], ".json")
        f_tests = tmp_tests

    fichiers = p.get("fichiers", [])  # [{nom, path?, source?}]
    resultats = []
    tmp_files = []
    try:
        for entry in fichiers:
            nom = entry.get("nom") or os.path.basename(entry.get("path", "copie.py"))
            path = entry.get("path")
            if not path:
                path = _tmp_write(entry.get("source", ""))
                tmp_files.append(path)
            try:
                r = correcteur.corriger(path, f_solution, f_tests)
                resultats.append({"nom": nom, "ok": True, "rapport": r})
            except Exception as e:
                resultats.append({"nom": nom, "ok": False,
                                  "erreur": f"{type(e).__name__}: {e}"})

        notes = [r["rapport"]["note"] for r in resultats if r["ok"]]
        stats = {
            "n": len(resultats),
            "n_ok": len(notes),
            "moyenne": round(sum(notes) / len(notes), 2) if notes else 0,
            "min": min(notes) if notes else 0,
            "max": max(notes) if notes else 0,
        }
        _out({"resultats": resultats, "stats": stats})
    finally:
        for t in tmp_files:
            try:
                os.unlink(t)
            except OSError:
                pass
        if not p.get("solution_path"):
            try:
                os.unlink(f_solution)
            except OSError:
                pass
        if tmp_tests:
            try:
                os.unlink(tmp_tests)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# executer : run student code (Editeur "Exécuter" action)
# ---------------------------------------------------------------------------
def cmd_executer(p):
    py = _resolve_python(p)
    correcteur.PYTHON = py
    path = p.get("path") or _tmp_write(p.get("source", ""))
    try:
        res = correcteur.executer(path, p.get("fonction") or None,
                                   p.get("args") or None, p.get("stdin", ""))
        _out(res)
    finally:
        if not p.get("path"):
            try:
                os.unlink(path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# compat : run the same source across several interpreters
# ---------------------------------------------------------------------------
def cmd_compat(p):
    source = p.get("source", "")
    stdin = p.get("stdin", "")
    chemins = p.get("pythons") or None
    res = itp.matrice_compatibilite(source, chemins, stdin)
    _out({"resultats": res})


# ---------------------------------------------------------------------------
# interpreteurs
# ---------------------------------------------------------------------------
def cmd_interpreteurs_scanner(p):
    _out({"interpretes": itp.scanner(bool(p.get("forcer")))})


def cmd_interpreteurs_info(p):
    _out(itp.info(p["chemin"], bool(p.get("forcer"))))


def cmd_interpreteurs_valider(p):
    _out(itp.valider(p["chemin"]))


# ---------------------------------------------------------------------------
# bareme : rubric management (baremes/*.json)
# ---------------------------------------------------------------------------
def cmd_bareme_list(p):
    profils = bareme.profils()
    _out({"profils": [{"nom": n, "chemin": c} for n, c in profils]})


def cmd_bareme_get(p):
    chemin = p.get("chemin")
    if chemin:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
        _out({"chemin": chemin, "data": data})
    else:
        bareme.reinitialiser()
        _out({"chemin": "", "data": bareme.actif()})


def cmd_bareme_resolved(p):
    """Resolved/active view: regles(), axes(), note_max(), seuils()..."""
    _apply_bareme(p)
    _out({
        "nom": bareme.nom(), "chemin": bareme.chemin(),
        "axes": bareme.axes(), "axes_bd": bareme.axes_bd(),
        "regles": bareme.regles(), "note_max": bareme.note_max(),
        "seuils": bareme.seuils(), "tolerance": bareme.tolerance(),
        "erreur_fatale": bareme.erreur_fatale(),
        "actif": bareme.actif(),
    })


def cmd_bareme_save(p):
    chemin = p.get("chemin")
    data = p.get("data")
    if not chemin:
        nom_fichier = (p.get("nom") or "mon_bareme").strip().replace(" ", "_")
        chemin = os.path.join(bareme.DOSSIER, f"{nom_fichier}.json")
    os.makedirs(os.path.dirname(os.path.abspath(chemin)), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _out({"chemin": chemin, "ok": True})


def cmd_bareme_delete(p):
    chemin = p["chemin"]
    if os.path.isfile(chemin):
        os.remove(chemin)
        _out({"ok": True})
    else:
        _out({"ok": False, "erreur": "introuvable"})


def cmd_bareme_create_defaults(p):
    faits = bareme.creer_profils_prets()
    _out({"crees": faits})


# ---------------------------------------------------------------------------
# BD (Access/SQLite) comparison
# ---------------------------------------------------------------------------
def _require_ca():
    if ca is None:
        raise RuntimeError("correcteur_access.py indisponible")


def cmd_bd_comparer(p):
    _require_ca()
    _apply_lang(p)
    _apply_bareme(p)
    solution_path = p["solution_path"]
    fichiers = p.get("fichiers", [])  # [{nom, path}]
    resultats = []
    tmp_dir = tempfile.mkdtemp(prefix="accdb2sqlite_")
    try:
        try:
            solution_db = _resolve_bd_path(solution_path, tmp_dir)
        except Exception as e:
            _out({"resultats": [{"nom": os.path.basename(solution_path),
                                  "ok": False, "erreur": str(e)}],
                  "stats": {"n": 0, "n_ok": 0, "moyenne": 0}})
            return
        for entry in fichiers:
            nom = entry.get("nom") or os.path.basename(entry["path"])
            path = entry["path"]
            try:
                db_path = _resolve_bd_path(path, tmp_dir)
                r = ca.comparer(db_path, solution_db)
                resultats.append({"nom": nom, "ok": True, "rapport": r})
            except Exception as e:
                resultats.append({"nom": nom, "ok": False,
                                  "erreur": f"{type(e).__name__}: {e}"})
        notes = [r["rapport"]["note"] for r in resultats if r["ok"]]
        stats = {"n": len(resultats), "n_ok": len(notes),
                 "moyenne": round(sum(notes) / len(notes), 2) if notes else 0}
        _out({"resultats": resultats, "stats": stats})
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            ca.fermer_connexions()
        except Exception:
            pass


def cmd_bd_diagnostic(p):
    _require_ca()
    _out({"diagnostic": ca.diagnostic()})


def cmd_bd_export_excel(p):
    _require_ca()
    solution_path = p["solution_path"]
    out_path = p["out_path"]
    fichiers = p.get("fichiers", [])
    rapports = []
    tmp_dir = tempfile.mkdtemp(prefix="accdb2sqlite_")
    try:
        solution_db = _resolve_bd_path(solution_path, tmp_dir)
        for entry in fichiers:
            nom = entry.get("nom") or os.path.basename(entry["path"])
            try:
                db_path = _resolve_bd_path(entry["path"], tmp_dir)
                r = ca.comparer(db_path, solution_db)
                rapports.append((nom, r))
            except Exception:
                pass
        path = ca.exporter_excel(out_path, rapports, solution_db)
        _out({"path": path})
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            ca.fermer_connexions()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Class-wide exports (Excel / Access-SQLite-CSV) — reuses rapport_excel.py
# and rapport_access.py exactly like lanceur.py's batch grading.
# ---------------------------------------------------------------------------
def _classe_resultats_bruts(p):
    """[(nom, chemin_fichier, rapport_dict), ...] as expected by rapport_excel."""
    _apply_lang(p)
    _apply_bareme(p)
    if p.get("python"):
        correcteur.PYTHON = p["python"]
        analyseur.PYTHON = p["python"]
    f_solution = p.get("solution_path") or _tmp_write(p.get("solution_source", ""))
    f_tests = p.get("tests_path")
    tmp_tests = None
    if not f_tests and p.get("tests_source"):
        tmp_tests = _tmp_write(p["tests_source"], ".json")
        f_tests = tmp_tests

    out, tmp_files = [], []
    for entry in p.get("fichiers", []):
        nom = entry.get("nom") or os.path.basename(entry.get("path", "copie.py"))
        path = entry.get("path")
        if not path:
            path = _tmp_write(entry.get("source", ""))
            tmp_files.append(path)
        try:
            r = correcteur.corriger(path, f_solution, f_tests)
            out.append((nom, path, r))
        except Exception as e:
            out.append((nom, path, {"erreur": f"{type(e).__name__}: {e}"}))
    return out, f_solution, f_tests, tmp_files, tmp_tests


def cmd_export_excel(p):
    if rapport_excel is None:
        raise RuntimeError("rapport_excel.py indisponible (openpyxl manquant ?)")
    resultats, f_solution, f_tests, tmp_files, tmp_tests = _classe_resultats_bruts(p)
    out_path = p["out_path"]
    try:
        rapport_excel.exporter(out_path, resultats, f_solution, f_tests or "",
                                _resolve_python(p))
        _out({"path": out_path})
    finally:
        for t in tmp_files:
            try:
                os.unlink(t)
            except OSError:
                pass
        if tmp_tests:
            try:
                os.unlink(tmp_tests)
            except OSError:
                pass


def cmd_export_access(p):
    if ra is None:
        raise RuntimeError("rapport_access.py indisponible")
    mode = p.get("mode", "sqlite")
    if mode == "access" and os.name != "nt":
        _out({"error": "Export .accdb indisponible sur ce serveur (Windows + "
                        "moteur Access requis). Utilisez mode=sqlite ou csv."})
        return
    resultats, f_solution, f_tests, tmp_files, tmp_tests = _classe_resultats_bruts(p)
    out_path = p["out_path"]
    try:
        ra.exporter(out_path, resultats, mode, f_solution, f_tests or "",
                    _resolve_python(p))
        _out({"path": out_path})
    finally:
        for t in tmp_files:
            try:
                os.unlink(t)
            except OSError:
                pass
        if tmp_tests:
            try:
                os.unlink(tmp_tests)
            except OSError:
                pass


# ---------------------------------------------------------------------------
COMMANDES = {
    "demo": cmd_demo,
    "langues": cmd_langues,
    "analyser": cmd_analyser,
    "corriger": cmd_corriger,
    "classe": cmd_classe,
    "executer": cmd_executer,
    "compat": cmd_compat,
    "interpreteurs-scanner": cmd_interpreteurs_scanner,
    "interpreteurs-info": cmd_interpreteurs_info,
    "interpreteurs-valider": cmd_interpreteurs_valider,
    "bareme-list": cmd_bareme_list,
    "bareme-get": cmd_bareme_get,
    "bareme-resolved": cmd_bareme_resolved,
    "bareme-save": cmd_bareme_save,
    "bareme-delete": cmd_bareme_delete,
    "bareme-create-defaults": cmd_bareme_create_defaults,
    "bd-comparer": cmd_bd_comparer,
    "bd-diagnostic": cmd_bd_diagnostic,
    "bd-export-excel": cmd_bd_export_excel,
    "export-excel": cmd_export_excel,
    "export-access": cmd_export_access,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDES:
        _out({"error": f"commande inconnue (attendu: {', '.join(COMMANDES)})"})
        return 2
    try:
        payload = _payload()
        COMMANDES[sys.argv[1]](payload)
        return 0
    except Exception as e:
        _out({"error": f"{type(e).__name__}: {e}",
              "trace": traceback.format_exc()[-4000:]})
        return 1


if __name__ == "__main__":
    sys.exit(main())
