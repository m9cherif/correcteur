#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
creer_bases.py — يبني قواعد التجربة انطلاقًا من ملفّات sql/
============================================================
    python creer_bases.py            # ينشئ solution.db و classe/*.db

كل ملفّ في sql/ هو نسخة تلميذ مكتوبة بـ SQL عاديّ، فيمكن قراءتها وتعديلها
بمحرّر نصوص، أو لصقها في Access (Créer ▸ Création de requête ▸ Mode SQL)
لإنشاء نفس القواعد بصيغة .accdb.

ملفّات التلاميذ وأخطاؤها المقصودة
  01_sami     : tout correct sauf la requête R3 non créée
  02_rania    : pas de clé primaire, date en texte, champ manquant,
                aucune relation, table en trop, requêtes fausses
  03_khalil   : dates stockées en texte, Note sans clé primaire
  04_ines     : structure parfaite mais 3 requêtes fausses
                (produit cartésien, >= au lieu de >, jointure oubliée)
  05_walid    : table Matiere absente → relations et requête R3 impossibles
  06_nour     : copie parfaite → 20/20
  07_hedi     : champs renommés (Nom_Eleve) et champ Adresse en trop
"""

import os
import sqlite3

ICI = os.path.dirname(os.path.abspath(__file__))
SQL = os.path.join(ICI, "sql")
CLASSE = os.path.join(ICI, "classe")


def construire(fichier_sql, cible):
    if os.path.exists(cible):
        os.remove(cible)
    cx = sqlite3.connect(cible)
    cx.executescript(open(fichier_sql, encoding="utf-8").read())
    cx.commit()
    cx.close()
    return cible


def main():
    os.makedirs(CLASSE, exist_ok=True)
    faits = [construire(os.path.join(SQL, "00_solution.sql"),
                        os.path.join(ICI, "solution.db"))]
    for f in sorted(os.listdir(SQL)):
        if f.endswith(".sql") and not f.startswith("00_"):
            faits.append(construire(os.path.join(SQL, f),
                                    os.path.join(CLASSE, f[:-4] + ".db")))
    for c in faits:
        print("✔", os.path.relpath(c, ICI))
    print("\nCorriger la classe :")
    print("  python correcteur_access.py bd/classe -s bd/solution.db "
          "--excel rapport_bd.xlsx --lang fr")


if __name__ == "__main__":
    main()
