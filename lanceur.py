#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lanceur.py — الواجهة الرسومية الرئيسية (PyQt5)
==============================================
نافذة واحدة تُغني عن سطر الأوامر تمامًا:

  1. تبويب «الإعداد»   : اختيار python.exe المكتشَف تلقائيًّا، لغة الشرح،
                          ملفّات التمرين (الحلّ، الاختبارات، النصّ، مجلّد المحاولات)،
                          ثم فتح محرّر التلميذ.
  2. تبويب «تصحيح القسم»: اختيار مجلّد يحوي محاولات التلاميذ، تصحيحها كلّها
                          في الخلفية مع شريط تقدّم، جدول نقاط قابل للفرز،
                          تصدير CSV، ونقر مزدوج يفتح المحاولة في المحرّر.

    pip install PyQt5
    python lanceur.py
"""

import csv
import glob
import os
import sys

try:
    from PyQt5.QtCore import Qt, QSettings, QThread, pyqtSignal
    from PyQt5.QtGui import QColor, QFont
    from PyQt5.QtWidgets import (QApplication, QComboBox, QFileDialog, QFormLayout,
                                 QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                                 QLineEdit, QMainWindow, QMessageBox, QProgressBar,
                                 QPushButton, QTabWidget, QTableWidget,
                                 QTableWidgetItem, QVBoxLayout, QWidget)
except ImportError:
    sys.exit("PyQt5 غير مثبَّت — نفّذ:  pip install PyQt5")

import langues
from langues import U
import analyseur
import correcteur
import interpreteurs as itp
import ide_qt


# ---------------------------------------------------------------------------
class Lot(QThread):
    """تصحيح مجلّد كامل في الخلفية."""
    avance = pyqtSignal(int, int, str)
    ligne = pyqtSignal(str, object)
    fini = pyqtSignal()

    def __init__(self, fichiers, solution, tests):
        super().__init__()
        self.fichiers, self.solution, self.tests = fichiers, solution, tests

    def run(self):
        for i, f in enumerate(self.fichiers, 1):
            self.avance.emit(i, len(self.fichiers), os.path.basename(f))
            try:
                self.ligne.emit(f, correcteur.corriger(f, self.solution, self.tests))
            except Exception as e:
                self.ligne.emit(f, {"erreur": f"{type(e).__name__}: {e}"})
        self.fini.emit()


# ---------------------------------------------------------------------------
class Lanceur(QMainWindow):
    def __init__(self):
        super().__init__()
        self.reg = QSettings("ecole", "lanceur")
        self.editeurs = []
        self.resultats = []
        self.setWindowTitle("🐍 " + U("titre_app"))
        self.resize(980, 620)
        self.setStyleSheet(ide_qt.SOMBRE)  # يُعاد ضبطه في basculer_theme

        self.sombre = self.reg.value("sombre", True, type=bool)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.page_config(), "⚙ " + U("tab_config"))
        self.tabs.addTab(self.page_lot(), "📚 " + U("tab_lot"))
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage("🐍 " + itp.info(CFG_PY()).get("etiquette", ""))
        self.scanner()

    # ---------------- تبويب الإعداد ----------------
    def page_config(self):
        w = QWidget()
        v = QVBoxLayout(w)

        g1 = QGroupBox("🐍 " + U("interp_actif"))
        f1 = QFormLayout(g1)
        self.combo_py = QComboBox()
        self.combo_py.currentIndexChanged.connect(self.appliquer_py)
        ligne = QHBoxLayout()
        ligne.addWidget(self.combo_py, 1)
        b = QPushButton("…")
        b.setMaximumWidth(44)
        b.clicked.connect(self.parcourir_py)
        ligne.addWidget(b)
        b2 = QPushButton("⟳")
        b2.setMaximumWidth(44)
        b2.clicked.connect(lambda: self.scanner(True))
        ligne.addWidget(b2)
        cadre = QWidget()
        cadre.setLayout(ligne)
        f1.addRow(QLabel(U("sous_interp"), objectName="sous"))
        f1.addRow(U("c_interp"), cadre)
        self.lbl_py = QLabel("—")
        f1.addRow("", self.lbl_py)
        v.addWidget(g1)

        g2 = QGroupBox("🗣 " + U("langue_expl"))
        f2 = QFormLayout(g2)
        f2.addRow(QLabel(U("sous_langue"), objectName="sous"))
        self.combo_lg = QComboBox()
        for c, n in langues.LANGUES.items():
            self.combo_lg.addItem(n, c)
        self.combo_lg.setCurrentIndex(list(langues.LANGUES).index(langues.langue()))
        self.combo_lg.currentIndexChanged.connect(
            lambda: langues.definir_langue(self.combo_lg.currentData()))
        f2.addRow(U("langue_expl"), self.combo_lg)
        v.addWidget(g2)

        g3 = QGroupBox("📘 " + U("tab_enonce"))
        f3 = QFormLayout(g3)
        f3.addRow(QLabel(U("sous_exo"), objectName="sous"))
        self.champs = {}
        for cle, titre, filtre in (
                ("solution", U("solution"), "Python (*.py)"),
                ("tests", "tests.json", "JSON (*.json)"),
                ("enonce", U("tab_enonce"), "Texte (*.txt *.md)"),
                ("essais", U("tab_hist"), "")):
            e = QLineEdit(self.reg.value(cle, "", type=str))
            bp = QPushButton("📂")
            bp.setMaximumWidth(44)
            bp.clicked.connect(lambda _, k=cle, ft=filtre: self.choisir(k, ft))
            h = QHBoxLayout()
            h.addWidget(e, 1)
            h.addWidget(bp)
            c = QWidget()
            c.setLayout(h)
            self.champs[cle] = e
            f3.addRow(titre, c)
        v.addWidget(g3)

        h = QHBoxLayout()
        b_ed = QPushButton("✏ " + U("titre_app").replace("&", "&&"))
        b_ed.setObjectName("p")
        b_ed.clicked.connect(self.ouvrir_editeur)
        b_of = QPushButton("📂 " + U("bt_ouvrir"))
        b_of.clicked.connect(self.ouvrir_fichier)
        b_demo = QPushButton("🚀 " + U("bt_demo"))
        b_demo.clicked.connect(self.charger_demo)
        b_th = QPushButton("🌗")
        b_th.setMaximumWidth(52)
        b_th.clicked.connect(self.basculer_theme)
        h.addWidget(b_ed)
        h.addWidget(b_of)
        h.addWidget(b_demo)
        h.addWidget(b_th)
        h.addStretch()
        v.addLayout(h)
        v.addStretch()
        return w

    def choisir(self, cle, filtre):
        if cle == "essais":
            p = QFileDialog.getExistingDirectory(self, U("tab_hist"))
        else:
            p, _ = QFileDialog.getOpenFileName(self, cle, "", filtre)
        if p:
            self.champs[cle].setText(p)
            self.reg.setValue(cle, p)

    def scanner(self, forcer=False):
        self.combo_py.blockSignals(True)
        self.combo_py.clear()
        for d in itp.scanner(forcer):
            self.combo_py.addItem(d["etiquette"], d["chemin"])
        if self.combo_py.count() == 0:
            self.combo_py.addItem(sys.executable, sys.executable)
        self.combo_py.blockSignals(False)
        self.appliquer_py()

    def parcourir_py(self):
        filtre = "python.exe (python*.exe)" if os.name == "nt" else "python (python*)"
        f, _ = QFileDialog.getOpenFileName(self, U("bt_parcourir"), "", filtre)
        if not f:
            return
        v = itp.valider(f)
        if not v.get("ok"):
            QMessageBox.warning(self, "⛔", U("interp_ko"))
            return
        self.combo_py.insertItem(0, v["etiquette"], v["chemin"])
        self.combo_py.setCurrentIndex(0)

    def appliquer_py(self):
        chemin = self.combo_py.currentData() or sys.executable
        d = itp.info(chemin)
        analyseur.PYTHON = correcteur.PYTHON = chemin
        ide_qt.CFG["python"] = chemin
        self.lbl_py.setText(
            f"{chemin}   ·   {d.get('impl','?')} {d.get('version','?')} "
            f"{d.get('bits','?')}-bit   ·   pip: {'✅' if d.get('pip') else '❌'}"
            f"   ·   PyQt5: {'✅' if d.get('pyqt5') else '❌'}"
            f"{'   ·   venv' if d.get('venv') else ''}")
        self.statusBar().showMessage("🐍 " + d.get("etiquette", chemin))

    def basculer_theme(self):
        self.sombre = not self.sombre
        self.reg.setValue("sombre", self.sombre)
        self.setStyleSheet(ide_qt.SOMBRE if self.sombre else ide_qt.CLAIR)

    def charger_demo(self):
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exemples")
        paires = {"solution": "solution.py", "tests": "tests.json",
                  "enonce": "enonce.txt"}
        for k, f in paires.items():
            c = os.path.join(base, f)
            if os.path.isfile(c):
                self.champs[k].setText(c)
                self.reg.setValue(k, c)
        self.champs["essais"].setText(os.path.join(base, "essais"))
        cl = os.path.join(base, "classe")
        if os.path.isdir(cl):
            self.dossier.setText(cl)
            self.reg.setValue("dossier", cl)
        self.statusBar().showMessage("🚀 " + base, 5000)

    def config(self):
        c = {k: (e.text().strip() or None) for k, e in self.champs.items()}
        ide_qt.CFG.update(solution=c["solution"], tests=c["tests"],
                          essais=c["essais"] or "essais",
                          python=self.combo_py.currentData() or sys.executable)
        ide_qt.CFG["enonce"] = (open(c["enonce"], encoding="utf-8").read()
                                if c["enonce"] and os.path.isfile(c["enonce"]) else "")
        return c

    def ouvrir_editeur(self, source=None):
        self.config()
        f = ide_qt.Fenetre()
        if source:
            f.ed.setPlainText(source)
            f.analyser()
        f.show()
        self.editeurs.append(f)

    def ouvrir_fichier(self):
        f, _ = QFileDialog.getOpenFileName(self, U("bt_ouvrir"), "", "Python (*.py)")
        if f:
            self.ouvrir_editeur(open(f, encoding="utf-8").read())

    # ---------------- تبويب تصحيح القسم ----------------
    def page_lot(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel(U("sous_lot"), objectName="sous"))
        h = QHBoxLayout()
        self.dossier = QLineEdit(self.reg.value("dossier", "", type=str))
        bp = QPushButton("📂")
        bp.setMaximumWidth(44)
        bp.clicked.connect(self.choisir_dossier)
        self.b_lot = QPushButton("▶ " + U("bt_corriger").replace("&", "&&"))
        self.b_lot.setObjectName("p")
        self.b_lot.clicked.connect(self.lancer_lot)
        b_csv = QPushButton("⬇ CSV")
        b_csv.clicked.connect(self.exporter_csv)
        b_xl = QPushButton("📊 Excel")
        b_xl.clicked.connect(self.exporter_excel)
        for x in (QLabel("📁 " + U("dossier")), self.dossier, bp, self.b_lot,
                  b_csv, b_xl):
            h.addWidget(x, 1 if x is self.dossier else 0)
        v.addLayout(h)

        self.barre = QProgressBar()
        self.barre.setTextVisible(True)
        v.addWidget(self.barre)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [U("c_num"), U("fichier"), U("note") + " /20", U("c_mention"),
             U("col_q") + " /6", U("col_r") + " /10", U("col_s") + " /4",
             U("tests")])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        en = self.table.horizontalHeader()
        for j in (0, 2, 3, 4, 5, 6, 7):
            en.setSectionResizeMode(j, QHeaderView.ResizeToContents)
        en.setSectionResizeMode(1, QHeaderView.Stretch)
        en.setMinimumSectionSize(60)
        self.table.setColumnWidth(1, 220)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self.ouvrir_copie)
        v.addWidget(self.table, 1)

        self.lbl_stat = QLabel("—")
        v.addWidget(self.lbl_stat)
        return w

    def choisir_dossier(self):
        d = QFileDialog.getExistingDirectory(self, "📁")
        if d:
            self.dossier.setText(d)
            self.reg.setValue("dossier", d)

    def lancer_lot(self):
        c = self.config()
        if not c["solution"]:
            QMessageBox.warning(self, "⛔", U("msg_no_sol"))
            return
        fichiers = sorted(glob.glob(os.path.join(self.dossier.text(), "*.py")))
        fichiers = [f for f in fichiers
                    if os.path.realpath(f) != os.path.realpath(c["solution"])]
        if not fichiers:
            QMessageBox.information(self, "—", "*.py : 0")
            return
        self.table.setRowCount(0)
        self.resultats = []
        self.barre.setMaximum(len(fichiers))
        self.b_lot.setEnabled(False)
        self.lot = Lot(fichiers, c["solution"], c["tests"])
        self.lot.avance.connect(lambda i, n, nom: (
            self.barre.setValue(i), self.barre.setFormat(f"{i}/{n} — {nom}")))
        self.lot.ligne.connect(self.ajouter_ligne)
        self.lot.fini.connect(self.fin_lot)
        self.lot.start()

    def ajouter_ligne(self, fichier, r):
        self.table.setSortingEnabled(False)
        i = self.table.rowCount()
        self.table.insertRow(i)
        if "erreur" in r:
            cells = [i + 1, os.path.basename(fichier), 0, "—", 0, 0, 0, r["erreur"]]
        else:
            reussis = sum(1 for t in r["resultats"] if t["reussi"])
            mention = next(m for seuil, m in langues.mentions() if r["note"] >= seuil)
            cells = [i + 1, os.path.basename(fichier), r["note"], mention.split("—")[0].strip(),
                     r["qualite"], r["tests"], r["structure"],
                     f"{reussis}/{len(r['resultats'])}"]
            self.resultats.append((os.path.basename(fichier), fichier, r))
        for j, val in enumerate(cells):
            it = QTableWidgetItem()
            it.setData(Qt.EditRole, val)
            it.setTextAlignment(Qt.AlignCenter if j != 1 else
                                Qt.AlignLeft | Qt.AlignVCenter)
            if j == 2:
                n = float(val)
                it.setForeground(QColor("#3fb950" if n >= 14 else
                                        "#d29922" if n >= 10 else "#f85149"))
                f = QFont()
                f.setBold(True)
                it.setFont(f)
            self.table.setItem(i, j, it)
        self.table.setSortingEnabled(True)

    def fin_lot(self):
        self.b_lot.setEnabled(True)
        notes = [r["note"] for _, _, r in self.resultats]
        if notes:
            notes_tri = sorted(notes)
            med = notes_tri[len(notes_tri) // 2]
            self.lbl_stat.setText(
                f"n = {len(notes)}   ·   {U('moyenne')} {sum(notes)/len(notes):.2f}/20"
                f"   ·   min {min(notes)}   ·   max {max(notes)}   ·   méd {med}"
                f"   ·   {U('reussite')} ≥10 : "
                f"{sum(1 for n in notes if n >= 10)}/{len(notes)}")
        self.barre.setFormat("✔")

    def ouvrir_copie(self, ligne, _):
        nom = self.table.item(ligne, 1).text()
        for n, chemin, r in self.resultats:
            if n == nom:
                self.ouvrir_editeur(open(chemin, encoding="utf-8").read())
                return

    def exporter_excel(self):
        if not self.resultats:
            return
        try:
            import rapport_excel
        except ImportError:
            QMessageBox.warning(self, "⛔", "pip install openpyxl")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Excel", "notes.xlsx", "Excel (*.xlsx)")
        if f:
            rapport_excel.exporter(f, self.resultats, ide_qt.CFG["solution"] or "",
                                   ide_qt.CFG["tests"] or "", ide_qt.CFG["python"])
            self.statusBar().showMessage(f"📊 {f}", 6000)

    def exporter_csv(self):
        if not self.resultats:
            return
        f, _ = QFileDialog.getSaveFileName(self, "CSV", "notes.csv", "CSV (*.csv)")
        if not f:
            return
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow([U("fichier"), U("note"), U("c_mention"), U("ax_qualite"),
                        U("ax_tests"), U("ax_structure"), U("tests")])
            for nom, _, r in self.resultats:
                reussis = sum(1 for t in r["resultats"] if t["reussi"])
                mention = next(m for seuil, m in langues.mentions() if r["note"] >= seuil)
                w.writerow([nom, r["note"], mention, r["qualite"], r["tests"],
                            r["structure"], f"{reussis}/{len(r['resultats'])}"])
        self.statusBar().showMessage(f"💾 {f}", 5000)


def CFG_PY():
    return ide_qt.CFG.get("python") or sys.executable


def main():
    app = QApplication(sys.argv)
    f = Lanceur()
    f.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
