#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
atelier.py — التطبيق 1 : بيئة تطوير بايثون (نمط Thonny + تحسينات)
==================================================================
موجَّه للتلميذ الذي يكتب ويجرّب، لا للتصحيح والتنقيط (ذلك في correcteur_app.py).

الواجهة: قائمة رئيسية علوية، وتحت كل قائمة صفّ أزرارها (ruban.py).
    📄 Fichier · ✏ Édition · ▶ Exécution · 🔍 Assistant ·
    🐍 Interpréteur · 👁 Affichage · ❓ Aide

المزايا مقارنةً بـ Thonny:
  • تبويبات لعدّة ملفّات في وقت واحد
  • صدفة تفاعلية (REPL) حقيقية داخل التطبيق + تشغيل الملف داخلها
  • لوحة «المتغيّرات» تُحدَّث بعد كل تنفيذ
  • «المساعد» يشرح الأخطاء بالعربية/الفرنسية/الإنجليزية مع التصحيح والنقطة /20
  • تبديل مفسّر بايثون (python.exe) لحظيًّا + اختبار الكود على كل النسخ المثبَّتة
  • مظهر داكن/فاتح، حجم خطّ، حفظ الجلسة

    pip install PyQt5
    python atelier.py [fichier.py]
"""

import argparse
import html
import json
import os
import re
import sys
import tempfile

from PyQt5.QtCore import Qt, QProcess, QSettings, QTimer
from PyQt5.QtWidgets import (QApplication, QComboBox, QFileDialog, QHeaderView,
                             QLabel, QLineEdit, QMainWindow, QMessageBox,
                             QPlainTextEdit, QSplitter, QTabWidget, QTableWidget,
                             QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

import langues
from langues import U
import analyseur
from analyseur import analyser_source, calculer_note, bloc_note, version_python
import interpreteurs as itp
import bareme
import ide_qt
from ide_qt import Editeur, Coloriste, Analyste, Compatibilite, SOMBRE, CLAIR
from ruban import Ruban

VARS = ('print("@@VARS@@" + __import__("json").dumps('
        '{k: repr(v)[:150] + " | " + type(v).__name__ '
        'for k, v in list(globals().items()) '
        'if not k.startswith("_") and not isinstance(v, type(__import__("json")))}))')


class Atelier(QMainWindow):
    def __init__(self, fichiers=None):
        super().__init__()
        self.reg = QSettings("ecole", "atelier")
        self.sombre = self.reg.value("sombre", True, type=bool)
        self.taille = self.reg.value("police", 13, type=int)
        self.shell = None
        self.tampon = ""
        self.setWindowTitle("🐍 Atelier Python")
        self.resize(1240, 780)
        self.construire()
        self.appliquer_theme()
        for f in (fichiers or []):
            self.ouvrir(f)
        if self.onglets.count() == 0:
            self.nouveau()
        self.demarrer_shell()

    # ------------------------------------------------------------------
    def construire(self):
        self.ruban = Ruban(self)

        g = self.ruban.menu("📄 " + U("tab_config").split()[0] if False else "📄 Fichier")
        g.bouton("🆕 Nouveau", self.nouveau, "Ctrl+N", principal=True)
        g.bouton("📂 " + U("bt_ouvrir"), self.dialogue_ouvrir, "Ctrl+O")
        g.bouton("💾 " + U("bt_enregistrer"), self.enregistrer, "Ctrl+S")
        g.bouton("💾 Enregistrer sous…", self.enregistrer_sous, "Ctrl+Shift+S")
        g.separateur()
        g.bouton("✖ Fermer l'onglet", self.fermer_onglet, "Ctrl+W")
        g.bouton("🚪 Quitter", self.close, "Ctrl+Q")

        g = self.ruban.menu("✏ Édition")
        g.bouton("↶ Annuler", lambda: self.ed() and self.ed().undo(), "Ctrl+Z")
        g.bouton("↷ Rétablir", lambda: self.ed() and self.ed().redo(), "Ctrl+Y")
        g.separateur()
        g.bouton("# Commenter", lambda: self.ed() and self.ed().commenter(), "Ctrl+/")
        g.bouton("→ Indenter", lambda: self.ed() and self.ed().indenter(False))
        g.bouton("← Désindenter", lambda: self.ed() and self.ed().indenter(True))
        g.bouton("✨ " + U("bt_formater"), self.formater)
        g.separateur()
        self.recherche = QLineEdit(placeholderText="🔎 Rechercher…", maximumWidth=190)
        self.recherche.returnPressed.connect(self.chercher)
        g.widget(self.recherche)

        g = self.ruban.menu("▶ Exécution")
        g.bouton("▶ " + U("bt_executer"), self.executer, "F5", principal=True)
        g.bouton("⏎ Exécuter la sélection", self.executer_selection, "F9")
        g.bouton("⏹ Interrompre", self.interrompre, "Ctrl+C")
        g.bouton("♻ Redémarrer la console", self.demarrer_shell, "Ctrl+F5")
        g.separateur()
        g.bouton("🔄 Variables", self.rafraichir_vars)

        g = self.ruban.menu("🔍 Assistant")
        g.bouton("🔍 " + U("bt_analyser"), self.analyser, "Ctrl+Return", principal=True)
        g.bouton("🧩 " + U("bt_compat"), self.compat)
        g.bouton("⬇ " + U("bt_telecharger"), self.exporter_annote)
        g.bouton("⚖ " + U("tab_bareme"), self.editer_bareme, "Ctrl+B")
        g.separateur()
        self.lbl_note = QLabel("— / 20", objectName="note")
        g.widget(self.lbl_note)

        g = self.ruban.menu("🐍 " + U("c_interp"))
        self.cpy = QComboBox(minimumWidth=230)
        self.cpy.activated.connect(lambda: self.changer_python(self.cpy.currentData()))
        g.widget(self.cpy)
        g.bouton("… " + U("bt_parcourir"), self.parcourir_python)
        g.bouton("⟳ " + U("bt_scan"), lambda: self.remplir_python(True))
        self.lbl_py = QLabel("—")
        g.widget(self.lbl_py, 1)

        g = self.ruban.menu("👁 Affichage")
        g.bouton("🌗 Thème", self.basculer_theme)
        g.bouton("A+", lambda: self.zoom(1), "Ctrl++")
        g.bouton("A−", lambda: self.zoom(-1), "Ctrl+-")
        g.separateur()
        self.combo_lg = QComboBox()
        for c, n in langues.LANGUES.items():
            self.combo_lg.addItem(n, c)
        self.combo_lg.setCurrentIndex(list(langues.LANGUES).index(langues.langue()))
        self.combo_lg.currentIndexChanged.connect(self.changer_langue)
        g.widget(self.combo_lg)

        g = self.ruban.menu("❓ Aide")
        g.bouton("⌨ Raccourcis", lambda: QMessageBox.information(
            self, "⌨", "Ctrl+N/O/S · F5 exécuter · F9 sélection · Ctrl+Return analyser\n"
                       "Ctrl+/ commenter · Ctrl+W fermer · Ctrl+F5 redémarrer console"))
        g.bouton("ℹ À propos", lambda: QMessageBox.information(
            self, "ℹ", "Atelier Python — écrire, exécuter, comprendre.\n"
                       "Correction et notation : correcteur_app.py"))

        # --- المحرّرات ---
        self.onglets = QTabWidget(tabsClosable=True, movable=True)
        self.onglets.tabCloseRequested.connect(self.fermer_onglet)
        self.onglets.currentChanged.connect(lambda _: self.analyser())

        # --- اللوحات السفلية ---
        self.console = QPlainTextEdit(readOnly=True)
        self.entree = QLineEdit(placeholderText=">>>")
        self.entree.returnPressed.connect(self.envoyer)
        boite = QWidget()
        vb = QVBoxLayout(boite)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.addWidget(self.console)
        vb.addWidget(self.entree)

        self.vars = QTableWidget(0, 3)
        self.vars.setHorizontalHeaderLabels(["Variable", "Valeur", "Type"])
        self.vars.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.vars.verticalHeader().setVisible(False)

        self.assistant = QTextBrowser(openLinks=False)
        self.assistant.anchorClicked.connect(
            lambda u: self.ed().aller_ligne(int(u.toString().split(":")[1])))
        self.compatv = QTextBrowser()

        self.bas = QTabWidget()
        self.bas.addTab(boite, "🖵 Console")
        self.bas.addTab(self.vars, "📦 Variables")
        self.bas.addTab(self.assistant, "🔍 " + U("tab_notes"))
        self.bas.addTab(self.compatv, "🧩 " + U("tab_compat"))

        split = QSplitter(Qt.Vertical)
        split.addWidget(self.onglets)
        split.addWidget(self.bas)
        split.setSizes([470, 300])

        centre = QWidget()
        v = QVBoxLayout(centre)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.ruban)
        v.addWidget(split, 1)
        self.setCentralWidget(centre)

        self.minuteur = QTimer(singleShot=True, interval=800)
        self.minuteur.timeout.connect(self.analyser)
        self.remplir_python()
        self.statusBar().showMessage(U("pret"))

    # --- أدوات مساعدة -------------------------------------------------
    def lancer(self, th, slot):
        """يُبقي مرجعًا للخيط حتى ينتهي (وإلّا انهار التطبيق)."""
        self._th = getattr(self, "_th", [])
        self._th.append(th)
        th.fini.connect(slot)
        th.finished.connect(lambda: self._th.remove(th) if th in self._th else None)
        th.start()

    def ed(self):
        return self.onglets.currentWidget()

    def nouveau(self, chemin=None, contenu=""):
        e = Editeur()
        e.chemin = chemin
        e.police(self.taille)
        e.col = Coloriste(e.document(), self.sombre)
        e.sombre = self.sombre
        e.setPlainText(contenu)
        e.textChanged.connect(self.minuteur.start)
        e.cursorPositionChanged.connect(self.maj_etat)
        i = self.onglets.addTab(e, os.path.basename(chemin) if chemin else "sans-titre.py")
        self.onglets.setCurrentIndex(i)
        return e

    def dialogue_ouvrir(self):
        f, _ = QFileDialog.getOpenFileName(self, U("bt_ouvrir"), "", "Python (*.py)")
        if f:
            self.ouvrir(f)

    def ouvrir(self, chemin):
        self.nouveau(chemin, open(chemin, encoding="utf-8").read())
        self.analyser()

    def enregistrer(self):
        e = self.ed()
        if not e:
            return None
        if not getattr(e, "chemin", None):
            return self.enregistrer_sous()
        open(e.chemin, "w", encoding="utf-8").write(e.toPlainText())
        self.statusBar().showMessage("💾 " + e.chemin, 4000)
        return e.chemin

    def enregistrer_sous(self):
        e = self.ed()
        f, _ = QFileDialog.getSaveFileName(self, U("bt_enregistrer"),
                                           getattr(e, "chemin", "") or "script.py",
                                           "Python (*.py)")
        if not f:
            return None
        e.chemin = f
        open(f, "w", encoding="utf-8").write(e.toPlainText())
        self.onglets.setTabText(self.onglets.currentIndex(), os.path.basename(f))
        return f

    def fermer_onglet(self, i=None):
        i = self.onglets.currentIndex() if i in (None, False) else i
        if self.onglets.count() > 1:
            self.onglets.removeTab(i)
        else:
            self.ed().setPlainText("")

    def formater(self):
        e = self.ed()
        t = e.toPlainText().replace("\t", "    ")
        t = re.sub(r"[ \t]+$", "", t, flags=re.M)
        e.setPlainText(re.sub(r"\n{3,}", "\n\n", t).rstrip() + "\n")

    def chercher(self):
        e = self.ed()
        if e and self.recherche.text():
            if not e.find(self.recherche.text()):
                e.moveCursor(e.textCursor().Start)
                e.find(self.recherche.text())

    # --- المفسّر --------------------------------------------------------
    def remplir_python(self, forcer=False):
        self.cpy.blockSignals(True)
        self.cpy.clear()
        for d in itp.scanner(forcer):
            self.cpy.addItem(d["etiquette"], d["chemin"])
        if not self.cpy.count():
            self.cpy.addItem(sys.executable, sys.executable)
        actif = os.path.realpath(ide_qt.CFG["python"])
        for i in range(self.cpy.count()):
            if os.path.realpath(self.cpy.itemData(i)) == actif:
                self.cpy.setCurrentIndex(i)
        self.cpy.blockSignals(False)
        self.maj_lbl_py()

    def maj_lbl_py(self):
        d = itp.info(ide_qt.CFG["python"])
        self.lbl_py.setText(f"{ide_qt.CFG['python']}  ·  pip {'✅' if d.get('pip') else '❌'}"
                            f"{'  ·  venv' if d.get('venv') else ''}")

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
        ide_qt.CFG["python"] = analyseur.PYTHON = v["chemin"]
        self.statusBar().showMessage(f"{U('interp_ok')} : {v['etiquette']}", 4000)
        self.remplir_python()
        self.demarrer_shell()
        self.analyser()

    # --- الصدفة التفاعلية ------------------------------------------------
    def demarrer_shell(self):
        if self.shell and self.shell.state():
            self.shell.kill()
            self.shell.waitForFinished(1500)
        self.console.clear()
        self.tampon = ""
        self.shell = QProcess(self)
        self.shell.setProcessChannelMode(QProcess.MergedChannels)
        self.shell.readyReadStandardOutput.connect(self.lire_shell)
        self.shell.start(ide_qt.CFG["python"], ["-i", "-u", "-q"])
        self.console.appendPlainText(f"🐍 {version_python(ide_qt.CFG['python'])} — "
                                     f"{U('pret')}\n")

    def lire_shell(self):
        txt = bytes(self.shell.readAllStandardOutput()).decode("utf-8", "replace")
        garde = []
        for l in txt.splitlines(True):
            if l.startswith("@@VARS@@"):
                try:
                    self.montrer_vars(json.loads(l[8:]))
                except Exception:
                    pass
            else:
                garde.append(l)
        if garde:
            self.console.moveCursor(self.console.textCursor().End)
            self.console.insertPlainText("".join(garde))
            self.console.ensureCursorVisible()

    def envoyer(self, commande=None, silencieux=False):
        """بلا وسيط: يرسل ما في حقل الإدخال. بوسيط: يرسل الأمر مباشرة."""
        cmd = self.entree.text() if commande is None else commande
        if commande is None:
            self.console.appendPlainText(">>> " + cmd)
            self.entree.clear()
        if self.shell and self.shell.state():
            self.shell.write((cmd + "\n").encode())

    def executer(self):
        e = self.ed()
        if not e:
            return
        chemin = getattr(e, "chemin", None)
        if not chemin:
            t = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                            encoding="utf-8")
            t.write(e.toPlainText())
            t.close()
            chemin = t.name
        else:
            self.enregistrer()
        self.bas.setCurrentIndex(0)
        self.console.appendPlainText(f"\n%Run {os.path.basename(chemin)}")
        self.envoyer(f'exec(compile(open(r"{chemin}", encoding="utf-8").read(), '
                     f'r"{chemin}", "exec"), globals())', silencieux=True)
        QTimer.singleShot(900, self.rafraichir_vars)

    def executer_selection(self):
        e = self.ed()
        sel = e.textCursor().selectedText().replace("\u2029", "\n") if e else ""
        for l in (sel or e.textCursor().block().text()).splitlines():
            self.console.appendPlainText(">>> " + l)
            self.envoyer(l, silencieux=True)
        QTimer.singleShot(600, self.rafraichir_vars)

    def interrompre(self):
        if self.shell and self.shell.state():
            self.shell.kill()
            self.console.appendPlainText("\n⏹ interrompu")
            QTimer.singleShot(400, self.demarrer_shell)

    def rafraichir_vars(self):
        self.envoyer(VARS, silencieux=True)

    def montrer_vars(self, d):
        self.vars.setRowCount(0)
        for k, v in sorted(d.items()):
            val, _, typ = v.rpartition(" | ")
            i = self.vars.rowCount()
            self.vars.insertRow(i)
            for j, x in enumerate((k, val, typ)):
                self.vars.setItem(i, j, QTableWidgetItem(x))

    def editer_bareme(self):
        import editeur_bareme
        if editeur_bareme.ouvrir(self):
            self.analyser()

    # --- المساعد --------------------------------------------------------
    def analyser(self):
        e = self.ed()
        if not e:
            return
        self.lancer(Analyste(e.toPlainText()), self.montrer_analyse)

    def montrer_analyse(self, probs, note, mention, detail):
        e = self.ed()
        if not e:
            return
        e.marques = {}
        for p in probs:
            if e.marques.get(p.ligne) != "e":
                e.marques[p.ligne] = "e" if p.gravite == analyseur.ERREUR else "w"
        e.marge.update()
        self.lbl_note.setText(f"{note} / 20")
        corps = "".join(
            f"<div style='border-left:3px solid "
            f"{'#f85149' if p.gravite == analyseur.ERREUR else '#d29922'};"
            f"padding:6px 10px;margin:6px 0'>{p.icone} "
            f"<a href='ligne:{p.ligne}'>{U('ligne')} {p.ligne}</a> [{p.code}] "
            f"{html.escape(p.message)}<br>💡 <b>{U('cause')}:</b> "
            f"{html.escape(p.explication)}<br>✅ <b>{U('fix')}:</b> "
            f"{html.escape(p.correction)}</div>"
            for p in sorted(probs, key=lambda x: x.ligne))
        self.assistant.setHtml(corps or
                               f"<p style='color:#3fb950'>✅ {U('aucun')}</p>")
        self.compatv.setProperty("bareme", "\n".join(bloc_note(note, mention, detail)))

    def compat(self):
        self.bas.setCurrentIndex(3)
        self.compatv.setPlainText(U("msg_running"))
        self.lancer(Compatibilite(self.ed().toPlainText()), self.montrer_compat)

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
        self.compatv.setHtml(t + "</table>")

    def exporter_annote(self):
        e = self.ed()
        f, _ = QFileDialog.getSaveFileName(self, U("bt_telecharger"),
                                           "script_annote.py", "Python (*.py)")
        if not f:
            return
        src = e.toPlainText()
        probs = analyser_source(src, "script.py", py=ide_qt.CFG["python"])
        open(f, "w", encoding="utf-8").write(
            analyseur.annoter(src.splitlines(), probs, "script.py"))
        self.statusBar().showMessage(f"💾 {f}", 4000)

    # --- المظهر واللغة --------------------------------------------------
    def appliquer_theme(self):
        self.setStyleSheet(SOMBRE if self.sombre else CLAIR)
        self.ruban.theme(self.sombre)
        for i in range(self.onglets.count()):
            e = self.onglets.widget(i)
            e.sombre = self.sombre
            e.col.definir(self.sombre)
            e.surligner_ligne()
            e.marge.update()

    def basculer_theme(self):
        self.sombre = not self.sombre
        self.reg.setValue("sombre", self.sombre)
        self.appliquer_theme()

    def zoom(self, d):
        self.taille = min(24, max(9, self.taille + d))
        self.reg.setValue("police", self.taille)
        for i in range(self.onglets.count()):
            self.onglets.widget(i).police(self.taille)

    def changer_langue(self):
        langues.definir_langue(self.combo_lg.currentData())
        QMessageBox.information(self, "🌐", U("interp_ok"))
        self.analyser()

    def maj_etat(self):
        e = self.ed()
        if not e:
            return
        c = e.textCursor()
        self.statusBar().showMessage(
            f"{getattr(e, 'chemin', None) or 'sans-titre.py'}   ·   "
            f"{U('ligne')} {c.blockNumber() + 1}:{c.positionInBlock() + 1}   ·   "
            f"🐍 {os.path.basename(ide_qt.CFG['python'])}")

    def closeEvent(self, e):
        if self.shell and self.shell.state():
            self.shell.kill()
        for th in list(getattr(self, "_th", [])):
            th.wait(3000)
        super().closeEvent(e)


def main():
    ap = argparse.ArgumentParser(description="Atelier Python (IDE)")
    ap.add_argument("fichiers", nargs="*")
    ap.add_argument("--python", default=analyseur.detecter_python())
    ap.add_argument("--lang", choices=list(langues.LANGUES), default=langues.langue())
    a = ap.parse_args()
    langues.definir_langue(a.lang)
    bareme.creer_profils_prets()
    ide_qt.CFG["python"] = analyseur.PYTHON = a.python

    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft if a.lang == "ar" else Qt.LeftToRight)
    f = Atelier(a.fichiers)
    f.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
