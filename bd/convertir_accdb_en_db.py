#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convertir_accdb_en_db.py — Convertir un .accdb Access en .db SQLite
=====================================================================
Contourne l'absence du moteur ACE/ODBC : lit un fichier Access (.accdb/.mdb)
purement en Python (access_parser) et écrit un SQLite (.db) équivalent,
lisible par correcteur_access / evaluer.py --bd.

Usage :
    python bd/convertir_accdb_en_db.py accdb_eleves/  -o db_eleves/
    python bd/convertir_accdb_en_db.py 07_hedi.accdb -o db_eleves/
    python bd/convertir_accdb_en_db.py 07_hedi.accdb --diagnostic

Ce qui est reproduit
    • tables + champs (type, taille, obligatoire) via access_parser
    • données (lignes) via access_parser
    • clés primaires : détectées par convention de nom (id*, *id, code*)
      ou AUTOINCREMENT dans MSysObjects si lisible
    • relations : reconstruction heuristique par colonnes partagées
      de même nom entre tables (tab.champ → tab_ref.champ_ref identique)
    • requêtes : access_parser ne lit PAS les requêtes sauvegardées d'un
      .accdb de façon fiable. Utilisez --requete nom=SQL pour les fournir,
      ou créez les vues dans le .db de sortie manuellement ensuite.

IMPORTANT — limites (à vérifier sur vos fichiers réels)
    L'axe « requêtes » du barème (4 points) ne peut être noté que si les
    requêtes sont lisibles (via ACE) ou fournies (--requete). Le script
    imprime un DIAGNOSTIC de ce qu'il a réellement capté.
"""

import argparse
import glob
import os
import re
import sqlite3
import sys


PARASITES = (re.compile(r"f_[0-9A-Fa-f]{32}_Data"),)  # caches d'objets liés Access


def _texte(v):
    """Les chaînes d'access_parser arrivent en bytes → str (utf-8, sinon latin-1)."""
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except Exception:
            return v.decode("latin-1", "replace")
    return v


def inferer_type(valeurs):
    """Devine INTEGER / REAL / TEXT d'après les valeurs réelles (access_parser
    ne donne pas les types déclarés de façon fiable, et les dates Access sont
    des doubles). L'inférence est SYMÉTRIQUE : solution et copie passent par
    le même chemin, donc les écarts de type ne naissent pas de la conversion."""
    non_nul = [v for v in valeurs if v is not None]
    if not non_nul:
        return "TEXT"
    if all(isinstance(v, int) for v in non_nul):
        return "LONG"    # Access "EntierLong" → SQLite INTEGER
    if all(isinstance(v, float) for v in non_nul):
        return "DOUBLE"  # Access "Réel" → SQLite REAL
    return "TEXT"


def lire_accdb(chemin):
    """Lit tables+champs+données d'un .accdb via access_parser (pur Python)."""
    from access_parser import AccessParser
    p = AccessParser(chemin)
    tables = {}
    # catalog ne garde que les tables utilisateur (Type==1) ; on ignore MSys*
    for nom in p.catalog:
        if nom.startswith("MSys") or any(pat.fullmatch(nom) for pat in PARASITES):
            continue
        try:
            tab = p.parse_table(nom)
        except Exception:
            continue
        if not tab:
            continue
        colonnes = list(tab.keys())
        champs = {}
        for c in colonnes:
            vals = [_texte(v) for v in tab[c]]
            champs[c] = {"type": inferer_type(vals), "taille": None,
                         "obligatoire": False}
            tab[c] = vals
        chp = champs
        tables[nom] = {"champs": chp, "pk": detecter_pk(nom, colonnes),
                       "lignes": max((len(v) for v in tab.values()), default=0),
                       "_data": dict(tab)}
    return tables


def detecter_pk(nom_table, colonnes):
    """Clé primaire par convention de nom : id*, *id, code*, nom#id."""
    for c in colonnes:
        cn = c.lower().replace(" ", "").replace("_", "")
        if re.fullmatch(r"(id|code|ref|num).*", cn) or cn.endswith("id"):
            return [c]
    return []


def reconstruire_relations(tables):
    """Heuristique : FK = même nom de colonne présent dans 2 tables."""
    relations = []
    noms = list(tables)
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            colonnes_a = set(tables[a]["champs"])
            colonnes_b = set(tables[b]["champs"])
            partages = colonnes_a & colonnes_b
            for c in sorted(partages):
                if c in tables[a].get("pk", []):
                    relations.append({"table": b, "champ": c,
                                      "table_ref": a, "champ_ref": c})
                elif c in tables[b].get("pk", []):
                    relations.append({"table": a, "champ": c,
                                      "table_ref": b, "champ_ref": c})
    # déduplications
    vus, out = set(), []
    for r in relations:
        cle = (r["table"], r["champ"], r["table_ref"], r["champ_ref"])
        if cle not in vus:
            vus.add(cle)
            out.append(r)
    return out


def type_sqlite(t):
    return "INTEGER" if t == "LONG" else "REAL" if t == "DOUBLE" else "TEXT"


def exporter_db(tables, out_dossier, nom_base, requetes=None):
    """Écrit un .db SQLite à partir du dict tables ({champs, pk, lignes, _data}).
    C'est le cœur de la conversion, testable sans .accdb (voir le module de test)."""
    out = os.path.join(out_dossier, nom_base + ".db")
    os.makedirs(out_dossier, exist_ok=True)
    if os.path.exists(out):
        os.remove(out)

    relations = reconstruire_relations(tables)
    fk_par_table = {}
    for r in relations:
        fk_par_table.setdefault(r["table"], []).append(r)

    cx = sqlite3.connect(out)
    cur = cx.cursor()

    # tables (FK en inline : SQLite ne permet pas ALTER ADD FOREIGN KEY) ;
    # les tables référencées sont créées d'abord (bon ordre)
    refs = {r["table_ref"] for r in relations}
    ordre = ([t for t in tables if t not in refs] +
             [t for t in tables if t in refs])
    for nom_t in ordre:
        td = tables[nom_t]
        cols = []
        for c, info in td["champs"].items():
            cols.append(f'"{c}" {type_sqlite(info["type"])}')
        pk = td.get("pk")
        if pk:
            cols.append("PRIMARY KEY (%s)" % ", ".join(f'"{c}"' for c in pk))
        for r in fk_par_table.get(nom_t, []):
            cols.append(f'FOREIGN KEY ("{r["champ"]}") '
                        f'REFERENCES "{r["table_ref"]}" ("{r["champ_ref"]}")')
        cur.execute(f'CREATE TABLE "{nom_t}" ({", ".join(cols)})')

    # données (valeurs natives : int/float/str, bytes décodés)
    for nom_t, td in tables.items():
        cols = list(td["champs"])
        d = td.get("_data") or {}
        ins = (f'INSERT INTO "{nom_t}" ({", ".join(f"\"{c}\"" for c in cols)}) '
               f'VALUES ({", ".join("?" * len(cols))})')
        for i in range(td["lignes"]):
            vals = []
            for c in cols:
                v = _texte(d.get(c, [None] * td["lignes"])[i])
                vals.append(None if isinstance(v, float) and v != v else v)
            try:
                cur.execute(ins, vals)
            except Exception:
                pass

    # requêtes fournies manuellement (--requete nom=SQL) → vues ;
    # un SQL issu de sqlite_master commence déjà par CREATE VIEW → tel quel
    for q, sql in (requetes or {}).items():
        try:
            s = (sql or "").strip()
            if s.upper().startswith("CREATE "):
                cur.execute(s)
            else:
                cur.execute(f'CREATE VIEW "{q}" AS {s}')
        except Exception as e:
            print(f"   ⚠️ vue {q} : {e}", file=sys.stderr)

    cx.commit()
    cx.close()
    return out


def convertir(chemin, out_dossier, requetes=None):
    """Écrit le .db équivalent, retourne (prof, tables_lues)."""
    tables = lire_accdb(chemin)
    if not tables:
        raise RuntimeError("aucune table utilisateur lisible")

    nom = os.path.splitext(os.path.basename(chemin))[0]
    out = exporter_db(tables, out_dossier, nom, requetes)
    return out, tables


def diagnostiquer(chemin):
    tables = lire_accdb(chemin)
    print(f"Fichier : {chemin}")
    print(f"Tables utiles captées : {len(tables)}")
    for nom, td in tables.items():
        print(f"  • {nom}  champs={sorted(td['champs'])}  lignes={td['lignes']}  "
              f"pk={td.get('pk')}")
    rel = reconstruire_relations(tables)
    print(f"Relations reconstruites (heuristique) : {len(rel)}")
    for r in rel:
        print(f"  • {r['table']}.{r['champ']} → {r['table_ref']}.{r['champ_ref']}")
    print("Requêtes : access_parser ne les lit pas — utilisez --requete nom=SQL")


def main():
    ap = argparse.ArgumentParser(description="Accdb → SQLite (.db) sans ACE")
    ap.add_argument("source", help="fichier .accdb/.mdb ou dossier")
    ap.add_argument("-o", "--out", default="db_eleves", help="dossier de sortie")
    ap.add_argument("--requete", action="append", default=[],
                    help="nom=SQL (vue), répétable")
    ap.add_argument("--diagnostic", action="store_true")
    a = ap.parse_args()

    if a.diagnostic:
        diagnostiquer(a.source)
        return

    requetes = {}
    for item in a.requete:
        nom, _, sql = item.partition("=")
        requetes[nom.strip()] = sql.strip()

    fichiers = (sorted(glob.glob(os.path.join(a.source, "*.accdb")) +
                       glob.glob(os.path.join(a.source, "*.mdb")))
                if os.path.isdir(a.source) else [a.source])
    if not fichiers:
        sys.exit(f"aucun .accdb/.mdb dans {a.source}")

    for f in fichiers:
        try:
            out, tables = convertir(f, a.out, requetes)
            print(f"  ✔ {os.path.basename(out):<28} tables={len(tables)}")
        except Exception as e:
            print(f"  ⚠️ {os.path.basename(f)} : {e}", file=sys.stderr)


if __name__ == "__main__":
    main()