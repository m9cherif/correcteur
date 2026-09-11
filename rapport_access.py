#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rapport_access.py — تصدير تصحيح القسم إلى قاعدة بيانات
=======================================================
نفس بنية تقرير Excel لكن في جداول قاعدة بيانات، مع ثلاث صيغ:

  --mode access   ملف .accdb حقيقي  (ويندوز فقط — يحتاج محرّك Access)
  --mode sqlite   ملف .db محمول     (يعمل في كل مكان، و Access يستطيع ربطه)
  --mode csv      مجلّد CSV + دليل استيراد (يعمل دائمًا، بلا أيّ تثبيت)

الجداول المنتَجة (نفس منطق أوراق Excel):
  Parametres   : التمرين، المفسّر، التاريخ، اللغة
  Eleves       : نقطة كل تلميذ ومحاورها الثلاثة والتقدير
  Tests        : قائمة الاختبارات
  Resultats    : سطر لكل (تلميذ × اختبار) مع المنتظَر والمحصَّل
  Erreurs      : سطر لكل ملاحظة مع سببها وتصحيحها
  Bareme       : سلّم التنقيط

والاستعلامات (Queries / Views) الجاهزة:
  Q_Synthese          المعدّل، الأدنى، الأعلى، عدد الناجحين
  Q_ReussiteParTest   نسبة النجاح لكل اختبار → الدرس الواجب إعادته
  Q_FrequenceErreurs  عدد التلاميذ المعنيّين بكل نوع خطأ
  Q_ElevesEnDifficulte كل من نقطته < 10 مع عدد أخطائه

الاستعمال:
    python rapport_access.py classe/ -s solution.py -t tests.json -o notes.accdb
    python rapport_access.py classe/ -s solution.py --mode sqlite -o notes.db
    python rapport_access.py classe/ -s solution.py --mode csv -o dossier_csv/

ملاحظة مهمّة عن .accdb :
    إنشاء ملف Access حقيقي يتطلّب «Microsoft Access Database Engine» (ACE)
    وهو متوفّر على ويندوز فقط. إن لم يكن مثبَّتًا، استعمل mode sqlite أو csv:
      • csv    → في Access: Données externes ▸ Nouvelle source ▸ Fichier ▸ Texte
      • sqlite → في Access: Données externes ▸ ODBC ▸ pilote SQLite (lien direct)
"""

import argparse
import csv
import datetime
import glob
import os
import shutil
import sqlite3
import sys

import langues
from langues import U
import analyseur
import correcteur

# ---------------------------------------------------------------------------
# مخطّط الجداول — واحد لكل الصيغ (أنواع Access/Jet متوافقة مع SQLite)
# ---------------------------------------------------------------------------
SCHEMA = {
    "Parametres": [("Cle", "TEXT(60)"), ("Valeur", "TEXT(255)")],
    "Eleves": [("IdEleve", "INTEGER"), ("Fichier", "TEXT(120)"), ("Note", "DOUBLE"),
               ("Mention", "TEXT(40)"), ("Qualite", "DOUBLE"), ("Resultats", "DOUBLE"),
               ("Structure", "DOUBLE"), ("TestsReussis", "INTEGER"),
               ("TestsTotal", "INTEGER"), ("VuSolution", "INTEGER")],
    "Tests": [("IdTest", "INTEGER"), ("NomTest", "TEXT(120)")],
    "Resultats": [("IdEleve", "INTEGER"), ("IdTest", "INTEGER"),
                  ("Fichier", "TEXT(120)"), ("NomTest", "TEXT(120)"),
                  ("Reussi", "INTEGER"), ("Attendu", "TEXT(255)"),
                  ("Obtenu", "TEXT(255)")],
    "Erreurs": [("IdEleve", "INTEGER"), ("Fichier", "TEXT(120)"), ("Ligne", "INTEGER"),
                ("Code", "TEXT(10)"), ("Gravite", "TEXT(20)"), ("Message", "TEXT(255)"),
                ("Cause", "TEXT(255)"), ("Correction", "TEXT(255)")],
    "Bareme": [("Code", "TEXT(10)"), ("Regle", "TEXT(120)"), ("Penalite", "DOUBLE"),
               ("Plafond", "DOUBLE")],
}

VUES = {
    "Q_Synthese": """
        SELECT COUNT(*) AS Copies, AVG(Note) AS Moyenne, MIN(Note) AS NoteMin,
               MAX(Note) AS NoteMax, SUM(IIF(Note>=10,1,0)) AS Admis
        FROM Eleves""",
    "Q_ReussiteParTest": """
        SELECT NomTest, COUNT(*) AS Passages, SUM(Reussi) AS Reussites,
               100.0*SUM(Reussi)/COUNT(*) AS TauxPourcent
        FROM Resultats GROUP BY NomTest ORDER BY 100.0*SUM(Reussi)/COUNT(*)""",
    "Q_FrequenceErreurs": """
        SELECT Code, Message, COUNT(*) AS Occurrences,
               COUNT(DISTINCT Fichier) AS ElevesConcernes
        FROM Erreurs GROUP BY Code, Message ORDER BY COUNT(*) DESC""",
    "Q_ElevesEnDifficulte": """
        SELECT e.Fichier, e.Note, e.Mention,
               (SELECT COUNT(*) FROM Erreurs x WHERE x.Fichier = e.Fichier) AS NbErreurs
        FROM Eleves e WHERE e.Note < 10 ORDER BY e.Note""",
}
# SQLite لا يعرف IIF قبل 3.32 ولا COUNT(DISTINCT) في كل الحالات → نسخة مكافئة
VUES_SQLITE = dict(VUES, Q_Synthese="""
        SELECT COUNT(*) AS Copies, AVG(Note) AS Moyenne, MIN(Note) AS NoteMin,
               MAX(Note) AS NoteMax, SUM(CASE WHEN Note>=10 THEN 1 ELSE 0 END) AS Admis
        FROM Eleves""")


# ---------------------------------------------------------------------------
def lignes(resultats, solution="", tests="", python=""):
    """يحوّل تقارير correcteur إلى صفوف جاهزة لكل جدول."""
    resultats = [r for r in resultats if "erreur" not in r[2]]
    noms_tests, data = [], {k: [] for k in SCHEMA}

    data["Parametres"] = [
        ("TP / " + U("solution"), os.path.basename(solution) or "—"),
        ("tests.json", os.path.basename(tests) or "(auto)"),
        (U("c_interp"), python or analyseur.PYTHON),
        ("Date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
        (U("langue_expl"), langues.LANGUES[langues.langue()]),
        ("Copies", str(len(resultats))),
    ]
    data["Bareme"] = [(c, langues.titre(c), u, p)
                      for c, (u, p) in sorted(analyseur.BAREME.items(),
                                              key=lambda x: -x[1][0])]

    for i, (nom, _, r) in enumerate(sorted(resultats, key=lambda x: -x[2]["note"]), 1):
        reussis = sum(1 for t in r["resultats"] if t["reussi"])
        mention = next(m for s, m in langues.mentions() if r["note"] >= s)
        data["Eleves"].append((i, nom, r["note"], mention.split("—")[0].strip(),
                               r["qualite"], r["tests"], r["structure"],
                               reussis, len(r["resultats"]), 0))
        for t in r["resultats"]:
            if t["nom"] not in noms_tests:
                noms_tests.append(t["nom"])
            data["Resultats"].append(
                (i, noms_tests.index(t["nom"]) + 1, nom, t["nom"],
                 1 if t["reussi"] else 0, str(t["attendu"])[:250],
                 str(t["obtenu"])[:250]))
        for p in sorted(r["problemes"], key=lambda x: x.ligne):
            data["Erreurs"].append((i, nom, p.ligne, p.code, p.gravite_txt,
                                    p.message[:250], p.explication[:250],
                                    p.correction[:250]))
    data["Tests"] = [(j, n) for j, n in enumerate(noms_tests, 1)]
    return data


# ---------------------------------------------------------------------------
def _creer(cur, dialecte):
    for table, cols in SCHEMA.items():
        defs = ", ".join(f"[{n}] {t if dialecte == 'access' else _sqlite_type(t)}"
                         for n, t in cols)
        cur.execute(f"CREATE TABLE [{table}] ({defs})")


def _sqlite_type(t):
    return "REAL" if t == "DOUBLE" else "INTEGER" if t == "INTEGER" else "TEXT"


def _remplir(cur, data):
    for table, cols in SCHEMA.items():
        if not data.get(table):
            continue
        q = (f"INSERT INTO [{table}] ({', '.join('[' + c + ']' for c, _ in cols)}) "
             f"VALUES ({', '.join('?' * len(cols))})")
        for ligne in data[table]:
            cur.execute(q, tuple(ligne))


# ---------------------------------------------------------------------------
def exporter_sqlite(chemin, data):
    if os.path.exists(chemin):
        os.remove(chemin)
    cx = sqlite3.connect(chemin)
    cur = cx.cursor()
    _creer(cur, "sqlite")
    _remplir(cur, data)
    for nom, sql in VUES_SQLITE.items():
        cur.execute(f"CREATE VIEW [{nom}] AS {sql}")
    cx.commit()
    cx.close()
    return chemin


def exporter_csv(dossier, data):
    os.makedirs(dossier, exist_ok=True)
    for table, cols in SCHEMA.items():
        with open(os.path.join(dossier, f"{table}.csv"), "w", newline="",
                  encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow([c for c, _ in cols])
            w.writerows(data.get(table, []))
    with open(os.path.join(dossier, "IMPORT_ACCESS.txt"), "w", encoding="utf-8") as f:
        f.write(
            "Importer ces CSV dans Access\n"
            "============================\n"
            "1. Access ▸ Données externes ▸ Nouvelle source de données ▸\n"
            "   À partir d'un fichier ▸ Fichier texte\n"
            "2. Choisir Eleves.csv → Délimité → séparateur « ; » →\n"
            "   cocher « Première ligne contient les noms de champs » → encodage UTF-8\n"
            "3. Répéter pour Tests.csv, Resultats.csv, Erreurs.csv, Bareme.csv,\n"
            "   Parametres.csv\n"
            "4. Relations : Eleves.IdEleve ▸ Resultats.IdEleve et Erreurs.IdEleve ;\n"
            "   Tests.IdTest ▸ Resultats.IdTest\n"
            "5. Requêtes utiles (mode SQL) :\n\n"
            + "\n\n".join(f"-- {n}\n{s.strip()};" for n, s in VUES.items()) + "\n")
    return dossier


def exporter_access(chemin, data):
    """يُنشئ ملف .accdb حقيقيًّا عبر محرّك ACE (ويندوز)."""
    try:
        import pyodbc
    except ImportError:
        raise RuntimeError("pyodbc manquant : pip install pyodbc msaccessdb")

    pilotes = [d for d in pyodbc.drivers() if "Access" in d]
    if not pilotes:
        raise RuntimeError(
            "Aucun pilote Access (ACE) trouvé sur ce système.\n"
            "Installez « Microsoft Access Database Engine 2016 Redistributable »\n"
            "ou utilisez --mode sqlite / --mode csv.")

    if os.path.exists(chemin):
        os.remove(chemin)
    # ملف Access فارغ: عبر msaccessdb أو قالب مجاور
    try:
        import msaccessdb
        msaccessdb.create(chemin)
    except ImportError:
        modele = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "modele_vide.accdb")
        if not os.path.isfile(modele):
            raise RuntimeError("pip install msaccessdb  (ou placez modele_vide.accdb "
                               "à côté du script)")
        shutil.copy(modele, chemin)

    cx = pyodbc.connect(f"DRIVER={{{pilotes[0]}}};DBQ={os.path.abspath(chemin)};")
    cur = cx.cursor()
    _creer(cur, "access")
    _remplir(cur, data)
    for nom, sql in VUES.items():          # في Access تصبح «استعلامات» مسجَّلة
        try:
            cur.execute(f"CREATE VIEW [{nom}] AS {sql}")
        except Exception as e:             # بعض الصيغ لا يقبلها Jet كـ VIEW
            print(f"⚠️ {nom}: {e}", file=sys.stderr)
    cx.commit()
    cx.close()
    return chemin


def exporter(chemin, resultats, mode="sqlite", solution="", tests="", python=""):
    data = lignes(resultats, solution, tests, python)
    if mode == "access":
        return exporter_access(chemin, data)
    if mode == "csv":
        return exporter_csv(chemin, data)
    return exporter_sqlite(chemin, data)


def diagnostic() -> str:
    """يخبر المستخدم بما هو متاح على جهازه."""
    lignes_ = [f"OS : {os.name}"]
    try:
        import pyodbc
        pil = [d for d in pyodbc.drivers() if "Access" in d]
        lignes_.append("pyodbc : ✅   pilotes Access : " + (", ".join(pil) or "❌ aucun"))
    except ImportError:
        lignes_.append("pyodbc : ❌ (pip install pyodbc)")
    try:
        import msaccessdb  # noqa: F401
        lignes_.append("msaccessdb : ✅")
    except ImportError:
        lignes_.append("msaccessdb : ❌ (pip install msaccessdb)")
    lignes_.append("sqlite3 : ✅ (toujours disponible)   csv : ✅")
    return "\n".join(lignes_)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Export Access / SQLite / CSV")
    ap.add_argument("dossier", nargs="?")
    ap.add_argument("-s", "--solution")
    ap.add_argument("-t", "--tests")
    ap.add_argument("-o", "--out", default="notes.db")
    ap.add_argument("--mode", choices=["access", "sqlite", "csv"], default="sqlite")
    ap.add_argument("--lang", choices=list(langues.LANGUES), default=langues.langue())
    ap.add_argument("--diagnostic", action="store_true",
                    help="afficher ce qui est disponible sur cette machine")
    a = ap.parse_args()

    if a.diagnostic:
        print(diagnostic())
        return
    if not a.dossier or not a.solution:
        ap.error("dossier et --solution requis")

    langues.definir_langue(a.lang)
    res = []
    for f in sorted(glob.glob(os.path.join(a.dossier, "*.py"))):
        if os.path.realpath(f) == os.path.realpath(a.solution):
            continue
        try:
            res.append((os.path.basename(f), f,
                        correcteur.corriger(f, a.solution, a.tests)))
        except Exception as e:
            print(f"⚠️ {f}: {e}", file=sys.stderr)

    print(f"✔ {len(res)} copies")
    print("💾 " + exporter(a.out, res, a.mode, a.solution, a.tests or "",
                           analyseur.PYTHON))


if __name__ == "__main__":
    main()
