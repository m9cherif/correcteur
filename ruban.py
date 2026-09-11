#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ruban.py — قائمة رئيسية + شريط أزرار لكل قائمة (نمط Ribbon)
============================================================
كل «قائمة» تظهر في شريط علوي؛ عند اختيارها يظهر تحتها صفّ أزرارها.
وفي الوقت نفسه تُبنى قائمة نظام حقيقية (QMenuBar) بنفس الأفعال
والاختصارات، حتى يعمل التطبيق بالفأرة أو بلوحة المفاتيح.

    ruban = Ruban(fenetre)
    g = ruban.menu("📄 Fichier")
    g.bouton("Nouveau", self.nouveau, raccourci="Ctrl+N", principal=True)
    g.widget(mon_combo)
    g.separateur()
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (QAction, QButtonGroup, QFrame, QHBoxLayout,
                             QPushButton, QStackedWidget, QToolButton,
                             QVBoxLayout, QWidget)

STYLE = """
QWidget#barreMenus { background:#161b22; border-bottom:1px solid #30363d }
QToolButton { background:transparent; border:0; padding:9px 18px; color:#adbac7;
  font-size:14px; font-weight:600; border-radius:0 }
QToolButton:hover { background:#1f2630; color:#e6edf3 }
QToolButton:checked { background:#0d1117; color:#58a6ff;
  border-bottom:3px solid #58a6ff }
QWidget#groupe { background:#0d1117; border-bottom:1px solid #30363d }
"""
STYLE_CLAIR = """
QWidget#barreMenus { background:#eaeef2; border-bottom:1px solid #d0d7de }
QToolButton { background:transparent; border:0; padding:9px 18px; color:#57606a;
  font-size:14px; font-weight:600 }
QToolButton:hover { background:#dde3ea; color:#1f2328 }
QToolButton:checked { background:#fff; color:#0969da; border-bottom:3px solid #0969da }
QWidget#groupe { background:#fff; border-bottom:1px solid #d0d7de }
"""


class Groupe(QWidget):
    """صفّ الأزرار الخاصّ بقائمة واحدة."""

    def __init__(self, menu_systeme, fenetre):
        super().__init__()
        self.setObjectName("groupe")
        self.menu = menu_systeme
        self.fenetre = fenetre
        self.h = QHBoxLayout(self)
        self.h.setContentsMargins(10, 7, 10, 7)
        self.h.setSpacing(7)
        self.h.addStretch()

    def _inserer(self, w):
        self.h.insertWidget(self.h.count() - 1, w)

    def bouton(self, texte, slot, raccourci=None, principal=False, info=""):
        b = QPushButton(texte.replace("&", "&&"))
        b.clicked.connect(slot)
        if principal:
            b.setObjectName("p")
        if info or raccourci:
            b.setToolTip(f"{info} {'(' + raccourci + ')' if raccourci else ''}".strip())
        self._inserer(b)
        # نفس الفعل في قائمة النظام
        a = QAction(texte.replace("&", "&&"), self.fenetre)
        if raccourci:
            a.setShortcut(QKeySequence(raccourci))
            a.setShortcutContext(Qt.ApplicationShortcut)
        a.triggered.connect(slot)
        self.menu.addAction(a)
        self.fenetre.addAction(a)
        return b

    def widget(self, w, etirer=0):
        self.h.insertWidget(self.h.count() - 1, w, etirer)
        return w

    def separateur(self):
        s = QFrame()
        s.setFrameShape(QFrame.VLine)
        s.setStyleSheet("color:#30363d")
        self._inserer(s)
        self.menu.addSeparator()


class Ruban(QWidget):
    def __init__(self, fenetre):
        super().__init__()
        self.fenetre = fenetre
        self.setStyleSheet(STYLE)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.barre = QWidget(objectName="barreMenus")
        self.hb = QHBoxLayout(self.barre)
        self.hb.setContentsMargins(4, 0, 4, 0)
        self.hb.setSpacing(0)
        self.hb.addStretch()
        self.groupes = QStackedWidget()
        v.addWidget(self.barre)
        v.addWidget(self.groupes)

        self.gr = QButtonGroup(self)
        self.gr.setExclusive(True)
        self.gr.buttonClicked.connect(
            lambda b: self.groupes.setCurrentIndex(self.gr.id(b)))

    def menu(self, titre: str) -> Groupe:
        onglet = QToolButton(text=titre.replace("&", "&&"), checkable=True)
        onglet.setCursor(Qt.PointingHandCursor)
        self.hb.insertWidget(self.hb.count() - 1, onglet)
        g = Groupe(self.fenetre.menuBar().addMenu(titre.replace("&", "&&")),
                   self.fenetre)
        self.gr.addButton(onglet, self.groupes.count())
        self.groupes.addWidget(g)
        if self.groupes.count() == 1:
            onglet.setChecked(True)
        return g

    def theme(self, sombre: bool):
        self.setStyleSheet(STYLE if sombre else STYLE_CLAIR)
