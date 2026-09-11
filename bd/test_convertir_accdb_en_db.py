#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_convertir_accdb_en_db.py — Valide le pipeline accdb→db SANS vrai .accdb
============================================================================
Le moteur ACE/ODBC étant absent, on ne peut pas ouvrir de vrai .accdb rempli
ici. Ce test simule donc la sortie exacte que renvoie lire_accdb()
(access_parser) : un dict tables {champs, pk, lignes, _data}, reconstruit
depuis de vrais .db SQLite (bd/sql/*.sql via creer_bases).

Il vérifie ainsi la moitié SÛRE de la chaîne :

    accdb simulé → exporter_db() → .db → correcteur_access (lecture + note)

Et il met en évidence la limite asymétrique des .accdb réels : les
relations sont reconstruites par heuristique (colonnes partagées) et les
requêtes ne sont pas lues — à confirmer sur les vrais fichiers fournis.

Usage :
    python bd/test_convertir_accdb_en_db.py
"""

import os
import shutil
import sqlite3
import sys
import tempfile

BD = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(BD)
sys.path.insert(0, RACINE)
sys.path.insert(0, BD)

import langues
import correcteur_access as ca
import creer_bases
import convertir_accdb_en_db as conv

SOLUTION_SQL = os.path.join(BD, "sql", "00_solution.sql")
RANIA_SQL = os.path.join(BD, "sql", "02_rania.sql")

tests = []


def verifier(nom, cond, detail=""):
    tests.append((nom, bool(cond), detail))


def moquer_accdb(chemin_db):
    """Reconstruit le format lire_accdb() depuis un .db : types inférés,
    clés par convention, données par colonne."""
    cx = sqlite3.connect(chemin_db)
    cur = cx.cursor()
    tables, requetes = {}, {}
    objets = list(cur.execute("SELECT name, type, sql FROM sqlite_master "
                              "WHERE name NOT LIKE 'sqlite_%'"))
    for nom, typ, sql in objets:
        if typ == "view":
            requetes[nom] = sql
            continue
        if typ != "table":
            continue
        colonnes = [r[1] for r in cur.execute(f'PRAGMA table_info("{nom}")')]
        donnees = {c: [] for c in colonnes}
        nb = 0
        for ligne in cur.execute(f'SELECT * FROM "{nom}"'):
            nb += 1
            for c, v in zip(colonnes, ligne):
                donnees[c].append(None if v is None else v)
        champs = {}
        for c in colonnes:
            champs[c] = {"type": conv.inferer_type(donnees[c]),
                         "taille": None, "obligatoire": False}
        tables[nom] = {"champs": champs, "pk": conv.detecter_pk(nom, colonnes),
                       "lignes": nb, "_data": donnees}
    cx.close()
    return tables, requetes


def main():
    langues.definir_langue("fr")
    tmp = tempfile.mkdtemp(prefix="accdb_test_")
    try:
        # ---- 1. la solution doit être refondue (elle était corrompue) ----
        sol = creer_bases.construire(SOLUTION_SQL, os.path.join(BD, "solution.db"))
        verifier("bd/solution.db régénéré", os.path.getsize(sol) > 0)
        st = ca.lire_sqlite(sol)
        verifier("solution : 3 tables",
                 set(st["tables"]) == {"Eleve", "Matiere", "Note"},
                 str(sorted(st["tables"])))
        verifier("solution : 2 relations", len(st["relations"]) == 2)
        verifier("solution : 3 requêtes", len(st["requetes"]) == 3)

        # ---- 2. accdb simulé = solution, conversion fidèle ----
        sol_t, sol_q = moquer_accdb(sol)
        outre_sol = conv.exporter_db(sol_t, tmp, "solution_convertie", sol_q)
        cvt = ca.lire_sqlite(outre_sol)
        verifier("convertie : mêmes tables",
                 set(cvt["tables"]) == set(st["tables"]))
        verifier("convertie : mêmes colonnes",
                 all(sorted(t["champs"]) == sorted(st["tables"][n]["champs"])
                     for n, t in cvt["tables"].items()))
        verifier("convertie : pk préservés",
                 all(sorted(t["pk"]) == sorted(st["tables"][n]["pk"])
                     for n, t in cvt["tables"].items()))
        verifier("convertie : 2 relations (reconstruites)",
                 len(cvt["relations"]) == 2)
        verifier("convertie : 3 requêtes (fournies)",
                 len(cvt["requetes"]) == 3)

        cx_s = sqlite3.connect(sol)
        cx_c = sqlite3.connect(outre_sol)
        egal_donnees = all(
            list(cx_s.execute(f'SELECT * FROM "{t}" ORDER BY 1')) ==
            list(cx_c.execute(f'SELECT * FROM "{t}" ORDER BY 1'))
            for t in st["tables"])
        cx_s.close()
        cx_c.close()
        verifier("convertie : mêmes données", egal_donnees)

        # ---- 3. copie parfaite sur le pipeline complet → 20/20 ----
        r_ok = ca.comparer(outre_sol, outre_sol)
        verifier("copie parfaite = 20/20", r_ok["note"] == 20.00, str(r_ok["note"]))
        verifier("parfaite : aucun écart", not r_ok["ecarts"])

        # ---- 4. élève fautif (02_rania) : conversion + correction ----
        rania = creer_bases.construire(RANIA_SQL, os.path.join(tmp, "rania.db"))
        rania_t, rania_q = moquer_accdb(rania)
        outre_rania = conv.exporter_db(rania_t, tmp, "rania_convertie", rania_q)
        r_e = ca.comparer(outre_rania, outre_sol)

        # référence directe (sans conversion) pour comparer les deux notes
        r_ref = ca.comparer(rania, sol)
        verifier("rania convertie : note < 20 (erreurs préservées)",
                 r_e["note"] < 20.00, str(r_e["note"]))
        codes = {e.code for e in r_e["ecarts"]}
        verifier("rania : écarts attendus présents",
                 not codes.isdisjoint({"C001", "T002", "Q002"}),
                 ", ".join(sorted(codes)))

        print(f"   note 02_rania  directe     : {r_ref['note']:>5}/20")
        print(f"   note 02_rania  après conv. : {r_e['note']:>5}/20")
        print("   (écart = biais de la conversion simulée : relations/PK")
        print("    reconstruites par heuristique au lieu d'être absentes)")

        # ---- 5. tests unitaires ciblés ----
        verifier("detecter_pk : IdEleve",
                 conv.detecter_pk("Eleve", ["IdEleve", "Nom", "Prenom"]) == ["IdEleve"])
        verifier("detecter_pk : code_matiere",
                 conv.detecter_pk("Matiere", ["libelle", "code_matiere"]) == ["code_matiere"])
        verifier("detecter_pk : aucune convention",
                 conv.detecter_pk("T", ["nom", "prenom"]) == [])
        rel_test = conv.reconstruire_relations({
            "A": {"champs": {"Id": {}, "Nom": {}}, "pk": ["Id"]},
            "B": {"champs": {"Id": {}, "Valeur": {}}, "pk": []}})
        verifier("relations : colonne partagée → FK",
                 rel_test == [{"table": "B", "champ": "Id",
                               "table_ref": "A", "champ_ref": "Id"}])
        verifier("relations : aucune partage → aucune FK",
                 conv.reconstruire_relations({
                     "A": {"champs": {"Id": {}}, "pk": ["Id"]},
                     "B": {"champs": {"X": {}}, "pk": []}}) == [])
        verifier("inferer_type : entiers → LONG", conv.inferer_type([1, 2]) == "LONG")
        verifier("inferer_type : flottants → DOUBLE",
                 conv.inferer_type([1.5, 2.0]) == "DOUBLE")
        verifier("inferer_type : texte → TEXT", conv.inferer_type(["a"]) == "TEXT")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 70)
    ech = 0
    for nom, ok, detail in tests:
        print(("  ✔ " if ok else "  ✗ ") + nom + (("   [" + detail + "]") if detail else ""))
        ech += 0 if ok else 1
    print("=" * 70)
    print(f"Résumé : {len(tests) - ech}/{len(tests)} vérifications OK")
    print("\nLimites des vrais .accdb (à confirmer sur vos fichiers) :")
    print("  • les requêtes ne sont PAS lues → à fournir via --requete nom=SQL")
    print("  • les relations sont RECONSTRUITES par heuristique (colonnes")
    print("    partagées) → peut masquer des relations réellement absentes")
    print("  • les types sont INFÉRÉS des valeurs → symétrique entre solution")
    print("    et copie, mais ne reflète pas la déclaration Access exacte")
    return 1 if ech else 0


if __name__ == "__main__":
    sys.exit(main())