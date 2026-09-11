#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
correcteur_app.py — التطبيق 2 : شرح أخطاء محاولة التلميذ وتصحيحها وتنقيطها
==========================================================================
موجَّه للأستاذ (وللتلميذ عند المراجعة) : يقارن المحاولة بالحلّ النموذجي،
يشرح كل خطأ مع سببه وتصحيحه، ويعطي نقطة على 20 مفصَّلة، فردًا أو للقسم كلّه.

الواجهة: قائمة رئيسية علوية وتحت كل قائمة صفّ أزرارها (ruban.py)
    📄 TP · ✏ Copie · 📊 Correction · 👥 Classe · 🐍 Interpréteur ·
    👁 Affichage · ❓ Aide

    pip install PyQt5
    python correcteur_app.py
    python correcteur_app.py -s solution.py -t tests.json -e enonce.txt --lang fr
"""

import argparse
import csv
import datetime
import difflib
import glob
import html
import os
import re
import sys

from PyQt5.QtCore import Qt, QSettings, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QTextDocument
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtWidgets import (QApplication, QComboBox, QFileDialog, QHeaderView,
                             QLabel, QLineEdit, QMainWindow, QMessageBox,
                             QProgressBar, QSplitter, QTabWidget, QTableWidget,
                             QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

import langues
from langues import U
import analyseur
from analyseur import analyser_source, calculer_note, bloc_note, annoter
import correcteur
import interpreteurs as itp
import bareme
import correcteur_access as ca
import ide_qt
from ide_qt import (CFG, Editeur, Coloriste, Analyste, Correcteur, Compatibilite,
                    SOMBRE, CLAIR)
from lanceur import Lot
from ruban import Ruban


class LotBD(QThread):
    """تصحيح مجلّد قواعد بيانات في الخلفية."""
    avance = pyqtSignal(int, int, str)
    ligne = pyqtSignal(str, object)
    fini = pyqtSignal()

    def __init__(self, fichiers, solution):
        super().__init__()
        self.fichiers, self.solution = fichiers, solution

    def run(self):
        for i, f in enumerate(self.fichiers, 1):
            self.avance.emit(i, len(self.fichiers), os.path.basename(f))
            try:
                self.ligne.emit(f, ca.comparer(f, self.solution))
            except Exception as e:
                self.ligne.emit(f, {"erreur": f"{type(e).__name__}: {e}"})
        ca.fermer_connexions()
        self.fini.emit()


class AppCorrecteur(QMainWindow):
    def __init__(self):
        super().__init__()
        self.reg = QSettings("ecole", "correcteur_app")
        self.sombre = self.reg.value("sombre", True, type=bool)
        self.taille = self.reg.value("police", 13, type=int)
        self.resultats = []
        self.resultats_bd = []
        self.setWindowTitle("✔ " + U("bt_corriger"))
        self.resize(1280, 820)
        self.construire()
        self.appliquer_theme()
        self.charger_reglages()
        QTimer.singleShot(400, self.analyser)

    # =================================================================
    def construire(self):
        self.ruban = Ruban(self)

        # --- 📄 TP ---
        g = self.ruban.menu("📄 TP")
        self.ch = {}
        for cle, lib in (("solution", U("solution")), ("tests", "tests.json"),
                         ("enonce", U("tab_enonce")), ("essais", U("tab_hist"))):
            e = QLineEdit(placeholderText=lib, maximumWidth=210, toolTip=lib)
            self.ch[cle] = e
            g.widget(e)
            g.bouton("📂", lambda _, k=cle: self.choisir(k), info=lib)
        g.separateur()
        g.bouton("🚀 " + U("bt_demo"), self.charger_demo, principal=True)

        # --- ✏ Copie ---
        g = self.ruban.menu("✏ Copie")
        g.bouton("📂 " + U("bt_ouvrir"), self.ouvrir_copie_dlg, "Ctrl+O")
        g.bouton("💾 " + U("bt_enregistrer"), self.sauver, "Ctrl+S")
        g.bouton("▶ " + U("bt_executer"), self.executer, "F5")
        g.bouton("✨ " + U("bt_formater"), self.formater)
        g.bouton("⬇ " + U("bt_telecharger"), self.exporter)
        g.bouton("📄 PDF", self.exporter_pdf)
        g.separateur()
        self.stdin = QLineEdit(placeholderText=U("ph_stdin"), maximumWidth=160)
        g.widget(self.stdin)

        # --- 📊 Correction ---
        g = self.ruban.menu("📊 " + U("bt_corriger"))
        g.bouton("🔍 " + U("bt_analyser"), self.analyser, "Ctrl+Return")
        g.bouton("✔ " + U("bt_corriger"), self.corriger, "Ctrl+E", principal=True)
        g.bouton("🧮 " + U("bt_evaluer"), self.evaluer, "Ctrl+Shift+E")
        g.bouton("📘 " + U("bt_solution"), self.voir_solution)
        g.bouton("🧩 " + U("bt_compat"), self.compat)
        g.separateur()
        self.lbl_note = QLabel("— / 20", objectName="note")
        g.widget(self.lbl_note)

        # --- ⚖ Barème ---
        g = self.ruban.menu("⚖ " + U("tab_bareme"))
        self.combo_bar = QComboBox(minimumWidth=250)
        self.recharger_baremes()
        self.combo_bar.activated.connect(self.changer_bareme)
        g.widget(self.combo_bar)
        g.bouton("✏ Éditer…", self.editer_bareme, "Ctrl+B", principal=True)
        g.bouton("♻ Recalculer", self.recalculer, info="applique le barème courant")
        self.lbl_bar = QLabel("—")
        g.widget(self.lbl_bar, 1)

        # --- 👥 Classe ---
        g = self.ruban.menu("👥 " + U("tab_lot"))
        self.dossier = QLineEdit(placeholderText=U("dossier"), minimumWidth=250)
        g.widget(self.dossier, 1)
        g.bouton("📂", self.choisir_dossier, info=U("dossier"))
        self.b_lot = g.bouton("▶ " + U("bt_corriger"), self.lancer_lot, principal=True)
        g.bouton("⬇ CSV", self.exporter_csv)
        g.bouton("📊 Excel", self.exporter_excel)
        g.bouton("📄 PDF Classe", self.exporter_pdf_classe)
        g.bouton("🗄 Access / BD", self.exporter_bd)
        g.bouton("👁 " + U("bt_ouvrir"), self.ouvrir_selection)

        # --- 🗄 Bases de données ---
        g = self.ruban.menu("🗄 BD")
        self.bd_sol = QLineEdit(placeholderText="solution.accdb / .db", maximumWidth=210)
        g.widget(self.bd_sol)
        g.bouton("📂", lambda: self.choisir_bd("sol"), info="solution")
        self.bd_dossier = QLineEdit(placeholderText=U("dossier"), maximumWidth=210)
        g.widget(self.bd_dossier)
        g.bouton("📂", lambda: self.choisir_bd("dossier"), info=U("dossier"))
        self.b_bd = g.bouton("▶ " + U("bt_corriger"), self.corriger_bd, principal=True)
        g.bouton("📊 Excel", self.excel_bd)
        g.separateur()
        g.bouton("🔧 Diagnostic", self.diagnostic_bd)

        # --- 🐍 Interpréteur ---
        g = self.ruban.menu("🐍 " + U("c_interp"))
        self.cpy = QComboBox(minimumWidth=230)
        self.cpy.activated.connect(lambda: self.changer_python(self.cpy.currentData()))
        g.widget(self.cpy)
        g.bouton("… " + U("bt_parcourir"), self.parcourir_python)
        g.bouton("⟳ " + U("bt_scan"), lambda: self.remplir_python(True))
        self.lbl_py = QLabel("—")
        g.widget(self.lbl_py, 1)

        # --- 👁 Affichage ---
        g = self.ruban.menu("👁 Affichage")
        g.bouton("🌗 Thème", self.basculer_theme)
        g.bouton("A+", lambda: self.zoom(1))
        g.bouton("A−", lambda: self.zoom(-1))
        g.separateur()
        self.combo_lg = QComboBox()
        for c, n in langues.LANGUES.items():
            self.combo_lg.addItem(n, c)
        self.combo_lg.setCurrentIndex(list(langues.LANGUES).index(langues.langue()))
        self.combo_lg.currentIndexChanged.connect(self.changer_langue)
        g.widget(self.combo_lg)

        g = self.ruban.menu("❓ Aide")
        g.bouton("ℹ " + U("bt_corriger"), lambda: QMessageBox.information(
            self, "ℹ",
            f"{U('ax_qualite')} : 6 · {U('ax_tests')} : 10 · {U('ax_structure')} : 4\n"
            f"{U('sous_exo')}"))

        # ================= الصفحات =================
        self.ed = Editeur()
        self.ed.police(self.taille)
        self.col = Coloriste(self.ed.document(), self.sombre)
        self.minuteur = QTimer(singleShot=True, interval=800)
        self.minuteur.timeout.connect(self.analyser)
        self.ed.textChanged.connect(self.minuteur.start)
        self.ed.cursorPositionChanged.connect(self.maj_etat)

        self.vues, self.panneaux = {}, QTabWidget()
        for cle, titre in (("err", "🔍 " + U("tab_notes")), ("run", "▶ " + U("tab_run")),
                           ("tst", "🧪 " + U("tab_tests")), ("bar", "📊 " + U("tab_bareme")),
                           ("sol", "📘 " + U("tab_sol")), ("enn", "📄 " + U("tab_enonce")),
                           ("his", "🕘 " + U("tab_hist")),
                           ("cmp", "🧩 " + U("tab_compat"))):
            v = QTextBrowser(openLinks=False)
            v.anchorClicked.connect(self.lien)
            self.vues[cle] = v
            self.panneaux.addTab(v, titre)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.ed)
        split.addWidget(self.panneaux)
        split.setSizes([660, 600])

        # صفحة القسم
        page_classe = QWidget()
        vc = QVBoxLayout(page_classe)
        vc.addWidget(QLabel(U("sous_lot"), objectName="sous"))
        self.barre = QProgressBar()
        vc.addWidget(self.barre)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [U("c_num"), U("fichier"), U("note") + " /20", U("c_mention"),
             U("col_q") + " /6", U("col_r") + " /10", U("col_s") + " /4", U("tests")])
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        en = self.table.horizontalHeader()
        for j in (0, 2, 3, 4, 5, 6, 7):
            en.setSectionResizeMode(j, QHeaderView.ResizeToContents)
        en.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(lambda l, _: self.ouvrir_ligne(l))
        vc.addWidget(self.table, 1)
        self.lbl_stat = QLabel("—")
        vc.addWidget(self.lbl_stat)

        # صفحة قواعد البيانات
        page_bd = QWidget()
        vb = QVBoxLayout(page_bd)
        vb.addWidget(QLabel("Comparer chaque base d'élève à la base de référence "
                            "(tables · champs · clés · relations · requêtes)",
                            objectName="sous"))
        self.barre_bd = QProgressBar()
        vb.addWidget(self.barre_bd)
        split_bd = QSplitter(Qt.Horizontal)
        self.bd_axes = ao = ca._axes()
        bd_lib = {"tables": "Tables", "champs": "Champs", "donnees": "Données",
                  "cles": "Clés", "relations": "Relations", "requetes": "Requêtes"}
        bd_cols = [U("fichier"), U("note") + " /20"] + \
            [f"{bd_lib.get(a, a)} /{ao[a]:g}" for a in ao] + ["Écarts"]
        self.table_bd = QTableWidget(0, len(bd_cols))
        self.table_bd.setHorizontalHeaderLabels(bd_cols)
        self.table_bd.setAlternatingRowColors(True)
        self.table_bd.setSortingEnabled(True)
        self.table_bd.verticalHeader().setVisible(False)
        self.table_bd.verticalHeader().setDefaultSectionSize(32)
        eb = self.table_bd.horizontalHeader()
        for j in range(1, len(bd_cols)):
            eb.setSectionResizeMode(j, QHeaderView.ResizeToContents)
        eb.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_bd.currentCellChanged.connect(
            lambda l, *a: self.montrer_ecarts(l))
        self.vue_bd = QTextBrowser()
        split_bd.addWidget(self.table_bd)
        split_bd.addWidget(self.vue_bd)
        split_bd.setSizes([560, 700])
        vb.addWidget(split_bd, 1)
        self.lbl_bd = QLabel("—")
        vb.addWidget(self.lbl_bd)

        self.pages = QTabWidget()
        page_eleve = QWidget()
        ve = QVBoxLayout(page_eleve)
        ve.setContentsMargins(0, 0, 0, 0)
        ve.addWidget(split)
        self.pages.addTab(page_eleve, "✏ Copie")
        self.pages.addTab(page_classe, "👥 " + U("tab_lot"))
        self.pages.addTab(page_bd, "🗄 Bases de données")

        centre = QWidget()
        v = QVBoxLayout(centre)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.ruban)
        v.addWidget(self.pages, 1)
        self.setCentralWidget(centre)
        self.remplir_python()
        self.maj_bareme()
        self.statusBar().showMessage(U("pret"))

    # ================= إعدادات التمرين =================
    def choisir(self, cle):
        if cle == "essais":
            p = QFileDialog.getExistingDirectory(self, U("tab_hist"))
        else:
            filtres = {"solution": "Python (*.py)", "tests": "JSON (*.json)",
                       "enonce": "Texte (*.txt *.md)"}
            p, _ = QFileDialog.getOpenFileName(self, cle, "", filtres[cle])
        if p:
            self.ch[cle].setText(p)
            self.appliquer_reglages()

    def choisir_dossier(self):
        d = QFileDialog.getExistingDirectory(self, U("dossier"))
        if d:
            self.dossier.setText(d)
            self.reg.setValue("dossier", d)

    def charger_demo(self):
        ici = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(ici, "exemples")
        # Le projet peut avoir été recopié dans un dossier déjà nommé « exemples » :
        # dans ce cas les fichiers du TP sont à côté de l'application elle-même.
        if not os.path.isfile(os.path.join(base, "solution.py")):
            base = ici
        for k, f in (("solution", "solution.py"), ("tests", "tests.json"),
                     ("enonce", "enonce.txt")):
            c = os.path.join(base, f)
            if os.path.isfile(c):
                self.ch[k].setText(c)
        self.ch["essais"].setText(os.path.join(base, "essais"))
        if os.path.isdir(os.path.join(base, "classe")):
            self.dossier.setText(os.path.join(base, "classe"))
        bd = os.path.join(base, "bd")
        if os.path.isdir(bd):
            self.bd_dossier.setText(bd)
            if os.path.isfile(os.path.join(bd, "solution.db")):
                self.bd_sol.setText(os.path.join(bd, "solution.db"))
        self.appliquer_reglages()
        self.statusBar().showMessage("🚀 " + base, 5000)

    def appliquer_reglages(self):
        CFG.update(solution=self.ch["solution"].text().strip() or None,
                   tests=self.ch["tests"].text().strip() or None,
                   essais=self.ch["essais"].text().strip() or "essais")
        e = self.ch["enonce"].text().strip()
        CFG["enonce"] = open(e, encoding="utf-8").read() \
            if e and os.path.isfile(e) else ""
        self.vues["enn"].setPlainText(CFG["enonce"] or "—")
        for k, w in self.ch.items():
            self.reg.setValue(k, w.text())
        self.historique()

    def charger_reglages(self):
        for k, w in self.ch.items():
            w.setText(self.reg.value(k, "", type=str))
        self.dossier.setText(self.reg.value("dossier", "", type=str))
        self.bd_sol.setText(self.reg.value("bd_sol", "", type=str))
        self.bd_dossier.setText(self.reg.value("bd_dossier", "", type=str))
        self.ed.setPlainText(self.reg.value("copie", "", type=str)
                             or "# " + U("titre_app") + "\n")
        self.appliquer_reglages()

    # ================= قواعد البيانات =================
    def choisir_bd(self, quoi):
        if quoi == "sol":
            f, _ = QFileDialog.getOpenFileName(
                self, U("solution"), "", "Bases (*.accdb *.mdb *.db *.sqlite)")
            if f:
                self.bd_sol.setText(f)
                self.reg.setValue("bd_sol", f)
        else:
            d = QFileDialog.getExistingDirectory(self, U("dossier"))
            if d:
                self.bd_dossier.setText(d)
                self.reg.setValue("bd_dossier", d)

    def corriger_bd(self):
        sol = self.bd_sol.text().strip()
        if not sol or not os.path.isfile(sol):
            QMessageBox.warning(self, "⛔", U("msg_no_sol"))
            return
        base = self.bd_dossier.text().strip() or os.path.dirname(sol)
        fichiers = [f for ext in ("*.accdb", "*.mdb", "*.db", "*.sqlite")
                    for f in sorted(glob.glob(os.path.join(base, ext)))
                    if os.path.realpath(f) != os.path.realpath(sol)]
        if not fichiers:
            QMessageBox.information(self, "—", "0 base trouvée")
            return
        self.pages.setCurrentIndex(2)
        self.table_bd.setRowCount(0)
        self.resultats_bd = []
        self.bd_corrigee = False
        self.barre_bd.setMaximum(len(fichiers))
        self.b_bd.setEnabled(False)
        self.lot_bd = LotBD(fichiers, sol)
        self.lot_bd.avance.connect(lambda i, n, nom: (
            self.barre_bd.setValue(i), self.barre_bd.setFormat(f"{i}/{n} — {nom}")))
        self.lot_bd.ligne.connect(self.ajouter_bd)
        self.lot_bd.fini.connect(self.fin_bd)
        self.lot_bd.start()

    def ajouter_bd(self, fichier, r):
        self.table_bd.setSortingEnabled(False)
        i = self.table_bd.rowCount()
        self.table_bd.insertRow(i)
        nom = os.path.basename(fichier)
        if "erreur" in r:
            vals = [nom, 0] + [0] * len(self.bd_axes) + [r["erreur"][:60]]
        else:
            a = r["axes"]
            vals = [nom, r["note"]] + [a.get(k, 0) for k in self.bd_axes] + \
                [len(r["ecarts"])]
            self.resultats_bd.append((nom, r))
        for j, v in enumerate(vals):
            it = QTableWidgetItem()
            it.setData(Qt.EditRole, v)
            it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter if j == 0 else Qt.AlignCenter)
            if j == 1 and isinstance(v, (int, float)):
                it.setForeground(QColor("#3fb950" if v >= 14 else
                                        "#d29922" if v >= 10 else "#f85149"))
                fo = QFont()
                fo.setBold(True)
                it.setFont(fo)
            self.table_bd.setItem(i, j, it)
        self.table_bd.setSortingEnabled(True)

    def fin_bd(self):
        self.b_bd.setEnabled(True)
        self.barre_bd.setFormat("✔")
        self.bd_corrigee = True
        notes = [r["note"] for _, r in self.resultats_bd]
        if notes:
            self.lbl_bd.setText(
                f"n = {len(notes)}   ·   {U('moyenne')} {sum(notes)/len(notes):.2f}/20"
                f"   ·   min {min(notes)}   ·   max {max(notes)}")
            self.table_bd.selectRow(0)

    def montrer_ecarts(self, ligne):
        if ligne < 0 or not getattr(self, "resultats_bd", None):
            return
        nom = self.table_bd.item(ligne, 0).text()
        for n, r in self.resultats_bd:
            if n != nom:
                continue
            e_, s_ = r["eleve"], r["solution"]
            t = (f"<h3>{html.escape(nom)} — {r['note']} / 20</h3>"
                 f"<table width='100%' cellpadding='5'>"
                 f"<tr><th align='left'>Objet</th><th>Élève</th><th>Solution</th>"
                 f"<th>=</th></tr>")
            for lib, a, b in (("Tables", len(e_["tables"]), len(s_["tables"])),
                              ("Champs",
                               sum(len(d["champs"]) for d in e_["tables"].values()),
                               r["attendu"]["champs"]),
                              ("Relations", len(e_["relations"]), len(s_["relations"])),
                              ("Requêtes", len(e_["requetes"]), len(s_["requetes"]))):
                t += (f"<tr><td>{lib}</td><td align='center'>{a}</td>"
                      f"<td align='center'>{b}</td>"
                      f"<td align='center'>{'✅' if a == b else '❌'}</td></tr>")
            t += "</table><hr>"
            for x in r["ecarts"]:
                c = "#f85149" if x.gravite == "erreur" else "#d29922"
                t += (f"<div style='border-left:3px solid {c};padding:6px 10px;"
                      f"margin:6px 0'>{x.icone} [{x.code}] {html.escape(x.message)}"
                      f"<br>💡 <b>{U('cause')}:</b> {html.escape(x.cause)}"
                      f"<br>✅ <b>{U('fix')}:</b> {html.escape(x.correction)}</div>")
            self.vue_bd.setHtml(t or "✅")
            return

    def excel_bd(self):
        if not getattr(self, "resultats_bd", None):
            QMessageBox.information(self, "—", U("msg_vide"))
            return
        f, _ = QFileDialog.getSaveFileName(self, "Excel", "rapport_bd.xlsx",
                                           "Excel (*.xlsx)")
        if f:
            ca.exporter_excel(f, self.resultats_bd, self.bd_sol.text())
            self.statusBar().showMessage(f"📊 {f}", 6000)

    def diagnostic_bd(self):
        import rapport_access
        QMessageBox.information(
            self, "🔧 Diagnostic",
            "Lecture des bases :\n" + ca.diagnostic() +
            "\n\nÉcriture Access :\n" + rapport_access.diagnostic() +
            "\n\nInterpréteurs Python :\n" +
            "\n".join(f"  • {d['etiquette']} — {d['chemin']}"
                       for d in itp.scanner()))

    # ================= السلّم =================
    def recharger_baremes(self):
        self.combo_bar.blockSignals(True)
        self.combo_bar.clear()
        for n, c in bareme.profils():
            self.combo_bar.addItem(n, c)
        self.combo_bar.blockSignals(False)

    def changer_bareme(self):
        c = self.combo_bar.currentData()
        try:
            bareme.charger(c) if c else bareme.reinitialiser()
        except Exception as e:
            QMessageBox.warning(self, "⛔", str(e))
            return
        self.maj_bareme()
        self.recalculer()

    def editer_bareme(self):
        import editeur_bareme
        if editeur_bareme.ouvrir(self, self.resultats):
            self.recharger_baremes()
            self.maj_bareme()
            self.recalculer()

    def maj_bareme(self):
        a = bareme.axes()
        self.lbl_bar.setText(
            f"⚖ {bareme.nom()} · {U('note')} max {bareme.note_max():g} · "
            f"{U('ax_qualite')} {a['qualite']:g} / {U('ax_tests')} {a['tests']:g} / "
            f"{U('ax_structure')} {a['structure']:g} · "
            f"{len(bareme.regles())} règles" +
            (f" · tolérance {bareme.tolerance()}" if bareme.tolerance() else ""))

    def recalculer(self):
        """يعيد التحليل، ويعيد تصحيح القسم إن كان مصحَّحًا من قبل."""
        self.analyser()
        if self.resultats and self.dossier.text():
            self.lancer_lot()
        if getattr(self, "bd_corrigee", False) and self.bd_sol.text():
            self.corriger_bd()

    # ================= المفسّر =================
    def remplir_python(self, forcer=False):
        self.cpy.blockSignals(True)
        self.cpy.clear()
        for d in itp.scanner(forcer):
            self.cpy.addItem(d["etiquette"], d["chemin"])
        if not self.cpy.count():
            self.cpy.addItem(sys.executable, sys.executable)
        actif = os.path.realpath(CFG["python"])
        for i in range(self.cpy.count()):
            if os.path.realpath(self.cpy.itemData(i)) == actif:
                self.cpy.setCurrentIndex(i)
        self.cpy.blockSignals(False)
        d = itp.info(CFG["python"])
        self.lbl_py.setText(f"{CFG['python']}  ·  pip {'✅' if d.get('pip') else '❌'}")

    def parcourir_python(self):
        filtre = "python.exe (python*.exe)" if os.name == "nt" else "python (python*)"
        f, _ = QFileDialog.getOpenFileName(self, U("bt_parcourir"), "", filtre)
        if f:
            self.changer_python(f)

    def changer_python(self, chemin):
        v = itp.valider(chemin)
        if not v.get("ok"):
            QMessageBox.warning(self, "⛔", U("interp_ko"))
            return
        CFG["python"] = analyseur.PYTHON = correcteur.PYTHON = v["chemin"]
        self.statusBar().showMessage(f"{U('interp_ok')} : {v['etiquette']}", 4000)
        self.remplir_python()
        self.analyser()

    # ================= المحاولة الفردية =================
    def lancer(self, th, slot, echec=None):
        self._th = getattr(self, "_th", [])
        self._th.append(th)
        th.fini.connect(slot)
        if echec:
            th.echec.connect(echec)
        th.finished.connect(lambda: self._th.remove(th) if th in self._th else None)
        th.start()

    def analyser(self):
        self.lancer(Analyste(self.ed.toPlainText()), self.montrer_analyse)

    def montrer_analyse(self, probs, note, mention, detail):
        self.ed.marques = {}
        for p in probs:
            if self.ed.marques.get(p.ligne) != "e":
                self.ed.marques[p.ligne] = "e" if p.gravite == analyseur.ERREUR else "w"
        self.ed.marge.update()
        self.lbl_note.setText(f"{note} / 20")
        self.vues["err"].setHtml(self.html_probs(probs) or
                                 f"<p style='color:#3fb950'>✅ {U('aucun')}</p>")
        self.vues["bar"].setHtml("<pre>" + html.escape(
            "\n".join(bloc_note(note, mention, detail))) + "</pre>")

    def html_probs(self, probs):
        return "".join(
            f"<div style='border-left:3px solid "
            f"{'#f85149' if p.gravite == analyseur.ERREUR else '#d29922'};"
            f"padding:6px 10px;margin:6px 0'>{p.icone} "
            f"<a href='ligne:{p.ligne}'>{U('ligne')} {p.ligne}</a> [{p.code}] "
            f"{html.escape(p.message)}<br>💡 <b>{U('cause')}:</b> "
            f"{html.escape(p.explication)}<br>✅ <b>{U('fix')}:</b> "
            f"{html.escape(p.correction)}"
            + (f"<br><code>{html.escape(p.ligne_corrigee.strip())}</code>"
               if p.ligne_corrigee else "") + "</div>"
            for p in sorted(probs, key=lambda x: x.ligne))

    def lien(self, url):
        s = url.toString()
        if s.startswith("ligne:"):
            self.ed.aller_ligne(int(s.split(":")[1]))
        elif s.startswith("essai:"):
            c = os.path.join(CFG["essais"], os.path.basename(s.split(":", 1)[1]))
            if os.path.isfile(c):
                t = open(c, encoding="utf-8").read().split("\n", 1)
                self.ed.setPlainText(t[1] if len(t) > 1 else "")
                self.analyser()

    def corriger(self):
        if not CFG["solution"]:
            QMessageBox.information(self, "—", U("msg_no_sol"))
            return
        self.pages.setCurrentIndex(0)
        self.panneaux.setCurrentIndex(2)
        self.vues["tst"].setPlainText(U("msg_running"))
        self.lancer(Correcteur(self.ed.toPlainText()), self.montrer_correction,
                    lambda m: self.vues["tst"].setPlainText(m))

    def montrer_correction(self, r):
        self.lbl_note.setText(f"{r['note']} / 20")
        t = (f"<table width='100%' cellpadding='6'><tr><th align='left'>{U('axe')}</th>"
             f"<th>{U('note')}</th><th>{U('sur')}</th></tr>")
        for lib, val, tot in ((U("ax_qualite"), r["qualite"], 6),
                              (U("ax_tests"), r["tests"], 10),
                              (U("ax_structure"), r["structure"], 4)):
            t += (f"<tr><td>{lib}</td><td align='center'>{val}</td>"
                  f"<td align='center'>{tot}</td></tr>")
        t += (f"<tr><td><b>{U('total')}</b></td><td align='center'><b>{r['note']}</b>"
              f"</td><td align='center'><b>20</b></td></tr></table><hr>")
        for x in r["resultats"]:
            c = "#3fb950" if x["reussi"] else "#f85149"
            t += (f"<div style='border-left:3px solid {c};padding:5px 10px;margin:5px 0'>"
                  f"{'✅' if x['reussi'] else '❌'} {html.escape(str(x['nom']))}")
            if not x["reussi"]:
                t += (f"<br>{U('attendu')}: <code>{html.escape(str(x['attendu']))}</code>"
                      f"<br>{U('obtenu')}: <code>{html.escape(str(x['obtenu']))}</code>")
            t += "</div>"
        for m in r["remarques"]:
            t += f"<div style='padding:4px 10px'>{html.escape(m)}</div>"
        self.vues["tst"].setHtml(t)
        self.vues["err"].setHtml(self.html_probs(r["problemes"]))
        self.journaliser(r["note"], "correction")

    def evaluer(self):
        """Évaluation complète puis export PDF du rapport (comme evaluer.py)."""
        if not CFG["solution"]:
            QMessageBox.information(self, "—", U("msg_no_sol"))
            return
        self.pages.setCurrentIndex(0)
        self.panneaux.setCurrentIndex(2)
        self.vues["tst"].setPlainText(U("msg_running"))
        self.lancer(Correcteur(self.ed.toPlainText()), self.evaluer_fin,
                    lambda m: self.vues["tst"].setPlainText(m))

    def evaluer_fin(self, r):
        self.montrer_correction(r)
        self.exporter_correction_pdf(r)

    def voir_solution(self):
        if not CFG["solution"]:
            QMessageBox.information(self, "—", U("msg_no_sol"))
            return
        if QMessageBox.question(self, "📘", U("msg_conf_sol")) != QMessageBox.Yes:
            return
        CFG["vu_solution"] = True
        src = open(CFG["solution"], encoding="utf-8").read()
        diff = "\n".join(difflib.unified_diff(
            self.ed.toPlainText().splitlines(), src.splitlines(), lineterm="", n=2))
        self.vues["sol"].setHtml(f"<pre>{html.escape(src)}</pre><hr>"
                                 f"<h4>🔀 {U('diff')}</h4><pre>{html.escape(diff)}</pre>")
        self.panneaux.setCurrentIndex(4)
        self.journaliser("—", "vue-solution")

    def compat(self):
        self.panneaux.setCurrentIndex(7)
        self.vues["cmp"].setPlainText(U("msg_running"))
        self.lancer(Compatibilite(self.ed.toPlainText(), self.stdin.text()),
                    self.montrer_compat)

    def montrer_compat(self, lignes):
        t = (f"<table width='100%' cellpadding='6'><tr><th align='left'>{U('c_interp')}"
             f"</th><th>{U('c_compile')}</th><th>{U('c_exec')}</th><th>{U('c_ms')}</th>"
             f"<th align='left'>{U('c_sortie')}</th></tr>")
        for x in lignes:
            t += (f"<tr><td>{html.escape(x['etiquette'])}</td>"
                  f"<td align='center'>{'✅' if x['compile'] else '❌'}</td>"
                  f"<td align='center'>{'✅' if x['execute'] else '❌'}</td>"
                  f"<td align='center'>{x['ms']} ms</td><td><code>"
                  f"{html.escape((x.get('sortie') or x.get('erreur') or '')[:110])}"
                  f"</code></td></tr>")
        self.vues["cmp"].setHtml(t + "</table>")

    def executer(self):
        self.panneaux.setCurrentIndex(1)
        self.vues["run"].setPlainText(U("msg_running"))
        r = itp.essayer(CFG["python"], self.ed.toPlainText(), self.stdin.text())
        self.vues["run"].setPlainText((r.get("sortie") or "") +
                                      (f"\n⛔ {r['erreur']}" if r.get("erreur") else "") +
                                      f"\n[{r['ms']} ms]")

    def ouvrir_copie_dlg(self):
        f, _ = QFileDialog.getOpenFileName(self, U("bt_ouvrir"), "", "Python (*.py)")
        if f:
            self.ed.setPlainText(open(f, encoding="utf-8").read())
            self.pages.setCurrentIndex(0)
            self.analyser()

    def formater(self):
        t = self.ed.toPlainText().replace("\t", "    ")
        t = re.sub(r"[ \t]+$", "", t, flags=re.M)
        self.ed.setPlainText(re.sub(r"\n{3,}", "\n\n", t).rstrip() + "\n")

    def exporter(self):
        f, _ = QFileDialog.getSaveFileName(self, U("bt_telecharger"),
                                           "copie_annotee.py", "Python (*.py)")
        if not f:
            return
        src = self.ed.toPlainText()
        probs = analyser_source(src, "copie.py", py=CFG["python"])
        open(f, "w", encoding="utf-8").write(annoter(src.splitlines(), probs, "copie.py"))
        self.statusBar().showMessage(f"💾 {f}", 4000)

    def exporter_pdf(self):
        """Génère un PDF annoté de la copie actuelle (note, erreurs, corrections)."""
        src = self.ed.toPlainText()
        probs = analyser_source(src, "copie.py", py=CFG["python"])
        note, mention, detail = calculer_note(probs)

        f = self._demander_pdf("copie_evaluee.pdf")
        if not f:
            return

        html = self._rapport_html(src, probs, note, mention, detail)
        self._imprimer_pdf(html, f)
        self.statusBar().showMessage(f"📄 {f}", 5000)

    def _demander_pdf(self, nom):
        dlg = QFileDialog(self, "📄 Export PDF")
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        dlg.setNameFilter("PDF (*.pdf)")
        dlg.selectFile(nom)
        if not dlg.exec_():
            return None
        f = dlg.selectedFiles()[0]
        return f if f.lower().endswith(".pdf") else f + ".pdf"

    @staticmethod
    def _imprimer_pdf(html, chemin):
        doc = QTextDocument()
        doc.setDefaultStyleSheet(
            "body{font-family:'Segoe UI',Arial;font-size:12px;color:#222}"
            "h1{font-size:20px;color:#1F3864}"
            "h2{font-size:15px;color:#1F3864;border-bottom:2px solid #1F3864}"
            ".err{border-left:4px solid #f85149;padding:6px 10px;margin:6px 0;"
            "background:#fdf2f2}"
            ".warn{border-left:4px solid #d29922;padding:6px 10px;margin:6px 0;"
            "background:#fff8e6}"
            "pre{font-family:Consolas,'Courier New';font-size:11px;background:#f5f5f5;"
            "padding:10px;border:1px solid #ddd}code{font-family:Consolas}"
            "table{border-collapse:collapse}"
            "th,td{border:1px solid #ccc;padding:5px 8px}"
            "th{background:#e8eef7;color:#1F3864}")
        doc.setHtml(html)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(chemin)
        printer.setPageSize(QPrinter.A4)
        printer.setPageMargins(15, 15, 15, 15, QPrinter.Millimeter)
        doc.print_(printer)

    def _rapport_html(self, src, probs, note, mention, detail):
        t = [f"<h1>📊 {U('note_finale')} : {note} / 20  —  {mention}</h1>"]
        t.append(f"<p><b>⚖ {U('c_regle')} :</b> {bareme.nom()} · "
                 f"{U('ax_qualite')} {bareme.axes()['qualite']:g} / "
                 f"{U('ax_tests')} {bareme.axes()['tests']:g} / "
                 f"{U('ax_structure')} {bareme.axes()['structure']:g}</p>")
        t.append("<pre>" + html.escape(
            "\n".join(bloc_note(note, mention, detail))) + "</pre>")
        t.append(f"<h2>🔍 {U('sur_code')} ({len(probs)})</h2>")
        for p in sorted(probs, key=lambda x: x.ligne):
            cls = "err" if p.gravite == analyseur.ERREUR else "warn"
            t.append(f"<div class='{cls}'><b>{p.icone} {U('ligne')} {p.ligne} "
                     f"[{p.code}]</b> {html.escape(p.message)}"
                     f"<br>💡 <b>{U('cause')}:</b> {html.escape(p.explication)}"
                     f"<br>✅ <b>{U('fix')}:</b> {html.escape(p.correction)}</div>")
        t.append("<h2>🧾 Python</h2><pre>" + html.escape(src) + "</pre>")
        return "".join(t)

    def exporter_correction_pdf(self, r):
        """PDF du rapport d'évaluation complet (note, tests, structure, code)."""
        f = self._demander_pdf("rapport_evaluation.pdf")
        if not f:
            return
        self._imprimer_pdf(self._rapport_correction_html(r), f)
        self.statusBar().showMessage(f"📄 {f}", 5000)

    def _rapport_correction_html(self, r):
        t = [f"<h1>🧮 {U('note_finale')} : {r['note']} / 20</h1>"]
        t.append(f"<p><b>⚖ {U('c_regle')} :</b> {bareme.nom()} · "
                 f"{U('ax_qualite')} {bareme.axes()['qualite']:g} / "
                 f"{U('ax_tests')} {bareme.axes()['tests']:g} / "
                 f"{U('ax_structure')} {bareme.axes()['structure']:g}</p>")
        t.append(f"<h2>📊 {U('axe')}</h2><table>"
                 f"<tr><th align='left'>{U('axe')}</th><th>{U('note')}</th><th>{U('sur')}</th></tr>")
        for lib, val, tot in ((U("ax_qualite"), r["qualite"], 6),
                              (U("ax_tests"), r["tests"], 10),
                              (U("ax_structure"), r["structure"], 4)):
            t.append(f"<tr><td>{lib}</td><td align='center'>{val}</td>"
                     f"<td align='center'>{tot}</td></tr>")
        t.append(f"<tr><td><b>{U('total')}</b></td><td align='center'><b>{r['note']}</b></td>"
                 f"<td align='center'><b>20</b></td></tr></table>")
        t.append(f"<h2>🧪 {U('tests')} ({len(r['resultats'])})</h2>")
        for x in r["resultats"]:
            c = "#3fb950" if x["reussi"] else "#f85149"
            t.append(f"<div style='border-left:4px solid {c};padding:5px 10px;margin:5px 0'>"
                     f"{'✅' if x['reussi'] else '❌'} {html.escape(str(x['nom']))}")
            if not x["reussi"]:
                t.append(f"<br>{U('attendu')}: <code>{html.escape(str(x['attendu']))}</code>"
                         f"<br>{U('obtenu')}: <code>{html.escape(str(x['obtenu']))}</code>")
            t.append("</div>")
        if r["remarques"]:
            t.append(f"<h2>🏗️ {U('structure')}</h2>")
            for m in r["remarques"]:
                t.append(f"<div style='padding:4px 10px'>{html.escape(m)}</div>")
        t.append(f"<h2>🔍 {U('sur_code')} ({len(r['problemes'])})</h2>")
        for p in sorted(r["problemes"], key=lambda x: x.ligne):
            cls = "err" if p.gravite == analyseur.ERREUR else "warn"
            t.append(f"<div class='{cls}'><b>{p.icone} {U('ligne')} {p.ligne} "
                     f"[{p.code}]</b> {html.escape(p.message)}"
                     f"<br>💡 <b>{U('cause')}:</b> {html.escape(p.explication)}"
                     f"<br>✅ <b>{U('fix')}:</b> {html.escape(p.correction)}</div>")
        t.append("<h2>🧾 Python</h2><pre>" + html.escape(self.ed.toPlainText()) + "</pre>")
        return "".join(t)

    def exporter_pdf_classe(self):
        """PDF récapitulatif de la classe : notes, statistiques, fréquences d'erreurs."""
        if not self.resultats:
            QMessageBox.information(self, "—", U("msg_vide"))
            return
        f = self._demander_pdf("classe_notes.pdf")
        if not f:
            return
        self._imprimer_pdf(self._classe_html(), f)
        self.statusBar().showMessage(f"📄 {f}", 5000)

    def _classe_html(self):
        notes = [r["note"] for _, _, r in self.resultats]
        tri = sorted(notes)
        stats = (f"n = {len(notes)} · {U('moyenne')} {sum(notes)/len(notes):.2f}/20"
                 f" · min {min(notes)} · max {max(notes)} · méd {tri[len(tri)//2]}"
                 f" · {U('reussite')} ≥10 : "
                 f"{sum(1 for n in notes if n >= 10)}/{len(notes)}")

        t = [f"<h1>👥 {U('tab_lot')} — {len(notes)} {U('copie')}(s)</h1>"]
        t.append(f"<p><b>⚖ {U('c_regle')} :</b> {bareme.nom()} · "
                 f"📘 {U('bt_solution')} : {html.escape(os.path.basename(CFG['solution'] or ''))} · "
                 f"🧪 {U('tests')} : {html.escape(os.path.basename(CFG['tests'] or ''))}</p>")
        t.append(f"<h2>📊 {U('moyenne')}</h2><p>{html.escape(stats)}</p>")

        lignes = ""
        for i, (_, chemin, r) in enumerate(
                sorted(self.resultats, key=lambda x: -x[2]["note"]), 1):
            reussis = sum(1 for tt in r["resultats"] if tt["reussi"])
            mention = next(m for s, m in langues.mentions()
                           if r["note"] >= s).split("—")[0].strip()
            lignes += (f"<tr><td align='center'>{i}</td>"
                       f"<td>{html.escape(os.path.basename(chemin)[:-3])}</td>"
                       f"<td align='center'><b>{r['note']:g}</b></td><td>{mention}</td>"
                       f"<td align='center'>{r['qualite']:g}</td>"
                       f"<td align='center'>{r['tests']:g}</td>"
                       f"<td align='center'>{r['structure']:g}</td>"
                       f"<td align='center'>{reussis}/{len(r['resultats'])}</td></tr>")
        t.append(f"<h2>👥 {U('tab_lot')}</h2><table><tr><th>#</th>"
                 f"<th align='left'>{U('fichier')}</th><th>{U('note')}</th>"
                 f"<th>{U('c_mention')}</th><th>{U('col_q')}</th><th>{U('col_r')}</th>"
                 f"<th>{U('col_s')}</th><th>{U('tests')}</th></tr>{lignes}</table>")

        freq = {}
        lib = {}
        for _, _, r in self.resultats:
            for p in r["problemes"]:
                freq[p.code] = freq.get(p.code, 0) + 1
                lib.setdefault(p.code, p.message)
        if freq:
            rang = ""
            for j, (code, nb) in enumerate(sorted(freq.items(), key=lambda kv: -kv[1]), 1):
                rang += (f"<tr><td align='center'>{j}</td><td><code>"
                         f"{html.escape(code)}</code></td>"
                         f"<td>{html.escape(lib[code])}</td>"
                         f"<td align='center'>{nb}</td></tr>")
            t.append(f"<h2>🔍 {U('sur_code')} — Occurrences</h2><table><tr><th>#</th>"
                     f"<th>{U('c_code')}</th><th>{U('c_regle')}</th><th>Occ.</th></tr>"
                     f"{rang}</table>")
        return "".join(t)

    def sauver(self):
        self.statusBar().showMessage(f"{U('msg_saved')} — "
                                     f"{self.journaliser('—', 'sauvegarde')}", 4000)

    def journaliser(self, note, etiquette):
        os.makedirs(CFG["essais"], exist_ok=True)
        h = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nom = f"essai_{h}.py"
        open(os.path.join(CFG["essais"], nom), "w", encoding="utf-8").write(
            f"# note={note} date={h} vu_solution={CFG['vu_solution']} ({etiquette})\n"
            + self.ed.toPlainText())
        self.reg.setValue("copie", self.ed.toPlainText())
        self.historique()
        return nom

    def historique(self):
        out = []
        for c in sorted(glob.glob(os.path.join(CFG["essais"], "essai_*.py")),
                        reverse=True)[:30]:
            e = open(c, encoding="utf-8").readline()
            n = re.search(r"note=(\S+)", e)
            d = re.search(r"date=(\d{8}_\d{6})", e)
            d = d.group(1) if d else ""
            out.append(f"<div style='padding:4px 8px'><a href='essai:"
                       f"{os.path.basename(c)}'>{os.path.basename(c)}</a> — "
                       f"<b>{n.group(1) if n else '—'}</b>/20 · {d[6:8]}/{d[4:6]} "
                       f"{d[9:11]}:{d[11:13]}{' · 📘' if 'vu_solution=True' in e else ''}"
                       f"</div>")
        self.vues["his"].setHtml("".join(out) or U("msg_vide"))

    # ================= القسم =================
    def lancer_lot(self):
        self.appliquer_reglages()
        if not CFG["solution"]:
            QMessageBox.warning(self, "⛔", U("msg_no_sol"))
            return
        fichiers = [f for f in sorted(glob.glob(os.path.join(self.dossier.text(), "*.py")))
                    if os.path.realpath(f) != os.path.realpath(CFG["solution"])]
        if not fichiers:
            QMessageBox.information(self, "—", "*.py : 0")
            return
        self.pages.setCurrentIndex(1)
        self.table.setRowCount(0)
        self.resultats = []
        self.barre.setMaximum(len(fichiers))
        self.b_lot.setEnabled(False)
        self.lot = Lot(fichiers, CFG["solution"], CFG["tests"])
        self.lot.avance.connect(lambda i, n, nom: (self.barre.setValue(i),
                                                   self.barre.setFormat(f"{i}/{n} — {nom}")))
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
            mention = next(m for s, m in langues.mentions() if r["note"] >= s)
            cells = [i + 1, os.path.basename(fichier), r["note"],
                     mention.split("—")[0].strip(), r["qualite"], r["tests"],
                     r["structure"], f"{reussis}/{len(r['resultats'])}"]
            self.resultats.append((os.path.basename(fichier), fichier, r))
        for j, val in enumerate(cells):
            it = QTableWidgetItem()
            it.setData(Qt.EditRole, val)
            it.setTextAlignment(Qt.AlignCenter if j != 1
                                else Qt.AlignLeft | Qt.AlignVCenter)
            if j == 2:
                n = float(val)
                it.setForeground(QColor("#3fb950" if n >= 14 else
                                        "#d29922" if n >= 10 else "#f85149"))
                fo = QFont()
                fo.setBold(True)
                it.setFont(fo)
            self.table.setItem(i, j, it)
        self.table.setSortingEnabled(True)

    def fin_lot(self):
        self.b_lot.setEnabled(True)
        notes = [r["note"] for _, _, r in self.resultats]
        if notes:
            tri = sorted(notes)
            self.lbl_stat.setText(
                f"n = {len(notes)}   ·   {U('moyenne')} {sum(notes)/len(notes):.2f}/20"
                f"   ·   min {min(notes)}   ·   max {max(notes)}"
                f"   ·   méd {tri[len(tri)//2]}   ·   {U('reussite')} ≥10 : "
                f"{sum(1 for n in notes if n >= 10)}/{len(notes)}")
        self.barre.setFormat("✔")

    def ouvrir_ligne(self, ligne):
        nom = self.table.item(ligne, 1).text()
        for n, chemin, r in self.resultats:
            if n == nom:
                self.ed.setPlainText(open(chemin, encoding="utf-8").read())
                self.pages.setCurrentIndex(0)
                self.montrer_correction(r)
                return

    def ouvrir_selection(self):
        if self.table.currentRow() >= 0:
            self.ouvrir_ligne(self.table.currentRow())

    def exporter_excel(self):
        """تقرير Excel متعدّد الأوراق (Synthèse, Notes, Tests, Erreurs…)."""
        if not self.resultats:
            QMessageBox.information(self, "—", U("msg_vide"))
            return
        try:
            import rapport_excel
        except ImportError:
            QMessageBox.warning(self, "⛔", "pip install openpyxl")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Excel", "notes.xlsx", "Excel (*.xlsx)")
        if not f:
            return
        try:
            rapport_excel.exporter(f, self.resultats, CFG["solution"] or "",
                                   CFG["tests"] or "", CFG["python"])
            self.statusBar().showMessage(f"📊 {f}", 6000)
        except Exception as e:
            QMessageBox.warning(self, "⛔", f"{type(e).__name__}: {e}")

    def exporter_bd(self):
        """تصدير إلى Access (.accdb) أو SQLite (.db) أو مجلّد CSV."""
        if not self.resultats:
            QMessageBox.information(self, "—", U("msg_vide"))
            return
        import rapport_access as ra
        f, filtre = QFileDialog.getSaveFileName(
            self, "Access / SQLite", "notes.accdb",
            "Access (*.accdb);;SQLite (*.db);;Dossier CSV (*)")
        if not f:
            return
        mode = ("access" if f.lower().endswith(".accdb")
                else "sqlite" if f.lower().endswith(".db") else "csv")
        try:
            ra.exporter(f, self.resultats, mode, CFG["solution"] or "",
                        CFG["tests"] or "", CFG["python"])
            self.statusBar().showMessage(f"🗄 {f}", 6000)
        except Exception as e:
            QMessageBox.warning(self, "⛔", f"{e}\n\n{ra.diagnostic()}")

    def exporter_csv(self):
        if not self.resultats:
            QMessageBox.information(self, "—", U("msg_vide"))
            return
        f, _ = QFileDialog.getSaveFileName(self, "CSV", "notes.csv", "CSV (*.csv)")
        if not f:
            return
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow([U("fichier"), U("note"), U("c_mention"), U("col_q"),
                        U("col_r"), U("col_s"), U("tests")])
            for nom, _, r in self.resultats:
                reussis = sum(1 for t in r["resultats"] if t["reussi"])
                mention = next(m for s, m in langues.mentions() if r["note"] >= s)
                w.writerow([nom, r["note"], mention, r["qualite"], r["tests"],
                            r["structure"], f"{reussis}/{len(r['resultats'])}"])
        self.statusBar().showMessage(f"💾 {f}", 5000)

    # ================= المظهر =================
    def appliquer_theme(self):
        self.setStyleSheet(SOMBRE if self.sombre else CLAIR)
        self.ruban.theme(self.sombre)
        self.ed.sombre = self.sombre
        self.col.definir(self.sombre)
        self.ed.surligner_ligne()
        self.ed.marge.update()

    def basculer_theme(self):
        self.sombre = not self.sombre
        self.reg.setValue("sombre", self.sombre)
        self.appliquer_theme()

    def zoom(self, d):
        self.taille = min(24, max(9, self.taille + d))
        self.reg.setValue("police", self.taille)
        self.ed.police(self.taille)

    def changer_langue(self):
        langues.definir_langue(self.combo_lg.currentData())
        QMessageBox.information(self, "🌐", U("interp_ok"))
        self.analyser()

    def maj_etat(self):
        c = self.ed.textCursor()
        self.statusBar().showMessage(
            f"{U('ligne')} {c.blockNumber() + 1}:{c.positionInBlock() + 1}   ·   "
            f"🐍 {os.path.basename(CFG['python'])}   ·   "
            f"📘 {os.path.basename(CFG['solution'] or '—')}")

    def closeEvent(self, e):
        for th in list(getattr(self, "_th", [])):
            th.wait(3000)
        self.reg.setValue("copie", self.ed.toPlainText())
        ca.fermer_connexions()
        super().closeEvent(e)


def main():
    ap = argparse.ArgumentParser(description="Correcteur de copies Python")
    ap.add_argument("-s", "--solution")
    ap.add_argument("-t", "--tests")
    ap.add_argument("-e", "--enonce")
    ap.add_argument("--essais", default="essais")
    ap.add_argument("--bareme", help="ملفّ سلّم JSON أو اسم ملفّ تعريف")
    ap.add_argument("--python", default=analyseur.detecter_python())
    ap.add_argument("--lang", choices=list(langues.LANGUES), default=langues.langue())
    a = ap.parse_args()

    langues.definir_langue(a.lang)
    bareme.creer_profils_prets()
    if a.bareme:
        bareme.charger_profil(a.bareme)
    CFG["python"] = analyseur.PYTHON = correcteur.PYTHON = a.python

    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft if a.lang == "ar" else Qt.LeftToRight)
    f = AppCorrecteur()
    for cle, val in (("solution", a.solution), ("tests", a.tests),
                     ("enonce", a.enonce), ("essais", a.essais)):
        if val:
            f.ch[cle].setText(val)
    f.appliquer_reglages()
    f.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
