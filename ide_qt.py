#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ide_qt.py — بيئة تحرير وتصحيح بواجهة PyQt5 (سطح المكتب)
========================================================
نفس محرّك analyseur.py / correcteur.py / langues.py، لكن بنافذة أصلية
بدل المتصفّح، ومع python.exe الحقيقي للترجمة والتنفيذ.

التثبيت:
    pip install PyQt5

الاستعمال:
    python ide_qt.py
    python ide_qt.py -s solution.py -t tests.json -e enonce.txt --lang fr
    python ide_qt.py --python "C:\\Python312\\python.exe"

المزايا:
  • محرّر بأرقام أسطر، تلوين صياغة، تعليم السطر الحالي
  • علامات ❌/⚠️ في الهامش + نقر على الملاحظة يقفز إلى السطر
  • تحليل تلقائي في خيط منفصل (لا تجمّد الواجهة) عبر py_compile الحقيقي
  • تنفيذ بـ QProcess مع stdin ومهلة وزرّ إيقاف وزمن التنفيذ
  • تصحيح ونقطة على 20 مع جدول المحاور والاختبارات والسلّم
  • الحلّ النموذجي محجوب حتى يُطلب، مع diff، ويُسجَّل الاطّلاع
  • سجلّ المحاولات مع النقاط واستعادتها
  • لغة الشرح ar/fr/en، مظهر داكن/فاتح، حجم الخطّ، حفظ التفضيلات

ملاحظة: على أندرويد/Termux حيث يصعب تثبيت PyQt5، استعمل ide.py (نسخة المتصفّح).
"""

import argparse
import datetime
import difflib
import glob
import html
import os
import re
import sys
import tempfile

try:
    from PyQt5.QtCore import (QRect, QSize, Qt, QThread, QTimer, QProcess,
                              QSettings, pyqtSignal)
    from PyQt5.QtGui import (QColor, QFont, QPainter, QSyntaxHighlighter,
                             QTextCharFormat, QTextCursor, QTextFormat, QKeySequence)
    from PyQt5.QtWidgets import (QAction, QApplication, QComboBox, QFileDialog,
                                 QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                                 QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
                                 QTabWidget, QTextBrowser, QTextEdit,
                                 QVBoxLayout, QWidget)
except ImportError:
    sys.exit("PyQt5 غير مثبَّت — نفّذ:  pip install PyQt5\n"
             "(أو استعمل نسخة المتصفّح: python ide.py)")

import langues
from langues import U
import analyseur
from analyseur import (analyser_source, calculer_note, bloc_note, annoter,
                       detecter_python, version_python)
import correcteur
import interpreteurs as itp

CFG = {"solution": None, "tests": None, "enonce": "", "essais": "essais",
       "python": detecter_python(), "vu_solution": False}

MOTS = ("and as assert async await break class continue def del elif else except "
        "False finally for from global if import in is lambda None nonlocal not or "
        "pass raise return True try while with yield").split()
NATIFS = ("print len range int str float list dict set tuple open input sum min max "
          "abs sorted enumerate zip map filter type isinstance").split()

SOMBRE = """
* { font-size: 14px; }
QMainWindow, QWidget { background:#0e1116; color:#e6edf3 }
QPlainTextEdit, QTextBrowser { background:#0d1117; color:#e6edf3;
  border:1px solid #30363d; border-radius:8px; padding:2px;
  selection-background-color:#264f78 }
QTabWidget::pane { border:1px solid #30363d; border-radius:8px; top:-1px }
QTabBar::tab { background:#161b22; color:#adbac7; padding:9px 18px; margin-right:3px;
  min-width:150px;
  border:1px solid #30363d; border-bottom:0; border-top-left-radius:8px;
  border-top-right-radius:8px; font-weight:500 }
QTabBar::tab:selected { background:#58a6ff; color:#04121f; font-weight:700 }
QTabBar::tab:hover:!selected { background:#1f2630; color:#e6edf3 }
QPushButton { background:#21262d; color:#e6edf3; border:1px solid #30363d;
  border-radius:8px; padding:8px 14px; min-height:20px }
QPushButton:hover { border-color:#58a6ff; background:#2b3240 }
QPushButton:disabled { color:#6b7481; border-color:#22272e }
QPushButton#p { background:#238636; color:#fff; font-weight:700; border:0 }
QPushButton#p:hover { background:#2ea043 }
QComboBox, QLineEdit { background:#0d1117; color:#e6edf3; border:1px solid #30363d;
  border-radius:8px; padding:7px 9px; min-height:20px }
QComboBox:focus, QLineEdit:focus { border-color:#58a6ff }
QLabel { color:#adbac7 }
QLabel#note { color:#e6edf3; font-weight:700; font-size:18px; padding:0 10px }
QLabel#titre { color:#e6edf3; font-size:17px; font-weight:700 }
QLabel#sous { color:#768390; font-size:12px }
QGroupBox { border:1px solid #30363d; border-radius:10px; margin-top:16px;
  padding:14px 12px 12px 12px; background:#12171e }
QGroupBox::title { subcontrol-origin:margin; left:14px; padding:2px 8px;
  color:#58a6ff; font-weight:700 }
QTableWidget { background:#0d1117; alternate-background-color:#11161d;
  gridline-color:#22272e; border:1px solid #30363d; border-radius:8px }
QHeaderView::section { background:#161b22; color:#adbac7; padding:8px;
  border:0; border-bottom:1px solid #30363d; font-weight:700 }
QTableWidget::item { padding:6px }
QTableWidget::item:selected { background:#1f6feb; color:#fff }
QProgressBar { border:1px solid #30363d; border-radius:8px; text-align:center;
  background:#0d1117; height:22px; color:#e6edf3 }
QProgressBar::chunk { background:#238636; border-radius:7px }
QStatusBar { background:#161b22; color:#768390 }
QScrollBar:vertical { background:#0d1117; width:11px }
QScrollBar::handle:vertical { background:#30363d; border-radius:5px; min-height:30px }
"""
CLAIR = """
* { font-size: 14px; }
QMainWindow, QWidget { background:#f6f8fa; color:#1f2328 }
QPlainTextEdit, QTextBrowser { background:#fff; color:#1f2328;
  border:1px solid #d0d7de; border-radius:8px; padding:2px }
QTabWidget::pane { border:1px solid #d0d7de; border-radius:8px; top:-1px }
QTabBar::tab { background:#eaeef2; color:#57606a; padding:9px 18px; margin-right:3px;
  min-width:150px;
  border:1px solid #d0d7de; border-bottom:0; border-top-left-radius:8px;
  border-top-right-radius:8px; font-weight:500 }
QTabBar::tab:selected { background:#0969da; color:#fff; font-weight:700 }
QPushButton { background:#f6f8fa; border:1px solid #d0d7de; border-radius:8px;
  padding:8px 14px; min-height:20px }
QPushButton:hover { border-color:#0969da; background:#eef3f8 }
QPushButton#p { background:#1f883d; color:#fff; font-weight:700; border:0 }
QComboBox, QLineEdit { background:#fff; border:1px solid #d0d7de; border-radius:8px;
  padding:7px 9px; min-height:20px }
QLabel#note { font-weight:700; font-size:18px; padding:0 10px }
QLabel#titre { font-size:17px; font-weight:700 }
QLabel#sous { color:#57606a; font-size:12px }
QGroupBox { border:1px solid #d0d7de; border-radius:10px; margin-top:16px;
  padding:14px 12px 12px 12px; background:#fff }
QGroupBox::title { subcontrol-origin:margin; left:14px; padding:2px 8px;
  color:#0969da; font-weight:700 }
QTableWidget { background:#fff; alternate-background-color:#f6f8fa;
  gridline-color:#eaeef2; border:1px solid #d0d7de; border-radius:8px }
QHeaderView::section { background:#eaeef2; color:#57606a; padding:8px; border:0;
  border-bottom:1px solid #d0d7de; font-weight:700 }
QProgressBar { border:1px solid #d0d7de; border-radius:8px; text-align:center;
  background:#fff; height:22px }
QProgressBar::chunk { background:#1f883d; border-radius:7px }
"""


# ---------------------------------------------------------------------------
# 1) تلوين الصياغة
# ---------------------------------------------------------------------------
def _fmt(couleur, gras=False, italique=False):
    f = QTextCharFormat()
    f.setForeground(QColor(couleur))
    if gras:
        f.setFontWeight(QFont.Bold)
    f.setFontItalic(italique)
    return f


class Coloriste(QSyntaxHighlighter):
    def __init__(self, doc, sombre=True):
        super().__init__(doc)
        self.definir(sombre)

    def definir(self, sombre: bool):
        p = dict(kw="#ff7b72", nat="#79c0ff", txt="#a5d6ff", com="#8b949e",
                 num="#79c0ff", fn="#d2a8ff") if sombre else \
            dict(kw="#cf222e", nat="#0550ae", txt="#0a3069", com="#6e7781",
                 num="#0550ae", fn="#8250df")
        self.regles = [
            (re.compile(r"\b(" + "|".join(MOTS) + r")\b"), _fmt(p["kw"], True)),
            (re.compile(r"\b(" + "|".join(NATIFS) + r")\b"), _fmt(p["nat"])),
            (re.compile(r"\b\d+\.?\d*\b"), _fmt(p["num"])),
            (re.compile(r"(?<=\bdef )\w+|(?<=\bclass )\w+"), _fmt(p["fn"], True)),
            (re.compile(r"@\w+"), _fmt(p["fn"])),
            (re.compile(r"'[^'\n]*'|\"[^\"\n]*\""), _fmt(p["txt"])),
            (re.compile(r"#[^\n]*"), _fmt(p["com"], italique=True)),
        ]
        self.f_txt = _fmt(p["txt"])
        self.rehighlight()

    def highlightBlock(self, texte):
        for regex, f in self.regles:
            for m in regex.finditer(texte):
                self.setFormat(m.start(), m.end() - m.start(), f)
        # النصوص متعدّدة الأسطر
        self.setCurrentBlockState(0)
        for delim in ('"""', "'''"):
            debut = 0 if self.previousBlockState() == 1 else texte.find(delim)
            while debut >= 0:
                fin = texte.find(delim, debut + (0 if self.previousBlockState() == 1 else 3))
                if fin < 0:
                    self.setCurrentBlockState(1)
                    self.setFormat(debut, len(texte) - debut, self.f_txt)
                    return
                self.setFormat(debut, fin - debut + 3, self.f_txt)
                debut = texte.find(delim, fin + 3)


# ---------------------------------------------------------------------------
# 2) المحرّر مع هامش الأرقام والعلامات
# ---------------------------------------------------------------------------
class Marge(QWidget):
    def __init__(self, editeur):
        super().__init__(editeur)
        self.ed = editeur

    def sizeHint(self):
        return QSize(self.ed.largeur_marge(), 0)

    def paintEvent(self, e):
        self.ed.peindre_marge(e)


class Editeur(QPlainTextEdit):
    PAIRES = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}

    def __init__(self):
        super().__init__()
        self.marques = {}                    # {ligne: "e" | "w"}
        self.marge = Marge(self)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.blockCountChanged.connect(lambda _: self.maj_marge())
        self.updateRequest.connect(self.defiler_marge)
        self.cursorPositionChanged.connect(self.surligner_ligne)
        self.police(13)
        self.maj_marge()

    def police(self, taille):
        f = QFont("Consolas" if os.name == "nt" else "Monospace", taille)
        f.setStyleHint(QFont.TypeWriter)
        self.setFont(f)
        self.setTabStopWidth(4 * self.fontMetrics().width(" "))
        self.maj_marge()

    # --- الهامش -------------------------------------------------------
    def largeur_marge(self):
        n = max(1, self.blockCount())
        return 22 + self.fontMetrics().width("9") * len(str(n))

    def maj_marge(self):
        self.setViewportMargins(self.largeur_marge(), 0, 0, 0)

    def defiler_marge(self, rect, dy):
        self.marge.scroll(0, dy) if dy else self.marge.update(0, rect.y(),
                                                              self.marge.width(),
                                                              rect.height())
        if rect.contains(self.viewport().rect()):
            self.maj_marge()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self.marge.setGeometry(QRect(cr.left(), cr.top(), self.largeur_marge(), cr.height()))

    def peindre_marge(self, e):
        p = QPainter(self.marge)
        p.fillRect(e.rect(), QColor("#161b22") if self.sombre else QColor("#eaeef2"))
        bloc = self.firstVisibleBlock()
        haut = self.blockBoundingGeometry(bloc).translated(self.contentOffset()).top()
        while bloc.isValid() and haut <= e.rect().bottom():
            no = bloc.blockNumber() + 1
            if bloc.isVisible():
                m = self.marques.get(no)
                p.setPen(QColor("#f85149") if m == "e" else
                         QColor("#d29922") if m == "w" else
                         QColor("#8b98a8"))
                txt = ("● " if m else "") + str(no)
                p.drawText(0, int(haut), self.marge.width() - 6,
                           self.fontMetrics().height(), Qt.AlignRight, txt)
            haut += self.blockBoundingRect(bloc).height()
            bloc = bloc.next()

    sombre = True

    def surligner_ligne(self):
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor("#161b22") if self.sombre else QColor("#eef3f8"))
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel])

    def aller_ligne(self, n):
        c = QTextCursor(self.document().findBlockByNumber(max(0, n - 1)))
        c.select(QTextCursor.LineUnderCursor)
        self.setTextCursor(c)
        self.setFocus()

    # --- الاختصارات ---------------------------------------------------
    def keyPressEvent(self, e):
        c = self.textCursor()
        if e.key() == Qt.Key_Tab and not c.hasSelection():
            c.insertText("    ")
            return
        if e.key() in (Qt.Key_Tab, Qt.Key_Backtab) and c.hasSelection():
            self.indenter(e.key() == Qt.Key_Backtab)
            return
        if e.key() == Qt.Key_Slash and e.modifiers() & Qt.ControlModifier:
            self.commenter()
            return
        if e.text() in self.PAIRES and not c.hasSelection():
            c.insertText(e.text() + self.PAIRES[e.text()])
            c.movePosition(QTextCursor.Left)
            self.setTextCursor(c)
            return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            ligne = c.block().text()[:c.positionInBlock()]
            ind = re.match(r"\s*", ligne).group(0) + ("    " if ligne.rstrip().endswith(":") else "")
            super().keyPressEvent(e)
            self.textCursor().insertText(ind)
            return
        super().keyPressEvent(e)

    def _bloc_selectionne(self):
        c = self.textCursor()
        d, f = sorted((c.selectionStart(), c.selectionEnd()))
        c.setPosition(d)
        p = c.blockNumber()
        c.setPosition(f)
        return p, c.blockNumber()

    def indenter(self, retirer):
        d, f = self._bloc_selectionne()
        c = self.textCursor()
        c.beginEditBlock()
        for i in range(d, f + 1):
            b = self.document().findBlockByNumber(i)
            cur = QTextCursor(b)
            if retirer:
                t = b.text()
                k = len(t) - len(t.lstrip(" "))
                cur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, min(4, k))
                cur.removeSelectedText()
            else:
                cur.insertText("    ")
        c.endEditBlock()

    def commenter(self):
        d, f = self._bloc_selectionne()
        blocs = [self.document().findBlockByNumber(i) for i in range(d, f + 1)]
        off = all(not b.text().strip() or b.text().lstrip().startswith("# ") for b in blocs)
        c = self.textCursor()
        c.beginEditBlock()
        for b in blocs:
            t = b.text()
            if not t.strip():
                continue
            cur = QTextCursor(b)
            k = len(t) - len(t.lstrip(" "))
            cur.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, k)
            if off:
                cur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 2)
                cur.removeSelectedText()
            else:
                cur.insertText("# ")
        c.endEditBlock()


# ---------------------------------------------------------------------------
# 3) خيوط العمل (حتى لا تتجمّد الواجهة)
# ---------------------------------------------------------------------------
class Analyste(QThread):
    fini = pyqtSignal(object, float, str, object)

    def __init__(self, source):
        super().__init__()
        self.source = source

    def run(self):
        probs = analyser_source(self.source, "essai.py", py=CFG["python"])
        note, mention, detail = calculer_note(probs)
        self.fini.emit(probs, note, mention, detail)


class Correcteur(QThread):
    fini = pyqtSignal(object)
    echec = pyqtSignal(str)

    def __init__(self, source):
        super().__init__()
        self.source = source

    def run(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
        f.write(self.source)
        f.close()
        try:
            self.fini.emit(correcteur.corriger(f.name, CFG["solution"], CFG["tests"]))
        except Exception as e:
            self.echec.emit(f"{type(e).__name__}: {e}")
        finally:
            os.unlink(f.name)


class Compatibilite(QThread):
    fini = pyqtSignal(object)

    def __init__(self, source, stdin=""):
        super().__init__()
        self.source, self.stdin = source, stdin

    def run(self):
        self.fini.emit(itp.matrice_compatibilite(self.source, stdin=self.stdin))


# ---------------------------------------------------------------------------
# 4) النافذة
# ---------------------------------------------------------------------------
class Fenetre(QMainWindow):
    def __init__(self):
        super().__init__()
        self.reglages = QSettings("ecole", "ide_qt")
        self.sombre = self.reglages.value("sombre", True, type=bool)
        self.taille = self.reglages.value("police", 13, type=int)
        self.proc = None
        self.construire()
        self.appliquer_theme()
        self.charger_dernier()
        QTimer.singleShot(300, self.analyser)

    # --- البناء -------------------------------------------------------
    def construire(self):
        self.setWindowTitle(f"🐍 {U('titre_app')} — {os.path.basename(CFG['python'])}")
        self.resize(1250, 760)

        self.ed = Editeur()
        self.ed.police(self.taille)
        self.color = Coloriste(self.ed.document(), self.sombre)
        self.minuteur = QTimer(singleShot=True, interval=700)
        self.minuteur.timeout.connect(self.analyser)
        self.ed.textChanged.connect(self.minuteur.start)
        self.ed.cursorPositionChanged.connect(self.maj_etat)

        self.onglets = QTabWidget()
        self.vues = {}
        for cle, titre in (("err", "🔍 " + U("tab_notes")), ("run", "▶ " + U("tab_run")),
                           ("tst", "🧪 " + U("tab_tests")), ("bar", "📊 " + U("tab_bareme")),
                           ("sol", "📘 " + U("tab_sol")), ("enn", "📄 " + U("tab_enonce")),
                           ("his", "🕘 " + U("tab_hist")),
                           ("cmp", "🧩 " + U("tab_compat"))):
            v = QTextBrowser(openLinks=False)
            v.anchorClicked.connect(self.lien)
            self.vues[cle] = v
            self.onglets.addTab(v, titre)
        self.vues["enn"].setPlainText(CFG["enonce"] or "—")
        self.vues["err"].setPlainText(U("msg_analyser"))

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.ed)
        split.addWidget(self.onglets)
        split.setSizes([680, 560])

        barre = QHBoxLayout()
        def bouton(txt, slot, principal=False):
            b = QPushButton(txt.replace("&", "&&"))
            b.clicked.connect(slot)
            if principal:
                b.setObjectName("p")
            barre.addWidget(b)
            return b

        bouton(U("bt_analyser"), self.analyser, True)
        bouton("▶ " + U("bt_executer"), self.executer)
        self.b_stop = bouton("⏹", self.arreter)
        self.b_stop.setEnabled(False)
        bouton("✔ " + U("bt_corriger"), self.corriger)
        bouton("📘 " + U("bt_solution"), self.solution)
        bouton("📂 " + U("bt_ouvrir"), self.ouvrir)
        bouton("💾 " + U("bt_enregistrer"), self.sauver)
        bouton("⬇ " + U("bt_telecharger"), self.exporter)
        bouton("✨ " + U("bt_formater"), self.formater)

        bouton("🧩 " + U("bt_compat"), self.compat)

        self.cpy = QComboBox(minimumWidth=210, toolTip=U("interp_actif"))
        self.cpy.activated.connect(
            lambda: self.changer_python(self.cpy.currentData()))
        barre.addWidget(self.cpy)
        bouton("…", self.choisir_python)
        bouton("⟳", lambda: self.remplir_interpreteurs(True))

        self.stdin = QLineEdit(placeholderText=U("ph_stdin"), maximumWidth=170)
        barre.addWidget(self.stdin)
        self.combo = QComboBox()
        for c, n in langues.LANGUES.items():
            self.combo.addItem(n, c)
        self.combo.setCurrentIndex(list(langues.LANGUES).index(langues.langue()))
        self.combo.currentIndexChanged.connect(self.changer_langue)
        barre.addWidget(self.combo)
        bouton("🌗", self.basculer_theme)
        bouton("A+", lambda: self.zoom(1))
        bouton("A−", lambda: self.zoom(-1))
        barre.addStretch()
        self.lbl_note = QLabel("— / 20", objectName="note")
        barre.addWidget(self.lbl_note)

        haut = QWidget()
        h = QVBoxLayout(haut)
        h.setContentsMargins(6, 6, 6, 6)
        h.addLayout(barre)
        h.addWidget(split)
        self.setCentralWidget(haut)

        self.statusBar().showMessage(f"🐍 {version_python(CFG['python'])}")
        for seq, slot in (("Ctrl+Return", self.analyser), ("F5", self.executer),
                          ("Ctrl+S", self.sauver), ("Ctrl+O", self.ouvrir),
                          ("Ctrl+E", self.corriger)):
            a = QAction(self)
            a.setShortcut(QKeySequence(seq))
            a.triggered.connect(slot)
            self.addAction(a)
        self.historique()
        self.remplir_interpreteurs()

    # --- المفسّرات -----------------------------------------------------
    def remplir_interpreteurs(self, forcer=False):
        self.cpy.blockSignals(True)
        self.cpy.clear()
        actif = os.path.realpath(CFG["python"])
        trouve = False
        for d in itp.scanner(forcer):
            self.cpy.addItem(d["etiquette"], d["chemin"])
            if os.path.realpath(d["chemin"]) == actif:
                self.cpy.setCurrentIndex(self.cpy.count() - 1)
                trouve = True
        if not trouve:
            self.cpy.insertItem(0, itp.info(CFG["python"]).get("etiquette",
                                                               CFG["python"]),
                                CFG["python"])
            self.cpy.setCurrentIndex(0)
        self.cpy.blockSignals(False)

    def choisir_python(self):
        filtre = "python.exe (python*.exe)" if os.name == "nt" else "python (python*)"
        f, _ = QFileDialog.getOpenFileName(self, U("bt_parcourir"), "", filtre)
        if f:
            self.changer_python(f)

    def changer_python(self, chemin):
        v = itp.valider(chemin)
        if not v.get("ok"):
            QMessageBox.warning(self, "⛔", U("interp_ko") + f"\n{chemin}")
            self.remplir_interpreteurs()
            return
        CFG["python"] = v["chemin"]
        analyseur.PYTHON = correcteur.PYTHON = v["chemin"]
        self.setWindowTitle(f"🐍 {U('titre_app')} — {v['etiquette']}")
        self.statusBar().showMessage(f"{U('interp_ok')} : {v['etiquette']}", 4000)
        self.remplir_interpreteurs()
        self.analyser()

    def compat(self):
        self.onglets.setCurrentIndex(7)
        self.vues["cmp"].setPlainText(U("msg_running"))
        self.lancer(Compatibilite(self.ed.toPlainText(), self.stdin.text()),
                    self.montrer_compat)

    def montrer_compat(self, lignes):
        t = (f"<table width='100%' cellpadding='5'><tr>"
             f"<th align='left'>{U('c_interp')}</th><th>{U('c_compile')}</th>"
             f"<th>{U('c_exec')}</th><th>{U('c_ms')}</th>"
             f"<th align='left'>{U('c_sortie')}</th></tr>")
        for x in lignes:
            t += (f"<tr><td>{html.escape(x['etiquette'])}</td>"
                  f"<td align='center'>{'✅' if x['compile'] else '❌'}</td>"
                  f"<td align='center'>{'✅' if x['execute'] else '❌'}</td>"
                  f"<td align='center'>{x['ms']} ms</td>"
                  f"<td><code>{html.escape((x.get('sortie') or x.get('erreur') or '')[:120])}"
                  f"</code></td></tr>")
        self.vues["cmp"].setHtml(t + "</table>")

    # --- المظهر -------------------------------------------------------
    def appliquer_theme(self):
        self.setStyleSheet(SOMBRE if self.sombre else CLAIR)
        self.ed.sombre = self.sombre
        self.color.definir(self.sombre)
        self.ed.surligner_ligne()
        self.ed.marge.update()

    def basculer_theme(self):
        self.sombre = not self.sombre
        self.reglages.setValue("sombre", self.sombre)
        self.appliquer_theme()

    def zoom(self, d):
        self.taille = min(24, max(9, self.taille + d))
        self.reglages.setValue("police", self.taille)
        self.ed.police(self.taille)

    def changer_langue(self):
        langues.definir_langue(self.combo.currentData())
        code = self.ed.toPlainText()
        self.centralWidget().deleteLater()
        self.construire()
        self.appliquer_theme()
        self.ed.setPlainText(code)
        self.analyser()

    # --- الأفعال ------------------------------------------------------
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
        self.vues["err"].setHtml(self.html_problemes(probs) or
                                 f"<p style='color:#3fb950'>✅ {U('aucun')} — {U('compile_ok')}</p>")
        self.vues["bar"].setHtml("<pre>" + html.escape(
            "\n".join(bloc_note(note, mention, detail))) + "</pre>")
        self.statusBar().showMessage(f"🐍 {version_python(CFG['python'])}  ·  {mention}")

    def html_problemes(self, probs):
        out = []
        for p in sorted(probs, key=lambda x: x.ligne):
            coul = "#f85149" if p.gravite == analyseur.ERREUR else "#d29922"
            out.append(
                f"<div style='border-left:3px solid {coul};padding:6px 10px;margin:6px 0'>"
                f"{p.icone} <a href='ligne:{p.ligne}'>{U('ligne')} {p.ligne}</a> "
                f"[{p.code}] {html.escape(p.message)}<br>"
                f"💡 <b>{U('cause')}:</b> {html.escape(p.explication)}<br>"
                f"✅ <b>{U('fix')}:</b> {html.escape(p.correction)}"
                + (f"<br><code>{html.escape(p.ligne_corrigee.strip())}</code>"
                   if p.ligne_corrigee else "") + "</div>")
        return "".join(out)

    def lien(self, url):
        s = url.toString()
        if s.startswith("ligne:"):
            self.ed.aller_ligne(int(s.split(":")[1]))
        elif s.startswith("essai:"):
            self.restaurer(s.split(":", 1)[1])

    def executer(self):
        self.onglets.setCurrentIndex(1)
        self.vues["run"].setPlainText(U("msg_running"))
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                               encoding="utf-8")
        self.tmp.write(self.ed.toPlainText())
        self.tmp.close()
        self.debut = datetime.datetime.now()
        self.sortie = ""
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.lire_proc)
        self.proc.finished.connect(self.fin_proc)
        self.proc.start(CFG["python"], ["-u", self.tmp.name])
        if self.stdin.text():
            self.proc.write((self.stdin.text() + "\n").encode())
        self.proc.closeWriteChannel()
        self.b_stop.setEnabled(True)
        QTimer.singleShot(10000, self.arreter_si_long)

    def lire_proc(self):
        self.sortie += bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        self.vues["run"].setPlainText(self.sortie)

    def fin_proc(self, code, _):
        ms = int((datetime.datetime.now() - self.debut).total_seconds() * 1000)
        self.vues["run"].setPlainText(self.sortie + f"\n[exit {code} · {ms} ms]")
        self.b_stop.setEnabled(False)
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def arreter(self):
        if self.proc and self.proc.state():
            self.proc.kill()

    def arreter_si_long(self):
        if self.proc and self.proc.state():
            self.proc.kill()
            self.vues["run"].setPlainText(self.sortie + "\n⛔ " + U("timeout", s=10))

    def corriger(self):
        if not CFG["solution"]:
            QMessageBox.information(self, "—", U("msg_no_sol"))
            return
        self.onglets.setCurrentIndex(2)
        self.vues["tst"].setPlainText(U("msg_running"))
        self.lancer(Correcteur(self.ed.toPlainText()), self.montrer_correction,
                    lambda m: self.vues["tst"].setPlainText(m))

    def montrer_correction(self, r):
        self.lbl_note.setText(f"{r['note']} / 20")
        t = (f"<table width='100%' cellpadding='5'>"
             f"<tr><th align='left'>{U('axe')}</th><th>{U('note')}</th><th>{U('sur')}</th></tr>"
             f"<tr><td>{U('ax_qualite')}</td><td align='center'>{r['qualite']}</td><td align='center'>6</td></tr>"
             f"<tr><td>{U('ax_tests')}</td><td align='center'>{r['tests']}</td><td align='center'>10</td></tr>"
             f"<tr><td>{U('ax_structure')}</td><td align='center'>{r['structure']}</td><td align='center'>4</td></tr>"
             f"<tr><td><b>{U('total')}</b></td><td align='center'><b>{r['note']}</b></td>"
             f"<td align='center'><b>20</b></td></tr></table><hr>")
        for x in r["resultats"]:
            coul = "#3fb950" if x["reussi"] else "#f85149"
            t += (f"<div style='border-left:3px solid {coul};padding:5px 10px;margin:5px 0'>"
                  f"{'✅' if x['reussi'] else '❌'} {html.escape(str(x['nom']))}")
            if not x["reussi"]:
                t += (f"<br>{U('attendu')}: <code>{html.escape(str(x['attendu']))}</code>"
                      f"<br>{U('obtenu')}: <code>{html.escape(str(x['obtenu']))}</code>")
            t += "</div>"
        for m in r["remarques"]:
            t += f"<div style='padding:4px 10px'>{html.escape(m)}</div>"
        self.vues["tst"].setHtml(t)
        self.vues["err"].setHtml(self.html_problemes(r["problemes"]))
        self.journaliser(r["note"], "correction")
        self.historique()

    def solution(self):
        if not CFG["solution"]:
            QMessageBox.information(self, "—", U("msg_no_sol"))
            return
        if QMessageBox.question(self, "📘", U("msg_conf_sol")) != QMessageBox.Yes:
            return
        CFG["vu_solution"] = True
        src = open(CFG["solution"], encoding="utf-8").read()
        diff = "\n".join(difflib.unified_diff(
            self.ed.toPlainText().splitlines(), src.splitlines(), lineterm="", n=2))
        self.vues["sol"].setHtml(f"<pre>{html.escape(src)}</pre><hr><h4>🔀 {U('diff')}</h4>"
                                 f"<pre>{html.escape(diff)}</pre>")
        self.onglets.setCurrentIndex(4)
        self.journaliser("—", "vue-solution")
        self.historique()

    # --- الملفات والسجلّ ------------------------------------------------
    def ouvrir(self):
        f, _ = QFileDialog.getOpenFileName(self, U("bt_ouvrir"), "", "Python (*.py)")
        if f:
            self.ed.setPlainText(open(f, encoding="utf-8").read())
            self.analyser()

    def sauver(self):
        nom = self.journaliser("—", "sauvegarde")
        self.statusBar().showMessage(f"{U('msg_saved')} — {nom}", 4000)
        self.historique()

    def exporter(self):
        f, _ = QFileDialog.getSaveFileName(self, U("bt_telecharger"),
                                           "essai_annote.py", "Python (*.py)")
        if not f:
            return
        src = self.ed.toPlainText()
        probs = analyser_source(src, "essai.py", py=CFG["python"])
        open(f, "w", encoding="utf-8").write(annoter(src.splitlines(), probs, "essai.py"))
        self.statusBar().showMessage(f"💾 {f}", 4000)

    def formater(self):
        t = self.ed.toPlainText().replace("\t", "    ")
        t = re.sub(r"[ \t]+$", "", t, flags=re.M)
        t = re.sub(r"\n{3,}", "\n\n", t).rstrip() + "\n"
        self.ed.setPlainText(t)

    def journaliser(self, note, etiquette):
        os.makedirs(CFG["essais"], exist_ok=True)
        h = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nom = f"essai_{h}.py"
        open(os.path.join(CFG["essais"], nom), "w", encoding="utf-8").write(
            f"# note={note} date={h} vu_solution={CFG['vu_solution']} ({etiquette})\n"
            + self.ed.toPlainText())
        self.reglages.setValue("dernier", self.ed.toPlainText())
        return nom

    def historique(self):
        lignes = []
        for c in sorted(glob.glob(os.path.join(CFG["essais"], "essai_*.py")),
                        reverse=True)[:30]:
            e = open(c, encoding="utf-8").readline()
            note = re.search(r"note=(\S+)", e)
            d = re.search(r"date=(\d{8}_\d{6})", e)
            d = d.group(1) if d else ""
            lignes.append(
                f"<div style='padding:4px 8px'>"
                f"<a href='essai:{os.path.basename(c)}'>{os.path.basename(c)}</a> — "
                f"<b>{note.group(1) if note else '—'}</b>/20 · "
                f"{d[6:8]}/{d[4:6]} {d[9:11]}:{d[11:13]}"
                f"{' · 📘' if 'vu_solution=True' in e else ''}</div>")
        self.vues["his"].setHtml("".join(lignes) or U("msg_vide"))

    def restaurer(self, nom):
        c = os.path.join(CFG["essais"], os.path.basename(nom))
        if os.path.isfile(c):
            txt = open(c, encoding="utf-8").read().split("\n", 1)
            self.ed.setPlainText(txt[1] if len(txt) > 1 else "")
            self.analyser()

    def charger_dernier(self):
        self.ed.setPlainText(self.reglages.value("dernier", "", type=str)
                             or f"# {U('titre_app')}\n")

    def maj_etat(self):
        c = self.ed.textCursor()
        self.statusBar().showMessage(
            f"{U('ligne')} {c.blockNumber() + 1}:{c.positionInBlock() + 1}  ·  "
            f"{self.ed.blockCount()} {U('st_lignes')}  ·  🐍 {os.path.basename(CFG['python'])}")

    def closeEvent(self, e):
        self.reglages.setValue("dernier", self.ed.toPlainText())
        super().closeEvent(e)


def main():
    ap = argparse.ArgumentParser(description="IDE PyQt5 للتلميذ")
    ap.add_argument("-s", "--solution")
    ap.add_argument("-t", "--tests")
    ap.add_argument("-e", "--enonce")
    ap.add_argument("--essais", default="essais")
    ap.add_argument("--python", default=detecter_python())
    ap.add_argument("--lang", choices=list(langues.LANGUES), default=langues.langue())
    a = ap.parse_args()

    langues.definir_langue(a.lang)
    CFG.update(solution=a.solution, tests=a.tests, essais=a.essais, python=a.python)
    analyseur.PYTHON = a.python
    correcteur.PYTHON = a.python
    if a.enonce and os.path.isfile(a.enonce):
        CFG["enonce"] = open(a.enonce, encoding="utf-8").read()

    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft if a.lang == "ar" else Qt.LeftToRight)
    f = Fenetre()
    f.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
