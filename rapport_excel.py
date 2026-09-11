#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rapport_excel.py — تقرير Excel متعدّد الأوراق لتصحيح قسم كامل
==============================================================
    pip install openpyxl

    import rapport_excel
    rapport_excel.exporter("notes.xlsx", resultats, solution="solution.py")
    # resultats : [(nom_fichier, chemin, rapport_correcteur), ...]

أو من سطر الأوامر (يصحّح المجلّد ثمّ يكتب الملف):
    python rapport_excel.py classe/ -s solution.py -t tests.json -o notes.xlsx

الأوراق المنتَجة
  1. Synthèse    : عنوان التمرين، المفسّر، التاريخ، المعدّل، أفضل/أضعف نقطة (بصيغ حيّة)
  2. Notes       : سطر لكل تلميذ — النقطة، التقدير، المحاور الثلاثة، عدد الاختبارات
  3. Tests       : مصفوفة تلميذ × اختبار (✔/�’) لمعرفة أيّ سؤال أسقط القسم
  4. Détail tests: كل اختبار فاشل مع المنتظَر والمحصَّل
  5. Erreurs     : كل ملاحظة مع سطرها وسببها وتصحيحها (قابلة للفرز والتصفية)
  6. Fréquences  : عدد التلاميذ المعنيّين بكل نوع خطأ → ما يجب إعادة شرحه
  7. Barème      : سلّم التنقيط المستعمَل

كل الأعمدة المحسوبة تُكتب كصيغ Excel حيّة (AVERAGE, COUNTIF, SUM…)،
فتتحدّث تلقائيًّا إن عدّل الأستاذ نقطة يدويًّا.
"""

import argparse
import datetime
import glob
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

import langues
from langues import U
import analyseur
import correcteur

POLICE = "Arial"
TITRE = Font(name=POLICE, size=14, bold=True, color="1F3864")
ENTETE = Font(name=POLICE, size=11, bold=True, color="FFFFFF")
NORMAL = Font(name=POLICE, size=11)
GRAS = Font(name=POLICE, size=11, bold=True)
FOND_ENTETE = PatternFill("solid", fgColor="1F3864")
FOND_OK = PatternFill("solid", fgColor="E2F0D9")
FOND_MOY = PatternFill("solid", fgColor="FFF2CC")
FOND_KO = PatternFill("solid", fgColor="FBE5D6")
CADRE = Border(*[Side(style="thin", color="BFBFBF")] * 4)
CENTRE = Alignment(horizontal="center", vertical="center")
GAUCHE = Alignment(horizontal="left", vertical="center", wrap_text=True)


def _entete(ws, titres, ligne=1):
    for j, t in enumerate(titres, 1):
        c = ws.cell(ligne, j, t)
        c.font = ENTETE
        c.fill = FOND_ENTETE
        c.alignment = CENTRE
        c.border = CADRE
    ws.freeze_panes = ws.cell(ligne + 1, 1)


def _largeurs(ws, largeurs):
    for j, l in enumerate(largeurs, 1):
        ws.column_dimensions[get_column_letter(j)].width = l


def _tableau(ws, nom, nb_lignes, nb_cols, ligne_entete=1):
    if nb_lignes < 1:
        return
    ref = (f"A{ligne_entete}:{get_column_letter(nb_cols)}"
           f"{ligne_entete + nb_lignes}")
    t = Table(displayName=nom, ref=ref)
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    ws.add_table(t)


# ---------------------------------------------------------------------------
def exporter(chemin_xlsx, resultats, solution="", tests="", python=""):
    """resultats : [(nom, chemin_fichier, rapport), ...] من correcteur.corriger"""
    resultats = [r for r in resultats if "erreur" not in r[2]]
    n = len(resultats)
    wb = Workbook()

    # ---------- 2. Notes (تُبنى أوّلًا لأنّ بقيّة الأوراق تشير إليها) ----------
    ws = wb.active
    ws.title = "Notes"
    _entete(ws, ["#", U("fichier"), U("note") + " /20", U("c_mention"),
                 U("col_q") + " /6", U("col_r") + " /10", U("col_s") + " /4",
                 U("tests"), "Tests /9"])
    _largeurs(ws, [5, 26, 11, 16, 11, 13, 12, 10, 10])
    for i, (nom, _, r) in enumerate(sorted(resultats, key=lambda x: -x[2]["note"]), 2):
        reussis = sum(1 for t in r["resultats"] if t["reussi"])
        mention = next(m for s, m in langues.mentions() if r["note"] >= s)
        vals = [i - 1, nom, r["note"], mention.split("—")[0].strip(),
                r["qualite"], r["tests"], r["structure"],
                f"{reussis}/{len(r['resultats'])}", reussis]
        for j, v in enumerate(vals, 1):
            c = ws.cell(i, j, v)
            c.font = GRAS if j == 3 else NORMAL
            c.alignment = GAUCHE if j == 2 else CENTRE
            c.border = CADRE
            if j == 3:
                c.number_format = "0.00"
                c.fill = (FOND_OK if r["note"] >= 14 else
                          FOND_MOY if r["note"] >= 10 else FOND_KO)
    _tableau(ws, "TableNotes", n, 9)

    # ---------- 1. Synthèse ----------
    syn = wb.create_sheet("Synthèse", 0)
    syn.sheet_view.showGridLines = False
    _largeurs(syn, [34, 26, 22])
    syn["A1"] = "📊 " + U("bt_corriger") + " — " + U("tab_lot")
    syn["A1"].font = TITRE
    infos = [("TP / " + U("solution"), os.path.basename(solution) or "—"),
             ("tests.json", os.path.basename(tests) or "(auto)"),
             (U("c_interp"), os.path.basename(python or analyseur.PYTHON)),
             ("Date", datetime.datetime.now().strftime("%d/%m/%Y %H:%M")),
             (U("langue_expl"), langues.LANGUES[langues.langue()])]
    for i, (k, v) in enumerate(infos, 3):
        syn.cell(i, 1, k).font = GRAS
        syn.cell(i, 2, v).font = NORMAL

    syn["A9"] = U("moyenne") + " / " + U("reussite")
    syn["A9"].font = TITRE
    stats = [("Nombre de copies", f"=COUNT(Notes!C2:C{n + 1})", "0"),
             (U("moyenne") + " /20", f"=IFERROR(AVERAGE(Notes!C2:C{n + 1}),0)", "0.00"),
             ("Médiane", f"=IFERROR(MEDIAN(Notes!C2:C{n + 1}),0)", "0.00"),
             ("Écart-type", f"=IFERROR(STDEV(Notes!C2:C{n + 1}),0)", "0.00"),
             ("Note minimale", f"=IFERROR(MIN(Notes!C2:C{n + 1}),0)", "0.00"),
             ("Note maximale", f"=IFERROR(MAX(Notes!C2:C{n + 1}),0)", "0.00"),
             (U("reussite") + " (≥10)", f'=COUNTIF(Notes!C2:C{n + 1},">=10")', "0"),
             ("Taux de réussite",
              f'=IFERROR(COUNTIF(Notes!C2:C{n + 1},">=10")/COUNT(Notes!C2:C{n + 1}),0)',
              "0.0%"),
             (U("ax_qualite") + " (moy.)", f"=IFERROR(AVERAGE(Notes!E2:E{n + 1}),0)", "0.00"),
             (U("ax_tests") + " (moy.)", f"=IFERROR(AVERAGE(Notes!F2:F{n + 1}),0)", "0.00"),
             (U("ax_structure") + " (moy.)", f"=IFERROR(AVERAGE(Notes!G2:G{n + 1}),0)", "0.00")]
    for i, (k, f, fmt) in enumerate(stats, 10):
        syn.cell(i, 1, k).font = GRAS
        c = syn.cell(i, 2, f)
        c.font = NORMAL
        c.number_format = fmt
        c.alignment = CENTRE

    syn["A22"] = "Répartition par tranche"
    syn["A22"].font = TITRE
    tranches = [("[16 – 20]", 16, 20), ("[14 – 16[", 14, 16), ("[12 – 14[", 12, 14),
                ("[10 – 12[", 10, 12), ("[0 – 10[", 0, 10)]
    syn.cell(23, 1, "Tranche").font = ENTETE
    syn.cell(23, 1).fill = FOND_ENTETE
    syn.cell(23, 2, "Effectif").font = ENTETE
    syn.cell(23, 2).fill = FOND_ENTETE
    for i, (lib, bas, haut) in enumerate(tranches, 24):
        syn.cell(i, 1, lib).font = NORMAL
        c = syn.cell(i, 2,
                     f'=COUNTIFS(Notes!C2:C{n + 1},">={bas}",Notes!C2:C{n + 1},'
                     f'"{"<=" if haut == 20 else "<"}{haut}")')
        c.font = NORMAL
        c.alignment = CENTRE
    syn.cell(29, 1, "Total").font = GRAS
    syn.cell(29, 2, "=SUM(B24:B28)").font = GRAS
    syn.cell(29, 2).alignment = CENTRE
    syn["A31"] = ("Les cellules bleues de la feuille Notes peuvent être modifiées à la "
                  "main : toutes les statistiques ci-dessus se recalculent.")
    syn["A31"].font = Font(name=POLICE, size=9, italic=True, color="808080")

    # ---------- 3. Tests (مصفوفة) ----------
    noms_tests = [t["nom"] for t in resultats[0][2]["resultats"]] if resultats else []
    wt = wb.create_sheet("Tests")
    _entete(wt, [U("fichier")] + noms_tests + ["Total"])
    _largeurs(wt, [26] + [17] * len(noms_tests) + [9])
    for i, (nom, _, r) in enumerate(resultats, 2):
        wt.cell(i, 1, nom).font = NORMAL
        wt.cell(i, 1).border = CADRE
        for j, t in enumerate(r["resultats"], 2):
            c = wt.cell(i, j, 1 if t["reussi"] else 0)
            c.alignment = CENTRE
            c.border = CADRE
            c.fill = FOND_OK if t["reussi"] else FOND_KO
        d = get_column_letter(2)
        f = get_column_letter(1 + len(noms_tests))
        wt.cell(i, 2 + len(noms_tests), f"=SUM({d}{i}:{f}{i})").font = GRAS
        wt.cell(i, 2 + len(noms_tests)).alignment = CENTRE
    if resultats:
        lig = len(resultats) + 2
        wt.cell(lig, 1, "Réussite par test").font = GRAS
        for j in range(2, 2 + len(noms_tests)):
            col = get_column_letter(j)
            c = wt.cell(lig, j, f"=IFERROR(AVERAGE({col}2:{col}{lig - 1}),0)")
            c.number_format = "0%"
            c.font = GRAS
            c.alignment = CENTRE
        wt.cell(lig + 1, 1, "1 = réussi · 0 = échoué — la ligne « Réussite par test » "
                            "montre la question qui a posé problème à la classe"
                ).font = Font(name=POLICE, size=9, italic=True, color="808080")

    # ---------- 4. Détail tests ----------
    wd = wb.create_sheet("Détail tests")
    _entete(wd, [U("fichier"), U("tests"), "OK", U("attendu"), U("obtenu")])
    _largeurs(wd, [24, 30, 7, 30, 46])
    i = 2
    for nom, _, r in resultats:
        for t in r["resultats"]:
            if t["reussi"]:
                continue
            for j, v in enumerate((nom, t["nom"], "✗", str(t["attendu"])[:200],
                                   str(t["obtenu"])[:200]), 1):
                c = wd.cell(i, j, v)
                c.font = NORMAL
                c.alignment = CENTRE if j == 3 else GAUCHE
                c.border = CADRE
            i += 1
    _tableau(wd, "TableDetail", i - 2, 5)

    # ---------- 5. Erreurs ----------
    we = wb.create_sheet("Erreurs")
    _entete(we, [U("fichier"), U("ligne"), "Code", U("erreur") + "/" + U("avertissement"),
                 U("c_regle"), U("cause"), U("fix")])
    _largeurs(we, [22, 8, 9, 13, 40, 56, 50])
    i = 2
    freq = {}
    for nom, _, r in resultats:
        for p in sorted(r["problemes"], key=lambda x: x.ligne):
            freq.setdefault(p.code, {"n": 0, "eleves": set(), "lib": p.message})
            freq[p.code]["n"] += 1
            freq[p.code]["eleves"].add(nom)
            for j, v in enumerate((nom, p.ligne, p.code, p.gravite_txt, p.message,
                                   p.explication, p.correction), 1):
                c = we.cell(i, j, v)
                c.font = NORMAL
                c.alignment = CENTRE if j in (2, 3, 4) else GAUCHE
                c.border = CADRE
                if j == 4:
                    c.fill = FOND_KO if p.gravite == analyseur.ERREUR else FOND_MOY
            i += 1
    _tableau(we, "TableErreurs", i - 2, 7)

    # ---------- 6. Fréquences ----------
    wf = wb.create_sheet("Fréquences")
    _entete(wf, ["Code", U("c_regle"), "Occurrences", "Élèves concernés",
                 "% de la classe", "Pénalité unitaire", "Plafond"])
    _largeurs(wf, [9, 44, 13, 17, 15, 17, 10])
    for i, (code, d) in enumerate(sorted(freq.items(), key=lambda x: -len(x[1]["eleves"])), 2):
        unite, plafond = analyseur.BAREME.get(code, (0, 0))
        vals = [code, langues.titre(code), d["n"], len(d["eleves"]),
                f"=IFERROR(D{i}/{max(n, 1)},0)", unite, plafond]
        for j, v in enumerate(vals, 1):
            c = wf.cell(i, j, v)
            c.font = NORMAL
            c.alignment = GAUCHE if j == 2 else CENTRE
            c.border = CADRE
            if j == 5:
                c.number_format = "0%"
    wf.cell(len(freq) + 3, 1,
            "Trié par nombre d'élèves : la première ligne est la notion à réexpliquer."
            ).font = Font(name=POLICE, size=9, italic=True, color="808080")
    _tableau(wf, "TableFreq", len(freq), 7)

    # ---------- 7. Barème ----------
    wb_ = wb.create_sheet("Barème")
    _entete(wb_, ["Code", U("c_regle"), U("c_unite"), U("c_plafond")])
    _largeurs(wb_, [9, 48, 14, 12])
    for i, (code, (unite, plafond)) in enumerate(
            sorted(analyseur.BAREME.items(), key=lambda x: -x[1][0]), 2):
        for j, v in enumerate((code, langues.titre(code), unite, plafond), 1):
            c = wb_.cell(i, j, v)
            c.font = NORMAL
            c.alignment = GAUCHE if j == 2 else CENTRE
            c.border = CADRE
    lig = len(analyseur.BAREME) + 3
    wb_.cell(lig, 1, f"{U('ax_qualite')} : 6 · {U('ax_tests')} : 10 · "
                     f"{U('ax_structure')} : 4 → 20").font = GRAS
    wb_.cell(lig + 1, 1, U("note_bas")).font = Font(name=POLICE, size=9, italic=True,
                                                    color="808080")
    _tableau(wb_, "TableBareme", len(analyseur.BAREME), 4)

    wb.save(chemin_xlsx)
    return chemin_xlsx


# ---------------------------------------------------------------------------
def corriger_dossier(dossier, solution, tests=None):
    out = []
    for f in sorted(glob.glob(os.path.join(dossier, "*.py"))):
        if os.path.realpath(f) == os.path.realpath(solution):
            continue
        try:
            out.append((os.path.basename(f), f, correcteur.corriger(f, solution, tests)))
        except Exception as e:
            print(f"⚠️ {f}: {e}", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description="Rapport Excel d'une classe")
    ap.add_argument("dossier")
    ap.add_argument("-s", "--solution", required=True)
    ap.add_argument("-t", "--tests")
    ap.add_argument("-o", "--out", default="notes.xlsx")
    ap.add_argument("--lang", choices=list(langues.LANGUES), default=langues.langue())
    a = ap.parse_args()
    langues.definir_langue(a.lang)

    res = corriger_dossier(a.dossier, a.solution, a.tests)
    print(f"✔ {len(res)} copies")
    print("💾 " + exporter(a.out, res, a.solution, a.tests or "", analyseur.PYTHON))


if __name__ == "__main__":
    main()
