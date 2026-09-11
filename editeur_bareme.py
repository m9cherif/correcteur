#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
editeur_bareme.py — محرّر السلّم بواجهة رسومية (PyQt5)
======================================================
نافذة واحدة يعدّل فيها الأستاذ كل شيء بلا لمس الكود:
  • ملفّ التعريف (Standard / Débutant / Examen / Algorithmique / ملفّ خاصّ)
  • النقطة القصوى، التسامح، «خطأ الصياغة قاتل»، حدود التقديرات
  • وزن كل محور (المجموع يجب أن يساوي النقطة القصوى — يُعرَض بالأخضر/الأحمر)
  • جدول القواعد: تفعيل/تعطيل، الخصم لكل حالة، السقف
  • زرّ «معاينة» يعيد حساب نقاط القسم بالسلّم الجديد ويعرض الفرق

    from editeur_bareme import ouvrir
    ouvrir(parent, resultats)     # resultats اختيارية للمعاينة
"""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QSpinBox, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

import bareme
import langues
from langues import U, titre


class EditeurBareme(QDialog):
    def __init__(self, parent=None, resultats=None):
        super().__init__(parent)
        self.resultats = resultats or []
        self.setWindowTitle("⚖ " + U("tab_bareme"))
        self.resize(880, 720)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self._initial = json_dump(bareme.actif())   # للاسترجاع عند الإلغاء
        self._construire()
        self._remplir(bareme.actif())

    # ------------------------------------------------------------------
    def _construire(self):
        v = QVBoxLayout(self)

        # --- ملفّ التعريف ---
        g0 = QGroupBox("📁 " + U("tab_config"))
        h0 = QHBoxLayout(g0)
        self.combo = QComboBox(minimumWidth=260)
        for n, c in bareme.profils():
            self.combo.addItem(n, c)
        self.combo.activated.connect(self._changer_profil)
        b_ouvrir = QPushButton("📂")
        b_ouvrir.setMaximumWidth(46)
        b_ouvrir.clicked.connect(self._ouvrir_fichier)
        self.nom = QLineEdit(maximumWidth=230)
        h0.addWidget(QLabel(U("tab_bareme")))
        h0.addWidget(self.combo, 1)
        h0.addWidget(b_ouvrir)
        h0.addWidget(QLabel("Nom"))
        h0.addWidget(self.nom)
        v.addWidget(g0)

        # --- عامّ + محاور ---
        ligne = QHBoxLayout()
        g1 = QGroupBox("⚙ Général")
        f1 = QFormLayout(g1)
        self.note_max = QDoubleSpinBox(minimum=1, maximum=100, decimals=0, value=20)
        self.tolerance = QSpinBox(minimum=0, maximum=20)
        self.fatale = QCheckBox("Une erreur de syntaxe met la note à 0")
        self.seuils = QLineEdit("18, 16, 14, 12, 10")
        self.note_max.valueChanged.connect(self._verifier_axes)
        f1.addRow(U("note") + " max", self.note_max)
        f1.addRow("Tolérance (avertissements gratuits)", self.tolerance)
        f1.addRow("", self.fatale)
        f1.addRow("Seuils des mentions", self.seuils)
        ligne.addWidget(g1, 1)

        g2 = QGroupBox("⚖ " + U("axe"))
        f2 = QFormLayout(g2)
        self.axes = {}
        for cle, lib in (("qualite", U("ax_qualite")), ("tests", U("ax_tests")),
                         ("structure", U("ax_structure"))):
            sp = QDoubleSpinBox(minimum=0, maximum=100, decimals=1, singleStep=0.5)
            sp.valueChanged.connect(self._verifier_axes)
            self.axes[cle] = sp
            f2.addRow(lib, sp)
        self.somme = QLabel("—")
        f2.addRow("Somme", self.somme)
        ligne.addWidget(g2, 1)
        v.addLayout(ligne)

        # --- جدول القواعد ---
        v.addWidget(QLabel("Règles — décochez pour signaler l'erreur sans la sanctionner",
                           objectName="sous"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Actif", U("c_code"), U("c_regle"), U("c_unite"), U("c_plafond")])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        en = self.table.horizontalHeader()
        en.setSectionResizeMode(2, QHeaderView.Stretch)
        for j in (0, 1, 3, 4):
            en.setSectionResizeMode(j, QHeaderView.ResizeToContents)
        v.addWidget(self.table, 1)

        # --- معاينة ---
        self.apercu = QLabel("—")
        self.apercu.setWordWrap(True)
        v.addWidget(self.apercu)

        # --- أزرار ---
        h = QHBoxLayout()
        for txt, slot in (("👁 Aperçu sur la classe", self._apercu),
                          ("♻ " + U("pret"), self._reinitialiser),
                          ("💾 Enregistrer sous…", self._enregistrer)):
            b = QPushButton(txt)
            b.clicked.connect(slot)
            h.addWidget(b)
        h.addStretch()
        v.addLayout(h)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("✔ Appliquer")
        bb.accepted.connect(self._appliquer)
        bb.rejected.connect(self._annuler)
        v.addWidget(bb)

    # ------------------------------------------------------------------
    def _remplir(self, d):
        self.nom.setText(d.get("nom", ""))
        self.note_max.setValue(float(d.get("note_max", 20)))
        self.tolerance.setValue(int(d.get("tolerance", 0)))
        self.fatale.setChecked(bool(d.get("erreur_fatale", False)))
        self.seuils.setText(", ".join(str(s) for s in d.get("seuils", [])))
        for cle, sp in self.axes.items():
            sp.setValue(float(d.get("axes", {}).get(cle, 0)))

        regles = d.get("regles", {})
        self.table.setRowCount(0)
        for code in sorted(regles, key=lambda c: -regles[c].get("penalite", 0)):
            r = regles[code]
            i = self.table.rowCount()
            self.table.insertRow(i)
            ch = QCheckBox()
            ch.setChecked(bool(r.get("actif", True)))
            box = QWidget()
            hb = QHBoxLayout(box)
            hb.setContentsMargins(0, 0, 0, 0)
            hb.addWidget(ch, 0, Qt.AlignCenter)
            self.table.setCellWidget(i, 0, box)
            it = QTableWidgetItem(code)
            it.setFlags(it.flags() ^ Qt.ItemIsEditable)
            it.setFont(QFont("Consolas"))
            self.table.setItem(i, 1, it)
            lib = QTableWidgetItem(titre(code))
            lib.setFlags(lib.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(i, 2, lib)
            for j, val in ((3, r.get("penalite", 0)), (4, r.get("plafond", 0))):
                sp = QDoubleSpinBox(minimum=0, maximum=100, decimals=2,
                                    singleStep=0.25, value=float(val))
                self.table.setCellWidget(i, j, sp)
            self.table.item(i, 1).setData(Qt.UserRole, ch)
        self._verifier_axes()

    def _lire(self):
        try:
            seuils = [float(x) for x in self.seuils.text().replace(";", ",").split(",")
                      if x.strip()]
        except ValueError:
            seuils = bareme.seuils()
        regles = {}
        for i in range(self.table.rowCount()):
            code = self.table.item(i, 1).text()
            ch = self.table.item(i, 1).data(Qt.UserRole)
            regles[code] = {"actif": ch.isChecked(),
                            "penalite": self.table.cellWidget(i, 3).value(),
                            "plafond": self.table.cellWidget(i, 4).value()}
        return {"nom": self.nom.text() or "Personnalisé",
                "note_max": self.note_max.value(),
                "tolerance": self.tolerance.value(),
                "erreur_fatale": self.fatale.isChecked(),
                "seuils": seuils,
                "axes": {k: sp.value() for k, sp in self.axes.items()},
                "regles": regles}

    def _verifier_axes(self):
        s = sum(sp.value() for sp in self.axes.values())
        ok = abs(s - self.note_max.value()) < 0.01
        self.somme.setText(f"{s:g} / {self.note_max.value():g}  "
                           f"{'✅' if ok else '⚠️ doit être égal'}")
        self.somme.setStyleSheet("color:#3fb950" if ok else "color:#d29922")

    def _changer_profil(self):
        c = self.combo.currentData()
        try:
            self._remplir(bareme.charger(c) if c else bareme.reinitialiser())
        except Exception as e:
            QMessageBox.warning(self, "⛔", str(e))

    def _ouvrir_fichier(self):
        f, _ = QFileDialog.getOpenFileName(self, U("bt_ouvrir"), bareme.DOSSIER,
                                           "JSON (*.json)")
        if f:
            self._remplir(bareme.charger(f))
            self.combo.addItem(bareme.nom(), f)
            self.combo.setCurrentIndex(self.combo.count() - 1)

    def _reinitialiser(self):
        self._remplir(bareme.reinitialiser())

    def _enregistrer(self):
        bareme.definir(self._lire())
        f, _ = QFileDialog.getSaveFileName(
            self, U("bt_enregistrer"),
            os.path.join(bareme.DOSSIER, (self.nom.text() or "bareme") + ".json"),
            "JSON (*.json)")
        if f:
            bareme.sauver(f)
            self.combo.addItem(bareme.nom(), f)
            self.combo.setCurrentIndex(self.combo.count() - 1)

    def _apercu(self):
        """يعيد حساب النقاط بالسلّم الجديد ويقارنها بالقديم."""
        if not self.resultats:
            self.apercu.setText("Aucune classe corrigée : lancez d'abord la correction.")
            return
        import analyseur
        ancien = json_dump(bareme.actif())
        bareme.definir(self._lire())
        lignes, deltas = [], []
        for nom, _, r in self.resultats[:12]:
            note_q, _, _ = analyseur.calculer_note(r["problemes"])
            q = round(note_q / bareme.note_max() * bareme.axes()["qualite"], 2)
            # المحوران الآخران يُعاد وزنهما نسبيًّا
            t = round(r["tests"] / max(r.get("_pt_tests", 10), 0.01)
                      * bareme.axes()["tests"], 2) if r.get("_pt_tests") else \
                round(r["tests"] / 10 * bareme.axes()["tests"], 2)
            s = round(r["structure"] / 4 * bareme.axes()["structure"], 2)
            neuf = round(q + t + s, 2)
            deltas.append(neuf - r["note"])
            lignes.append(f"{nom}: {r['note']} → <b>{neuf}</b>")
        bareme.definir(json_load(ancien))
        moy = sum(deltas) / len(deltas)
        self.apercu.setText(
            f"<b>Aperçu ({bareme.nom()} → {self.nom.text()})</b> · "
            f"variation moyenne <b>{moy:+.2f}</b> pt<br>" + " · ".join(lignes))

    def _annuler(self):
        """يستعيد السلّم كما كان قبل فتح النافذة."""
        bareme.definir(json_load(self._initial))
        self.reject()

    def _appliquer(self):
        d = self._lire()
        if abs(sum(d["axes"].values()) - d["note_max"]) > 0.01:
            if QMessageBox.question(
                    self, "⚠️",
                    "La somme des axes ne fait pas la note maximale. Continuer ?") \
                    != QMessageBox.Yes:
                return
        bareme.definir(d)
        self.accept()


def json_dump(d):
    import json
    return json.dumps(d, ensure_ascii=False)


def json_load(s):
    import json
    return json.loads(s)


def ouvrir(parent=None, resultats=None):
    """يفتح المحرّر ويُرجع True إن طُبِّق سلّم جديد."""
    d = EditeurBareme(parent, resultats)
    return d.exec_() == QDialog.Accepted
