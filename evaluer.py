#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluer.py — Évaluer un essai élève ou toute une classe, PDF/Excel/console
==========================================================================
Outil unique d'évaluation qui réutilise le moteur du projet
(correcteur.py + analyseur.py + rapport_excel.py + correcteur_access.py).

Usage :
    # Un seul essai élève (code Python) — affiche la note à l'écran
    python evaluer.py essai_eleve.py -s solution.py -t tests.json

    # Toute une classe (dossier de copies) + rapport Excel
    python evaluer.py classe/ -s solution.py -t tests.json -o rapport.xlsx

    # Une base de données d'élève (Access/SQLite)
    python evaluer.py --bd bd/eleve2_rania.db -s bd/solution.db

    # Toute une classe de bases + rapport Excel
    python evaluer.py --bd bd/classe -s bd/solution.db -o rapport_bd.xlsx

    # Sans solution : analyse de la qualité seule (+ fichier annoté)
    python evaluer.py essai_eleve.py --analyse-seule
"""

import argparse
import glob
import os
import sys

import langues
from langues import U
import analyseur
import correcteur


def evaluer_essai(essai, solution, tests, montrer_solution=False):
    """Évalue une seule copie Python et affiche le rapport détaillé."""
    print(f"\n{'=' * 70}")
    print(f"📄 ÉLÈVE : {os.path.basename(essai)}")
    print(f"{'=' * 70}")
    r = correcteur.corriger(essai, solution, tests)
    correcteur.afficher(r, montrer_solution)
    return r


def evaluer_classe(dossier, solution, tests, out_xlsx=None):
    """Évalue toutes les copies .py d'un dossier et (option) exporte Excel."""
    fichiers = [f for f in sorted(glob.glob(os.path.join(dossier, "*.py")))
                if os.path.realpath(f) != os.path.realpath(solution)]
    if not fichiers:
        print(f"❌ Aucune copie .py trouvée dans {dossier}")
        return []

    resultats = []
    for f in fichiers:
        try:
            r = correcteur.corriger(f, solution, tests)
            resultats.append((os.path.basename(f), f, r))
        except Exception as e:
            print(f"⚠️ {os.path.basename(f)} : {e}", file=sys.stderr)

    # Résumé console
    print(f"\n{'=' * 70}")
    print(f"👥 CLASSE : {dossier}  ({len(resultats)} copies)")
    print(f"{'=' * 70}")
    print(f"{'Copie':<20}{'Note':>8}  {'Mention'}")
    print("-" * 50)
    for nom, _, r in sorted(resultats, key=lambda x: -x[2]["note"]):
        mention = next(m for s, m in langues.mentions() if r["note"] >= s)
        print(f"{nom:<22}{r['note']:>6.2f}/20  {mention.split('—')[0].strip()}")
    notes = [r["note"] for _, _, r in resultats]
    if notes:
        med = sorted(notes)[len(notes) // 2]
        print("-" * 50)
        print(f"n = {len(notes)}   ·   {U('moyenne')} {sum(notes)/len(notes):.2f}/20"
              f"   ·   min {min(notes)}   ·   max {max(notes)}   ·   méd {med}"
              f"   ·   admis ≥10 : {sum(1 for n in notes if n >= 10)}/{len(notes)}")

    if out_xlsx:
        try:
            import rapport_excel
            chemin = rapport_excel.exporter(out_xlsx, resultats, solution,
                                            tests or "", analyseur.PYTHON)
            print(f"\n💾 Rapport Excel : {chemin}")
        except ImportError:
            print("\n⚠️  pip install openpyxl  pour le rapport Excel")
    return resultats


def evaluer_bd(cible, solution, out_xlsx=None, bareme_profil=None):
    """Évalue un fichier BD ou un dossier de BD (Access/SQLite)."""
    import bareme
    import correcteur_access as ca

    if bareme_profil:
        try:
            bareme.charger_profil(bareme_profil)
            print(f"⚖  {bareme.nom()}  ({bareme.chemin()})")
        except FileNotFoundError:
            print(f"⚠️  barème introuvable : {bareme_profil}", file=sys.stderr)
            return []

    cibles = ([f for ext in ("*.accdb", "*.mdb", "*.db", "*.sqlite")
               for f in sorted(glob.glob(os.path.join(cible, ext)))]
              if os.path.isdir(cible) else [cible])
    cibles = [c for c in cibles if os.path.realpath(c) != os.path.realpath(solution)]
    if not cibles:
        print(f"❌ Aucune base trouvée dans {cible}")
        return []

    resultats = []
    print(f"\n{'=' * 70}")
    print(f"🗄 BASES : {cible}  ({len(cibles)} base(s))")
    print(f"{'=' * 70}")
    for c in cibles:
        try:
            r = ca.comparer(c, solution)
            resultats.append((os.path.basename(c), r))
            mention = r["mention"].split("—")[0].strip()
            print(f"{os.path.basename(c):<28}{r['note']:>6.2f}/20  {mention}")
        except Exception as e:
            print(f"⚠️ {os.path.basename(c)} : {e}", file=sys.stderr)
    ca.fermer_connexions()
    notes = [r["note"] for _, r in resultats]
    if notes:
        print("-" * 50)
        print(f"n = {len(notes)}   ·   {U('moyenne')} {sum(notes)/len(notes):.2f}/20"
              f"   ·   min {min(notes)}   ·   max {max(notes)}")

    if out_xlsx:
        try:
            ca.exporter_excel(out_xlsx, resultats, solution)
            print(f"\n💾 Rapport Excel : {out_xlsx}")
        except ImportError:
            print("\n⚠️  pip install openpyxl  pour le rapport Excel")
    return resultats


def analyser_seul(essai):
    """Analyse de qualité sans solution ; produit aussi le fichier annoté."""
    base, ext = os.path.splitext(essai)
    annoted = f"{base}_annote{ext}"
    problemes = analyseur.analyser(essai, annoted, py=analyseur.PYTHON)
    return problemes


def main():
    ap = argparse.ArgumentParser(description="Évaluer un essai ou une classe")
    ap.add_argument("cible", help="fichier .py élève, dossier de copies, "
                                  "fichier/dossier de BD")
    ap.add_argument("-s", "--solution", help="solution.py (ou base de référence)")
    ap.add_argument("-t", "--tests", help="tests.json (optionnel)")
    ap.add_argument("-o", "--out", help="rapport Excel de sortie")
    ap.add_argument("-b", "--bareme", help="fichier barème JSON ou nom de profil "
                                           "(ex. --bareme baremes/access_v2.json)")
    ap.add_argument("--bd", action="store_true",
                    help="cible et solution sont des bases de données")
    ap.add_argument("--analyse-seule", action="store_true",
                    help="pas de solution : note la qualité seule + fichier annoté")
    ap.add_argument("--montrer-solution", action="store_true",
                    help="afficher la solution et le diff après correction")
    ap.add_argument("--lang", choices=list(langues.LANGUES),
                    default=langues.langue(), help="ar | fr | en")
    a = ap.parse_args()
    langues.definir_langue(a.lang)

    if not os.path.exists(a.cible):
        print(f"❌ Introuvable : {a.cible}", file=sys.stderr)
        return 2

    if a.analyse_seule and not a.solution:
        analyser_seul(a.cible)
    elif a.bd:
        if not a.solution:
            ap.error("--bd nécessite -s solution (base de référence)")
        evaluer_bd(a.cible, a.solution, a.out, a.bareme)
    elif a.solution:
        if os.path.isdir(a.cible):
            evaluer_classe(a.cible, a.solution, a.tests, a.out)
        else:
            if a.out:
                import rapport_excel
                r = correcteur.corriger(a.cible, a.solution, a.tests)
                resultats = [(os.path.basename(a.cible), a.cible, r)]
                print("💾 " + rapport_excel.exporter(
                    a.out, resultats, a.solution, a.tests or "", analyseur.PYTHON))
            else:
                evaluer_essai(a.cible, a.solution, a.tests, a.montrer_solution)
    else:
        ap.error("indiquez -s solution, ou --bd, ou --analyse-seule")
    return 0


if __name__ == "__main__":
    sys.exit(main())
