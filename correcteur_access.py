#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
correcteur_access.py — تصحيح قواعد بيانات التلاميذ (Access / SQLite)
=====================================================================
نفس منطق تصحيح كود بايثون، لكن على قاعدة بيانات: يقرأ بنية ملفّ التلميذ
ويقارنها ببنية ملفّ الأستاذ، ثمّ يشرح كل فرق ويعطي نقطة على 20.

ما يُقارَن
  • الجداول        : الموجودة، الناقصة، الزائدة
  • الحقول         : الاسم، النوع، الحجم، الإلزامية
  • المفاتيح       : المفتاح الأساسي لكل جدول
  • العلاقات       : الروابط بين الجداول (مفاتيح خارجية)
  • الاستعلامات    : وجودها، ثمّ تطابق نتائجها فعليًّا (تُنفَّذ وتُقارَن) وحسب
                   : عدد السجلّات المشتركة يُنقَص جزئيًّا
  • البيانات       : عدد السجلّات في كل جدول

السلّم (على 20)
  Tables 4 · Champs 6 · Clés 2 · Relations 4 · Requêtes 4
  (les poids peuvent être remplacés par un barème JSON v1/v2 — voir --bareme)

الاستعمال
    python correcteur_access.py eleve.accdb -s solution.accdb --lang fr
    python correcteur_access.py eleve.db    -s solution.db     --excel rapport.xlsx
    python correcteur_access.py eleve.db    -s solution.db --bareme baremes/access_v2.json
    python correcteur_access.py dossier_classe/ -s solution.accdb --excel classe.xlsx
    python correcteur_access.py --diagnostic

قراءة ملفّات .accdb / .mdb
    • ويندوز : pip install pyodbc  + Microsoft Access Database Engine (ACE)
    • لينكس  : sudo apt install mdbtools   (mdb-tables / mdb-schema / mdb-export)
    • .db (SQLite) يعمل في كل مكان بلا تثبيت — مفيد للتجريب والتكوين.
    • sans aucun moteur : repli pur Python (access_parser) — tables/champs/
      lignes lus, relations reconstruites par heuristique, requêtes non lues.
"""

import argparse
import csv
import glob
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

import langues
import bareme

# ---------------------------------------------------------------------------
# 1) نصوص الفروق (ar / fr / en)
# ---------------------------------------------------------------------------
TEXTES = {
    "T001": {"p": 4.0, "g": "erreur",
             "ar": ("الجدول '{o}' مفقود",
                    "الجدول موجود في الحلّ وغائب عند التلميذ، فكل ما يعتمد عليه يسقط.",
                    "أنشئ الجدول '{o}' بحقوله كما في نصّ التمرين."),
             "fr": ("Table « {o} » manquante",
                    "La table existe dans la solution mais pas dans la copie : "
                    "tout ce qui en dépend échoue.",
                    "Créez la table « {o} » avec ses champs."),
             "en": ("Table “{o}” missing",
                    "Present in the solution, absent here; everything depending on it fails.",
                    "Create table “{o}” with its fields.")},
    "T002": {"p": 0.5, "g": "avertissement",
             "ar": ("جدول زائد '{o}'", "غير مطلوب في التمرين؛ قد يكون بقايا تجربة.",
                    "احذفه إن لم يكن ضروريًّا."),
             "fr": ("Table « {o} » en trop", "Non demandée par l'énoncé.",
                    "Supprimez-la si elle n'est pas justifiée."),
             "en": ("Extra table “{o}”", "Not required by the task.",
                    "Delete it unless justified.")},
    "C001": {"p": 1.0, "g": "erreur",
             "ar": ("الحقل '{o}' مفقود في الجدول '{t}'",
                    "بيانات مطلوبة لا مكان لها؛ الاستعلامات التي تستعمله ستفشل.",
                    "أضف الحقل '{o}' من النوع {a}."),
             "fr": ("Champ « {o} » manquant dans « {t} »",
                    "Une donnée exigée n'a pas d'emplacement ; les requêtes qui "
                    "l'utilisent échouent.",
                    "Ajoutez le champ « {o} » de type {a}."),
             "en": ("Field “{o}” missing in “{t}”",
                    "Required data has nowhere to go; queries using it fail.",
                    "Add field “{o}” of type {a}.")},
    "C002": {"p": 0.25, "g": "avertissement",
             "ar": ("حقل زائد '{o}' في '{t}'", "غير مطلوب؛ يُثقل الجدول.",
                    "احذفه أو برّر وجوده."),
             "fr": ("Champ « {o} » en trop dans « {t} »", "Non demandé par l'énoncé.",
                    "Supprimez-le ou justifiez-le."),
             "en": ("Extra field “{o}” in “{t}”", "Not required.", "Remove or justify it.")},
    "C003": {"p": 0.75, "g": "erreur",
             "ar": ("نوع خاطئ: '{t}.{o}' = {b} بدل {a}",
                    "النوع الخاطئ يمنع الحسابات أو الفرز الصحيح (تاريخ كنصّ مثلًا).",
                    "غيّر نوع الحقل إلى {a}."),
             "fr": ("Type incorrect : « {t}.{o} » = {b} au lieu de {a}",
                    "Un mauvais type empêche calculs et tris corrects "
                    "(une date stockée en texte, par exemple).",
                    "Changez le type du champ en {a}."),
             "en": ("Wrong type: “{t}.{o}” = {b} instead of {a}",
                    "A wrong type breaks calculations and sorting.",
                    "Change the field type to {a}.")},
    "C004": {"p": 0.25, "g": "avertissement",
             "ar": ("حجم مختلف: '{t}.{o}' = {b} بدل {a}",
                    "حجم أصغر يبتر القيم، وأكبر يهدر المساحة.",
                    "اضبط الحجم على {a}."),
             "fr": ("Taille différente : « {t}.{o} » = {b} au lieu de {a}",
                    "Trop petite, les valeurs sont tronquées ; trop grande, "
                    "c'est de l'espace perdu.",
                    "Fixez la taille à {a}."),
             "en": ("Different size: “{t}.{o}” = {b} instead of {a}",
                    "Too small truncates values, too large wastes space.",
                    "Set the size to {a}.")},
    "P001": {"p": 1.0, "g": "erreur",
             "ar": ("المفتاح الأساسي للجدول '{t}' = {b} بدل {a}",
                    "بلا مفتاح صحيح تتكرّر السجلّات ولا تقوم العلاقات.",
                    "اجعل {a} مفتاحًا أساسيًّا."),
             "fr": ("Clé primaire de « {t} » = {b} au lieu de {a}",
                    "Sans clé correcte, les doublons passent et les relations "
                    "ne tiennent pas.",
                    "Définissez {a} comme clé primaire."),
             "en": ("Primary key of “{t}” = {b} instead of {a}",
                    "Without the right key, duplicates slip in and relations fail.",
                    "Set {a} as the primary key.")},
    "R001": {"p": 1.0, "g": "erreur",
             "ar": ("علاقة مفقودة: {a}",
                    "بلا علاقة لا تُحفَظ السلامة المرجعية ويمكن إدخال قيم يتيمة.",
                    "أنشئ العلاقة {a} مع فرض السلامة المرجعية."),
             "fr": ("Relation manquante : {a}",
                    "Sans relation, l'intégrité référentielle n'est pas assurée : "
                    "des valeurs orphelines deviennent possibles.",
                    "Créez la relation {a} avec intégrité référentielle."),
             "en": ("Missing relationship: {a}",
                    "Without it, referential integrity is not enforced.",
                    "Create relationship {a} with referential integrity.")},
    "R002": {"p": 0.5, "g": "avertissement",
             "ar": ("علاقة زائدة: {a}", "غير مطلوبة وقد تمنع إدخالات مشروعة.",
                    "احذفها إن لم يطلبها التمرين."),
             "fr": ("Relation en trop : {a}", "Non demandée ; peut bloquer des saisies légitimes.",
                    "Supprimez-la si l'énoncé ne la demande pas."),
             "en": ("Extra relationship: {a}", "Not required; may block valid input.",
                    "Remove it unless required.")},
    "Q001": {"p": 1.0, "g": "erreur",
             "ar": ("الاستعلام '{o}' مفقود", "المطلوب في التمرين غير منجَز.",
                    "أنشئ الاستعلام '{o}'."),
             "fr": ("Requête « {o} » manquante", "Le travail demandé n'est pas réalisé.",
                    "Créez la requête « {o} »."),
             "en": ("Query “{o}” missing", "Required work not done.",
                    "Create query “{o}”.")},
    "Q002": {"p": 1.0, "g": "erreur",
             "ar": ("الاستعلام '{o}' يعطي نتيجة مختلفة ({c}/{a} سجلّ مشترك)",
                    "المنتظَر {a} سجلّ والمحصَّل {b} — شرط أو ضمّ خاطئ غالبًا.",
                    "راجع شروط WHERE والضمّ JOIN والتجميع GROUP BY."),
             "fr": ("Requête « {o} » : résultat différent ({c}/{a} lignes communes)",
                    "Attendu {a} enregistrement(s), obtenu {b} — souvent un WHERE "
                    "ou une jointure erronée.",
                    "Vérifiez WHERE, les jointures et GROUP BY."),
             "en": ("Query “{o}”: different result ({c}/{a} shared rows)",
                    "Expected {a} row(s), got {b} — usually a wrong WHERE or join.",
                    "Check WHERE, joins and GROUP BY.")},
    "Q004": {"p": 1.0, "g": "erreur",
             "ar": ("الاستعلام '{o}': نفس عدد السجلّات ({a}) لكن القيم مختلفة ({c} مشترك)",
                    "الشرط أو الحقول المختارة أو الترتيب يعطي بيانات أخرى.",
                    "قارن الأعمدة المختارة وشروط الضمّ مع نصّ التمرين."),
             "fr": ("Requête « {o} » : même nombre de lignes ({a}) mais valeurs "
                    "différentes ({c} en commun)",
                    "Les colonnes choisies, la jointure ou le calcul ne donnent pas "
                    "les mêmes données.",
                    "Comparez les colonnes sélectionnées et les jointures avec l'énoncé."),
             "en": ("Query “{o}”: same row count ({a}) but different values ({c} shared)",
                    "Selected columns, join or computation differ.",
                    "Compare selected columns and joins with the task.")},
    "Q003": {"p": 0.0, "g": "avertissement",
             "ar": ("الاستعلام '{o}': SQL مختلف لكن النتيجة صحيحة",
                    "الصياغة تختلف عن الحلّ لكنّها تعطي نفس السجلّات.",
                    "مقبول — يمكن مقارنة الصياغتين مع التلميذ."),
             "fr": ("Requête « {o} » : SQL différent mais résultat correct",
                    "L'écriture diffère de la solution mais renvoie les mêmes lignes.",
                    "Accepté — comparez les deux écritures avec l'élève."),
             "en": ("Query “{o}”: different SQL, correct result",
                    "Different wording, same rows.", "Accepted.")},
    "D001": {"p": 0.0, "g": "avertissement",
             "ar": ("'{t}': {b} سجلّ بدل {a}", "البيانات المدخَلة ناقصة أو زائدة.",
                    "أكمل إدخال البيانات المطلوبة."),
             "fr": ("« {t} » : {b} enregistrement(s) au lieu de {a}",
                    "La saisie des données est incomplète ou excédentaire.",
                    "Complétez la saisie demandée."),
             "en": ("“{t}”: {b} row(s) instead of {a}", "Data entry incomplete or excessive.",
                    "Complete the required data entry.")},
    "D002": {"p": 1.0, "g": "erreur",
             "ar": ("بيانات الجدول '{t}' مختلفة ({c}/{a} سجلّ مشترك)",
                    "القيم المسجَّلة لا تطابق ورقة بيانات التمرين؛ فالبيانات "
                    "الخاطئة تعطي نتائج خاطئة في الاستعلامات.",
                    "أعد كتابة سجلات الجدول '{t}' حسب ورقة البيانات المطلوبة."),
             "fr": ("Données de « {t} » différentes ({c}/{a} enregistrements "
                    "en commun)",
                    "Les valeurs saisies ne correspondent pas à la feuille de "
                    "données : tant que la saisie est fausse, les requêtes "
                    "renvoient de mauvais résultats.",
                    "Corrigez les enregistrements de « {t} » d'après la feuille "
                    "de données."),
             "en": ("Table “{t}” data differs ({c}/{a} shared records)",
                    "Entered values don't match the data sheet; wrong data "
                    "produces wrong query results.",
                    "Fix table “{t}” records to match the data sheet.")},
}

AXES_DEFAUT = {"tables": 4.0, "champs": 4.0, "donnees": 2.0, "cles": 2.0,
               "relations": 4.0, "requetes": 4.0}
AXE_DE = {"T001": "tables", "T002": "tables", "C001": "champs", "C002": "champs",
          "C003": "champs", "C004": "champs", "P001": "cles", "R001": "relations",
          "R002": "relations", "Q001": "requetes", "Q002": "requetes",
          "Q003": "requetes", "Q004": "requetes", "D001": "donnees",
          "D002": "donnees"}

# Correspondance écart Access → code de règle du barème v2
ECART_VERS_REGLES = {"T001": "E001", "T002": "E002", "C001": "E102",
                     "C002": "W101", "C003": "E104", "C004": "W106",
                     "P001": "E108", "R001": "E110", "R002": "W107",
                     "E111": "E111", "Q001": "E120", "Q002": "E121",
                     "Q003": "W109", "Q004": "E121", "D001": "D001",
                     "D002": "D001"}


def _axes():
    """Poids des axes issus du barème chargé (v1 ou v2) — repli sur DEFAUT."""
    abd = bareme.axes_bd()
    return abd if abd else AXES_DEFAUT


def _seuils_mentions():
    """Limites + mentions : barème v2 d'abord, puis langues.py."""
    sc = bareme.seuils_mentions()
    if sc:
        return sc
    return langues.mentions()


def _cmp(section, cle, defaut=True):
    """Lit un réglage de comparaison v2 avec repli sur la valeur par défaut."""
    try:
        return bool(bareme.comparaison().get(section, {}).get(cle, defaut))
    except Exception:
        return bool(defaut)


def _cmp_donnees(cle, defaut=True):
    """Réglage « donnees.comparer.<cle> » (section v2 « donnees »).
    Section absente → réglage par défaut ; active:false → jamais comparé."""
    try:
        d = bareme.donnees()
    except Exception:
        return bool(defaut)
    if not isinstance(d, dict):
        return bool(defaut)
    if d.get("active") is False:
        return False
    return bool(d.get("comparer", {}).get(cle, defaut))


def _donnees_comparees(st, nom):
    """Lignes de la table « nom » sans les colonnes de la clé primaire : les
    identifiants auto-incrémentés ne sont pas de la « saisie » attendue (l'élève
    ne choisit pas la valeur de IdEleve), on compare le reste de la feuille."""
    d = st["tables"].get(nom, {})
    excl = set(d.get("pk") or [])
    cols = list(d.get("champs", {}))
    gardes = [i for i, c in enumerate(cols) if c not in excl]
    lignes = []
    for r in d.get("data") or []:
        lignes.append(tuple(r[i] for i in gardes if i < len(r)))
    return lignes


class _Fmt(dict):
    def __missing__(self, k):
        return ""


def _txt(code, **kw):
    d = TEXTES[code]
    lg = langues.langue() if langues.langue() in d else "fr"
    m, c, f = d[lg]
    z = _Fmt(kw)
    return m.format_map(z), c.format_map(z), f.format_map(z)


class Ecart:
    def __init__(self, code, penalite=None, **kw):
        self.code = code
        self.message, self.cause, self.correction = _txt(code, **kw)
        self.penalite = TEXTES[code]["p"] if penalite is None else penalite
        self.gravite = TEXTES[code]["g"]
        self.axe = AXE_DE[code]
        self.objet = kw.get("o") or kw.get("t") or kw.get("a", "")

    @property
    def icone(self):
        return "❌" if self.gravite == "erreur" else "⚠️"


# ---------------------------------------------------------------------------
# 2) قراءة البنية — ثلاثة محرّكات
# ---------------------------------------------------------------------------
TYPES = {  # توحيد أسماء الأنواع بين Access و SQLite
    "counter": "NumeroAuto", "integer": "Entier", "int": "Entier", "long": "EntierLong",
    "smallint": "Entier", "double": "Reel", "real": "Reel", "float": "Reel",
    "currency": "Monetaire", "varchar": "Texte", "text": "Texte", "char": "Texte",
    "nvarchar": "Texte", "longchar": "Memo", "memo": "Memo", "datetime": "DateHeure",
    "date": "DateHeure", "timestamp": "DateHeure", "bit": "Booleen",
    "boolean": "Booleen", "yesno": "Booleen", "numeric": "Reel", "decimal": "Reel",
    "blob": "ObjetOLE", "longbinary": "ObjetOLE",
}


def _type(brut):
    b = re.sub(r"\(.*?\)", "", str(brut or "")).strip().lower()
    return TYPES.get(b, b.capitalize() or "?")


def _taille(brut):
    m = re.search(r"\((\d+)", str(brut or ""))
    return int(m.group(1)) if m else None


def lire_sqlite(chemin):
    cx = sqlite3.connect(chemin)
    cur = cx.cursor()
    st = {"tables": {}, "relations": [], "requetes": {}, "moteur": "SQLite"}
    objets = list(cur.execute("SELECT name, type, sql FROM sqlite_master "
                              "WHERE name NOT LIKE 'sqlite_%'"))
    for nom, typ, sql in objets:
        if typ == "view":
            st["requetes"][nom] = sql
            continue
        if typ != "table":
            continue
        champs, pk = {}, []
        for _, cn, ct, notnull, _d, ipk in cur.execute(f'PRAGMA table_info("{nom}")'):
            champs[cn] = {"type": _type(ct), "taille": _taille(ct),
                          "obligatoire": bool(notnull or ipk)}
            if ipk:
                pk.append(cn)
        rel = []
        for r in cur.execute(f'PRAGMA foreign_key_list("{nom}")'):
            rel.append({"table": nom, "champ": r[3], "table_ref": r[2], "champ_ref": r[4]})
        st["relations"] += rel
        n = cur.execute(f'SELECT COUNT(*) FROM "{nom}"').fetchone()[0]
        data = [tuple(r) for r in cur.execute(f'SELECT * FROM "{nom}"')]
        st["tables"][nom] = {"champs": champs, "pk": pk, "lignes": n, "data": data}
    cx.close()
    return st


def _relations_partagees(st):
    """Heuristique de secours : colonne partagée qui est clé primaire chez l'une
    des tables → relation (utilisée si le moteur ne peut lire les FK réelles)."""
    noms = list(st["tables"])
    rels = []
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            partages = set(st["tables"][a]["champs"]) & set(st["tables"][b]["champs"])
            for c in sorted(partages):
                if c in st["tables"][a]["pk"]:
                    rels.append({"table": b, "champ": c,
                                 "table_ref": a, "champ_ref": c})
                elif c in st["tables"][b]["pk"]:
                    rels.append({"table": a, "champ": c,
                                 "table_ref": b, "champ_ref": c})
    return rels


def lire_access_odbc(chemin):
    import pyodbc
    pil = [d for d in pyodbc.drivers() if "Access" in d]
    if not pil:
        raise RuntimeError("pilote ACE absent")
    st = {"tables": {}, "relations": [], "requetes": {}, "moteur": "Access (ACE)"}
    # On réutilise la connexion en cache (_connexion_access) : le pilote ACE
    # limite son pool de « client tasks » (-1036) et libère lentement ses
    # connexions ; ouvrir/fermer à chaque lecture/requête finit par un arrêt
    # (violation d'accès à la fermeture). Voir fermer_connexions().
    cx = _connexion_access(chemin)
    cur = cx.cursor()
    adox = _adox_lire(chemin)   # PK/FK réels (None si pywin32 absent)
    noms = [t.table_name for t in cur.tables(tableType="TABLE")
            if not t.table_name.startswith("MSys")]
    for nom in noms:
        champs = {}
        for c in cur.columns(table=nom):
            champs[c.column_name] = {"type": _type(c.type_name),
                                     "taille": c.column_size,
                                     "obligatoire": c.nullable == 0}
        # Le pilote ACE refuse SQLPrimaryKeys (IM001) : on prend la vraie clé
        # ADOX ; repli par convention de nom si ADOX indisponible.
        adox_pk = (adox or {}).get("pk", {}).get(nom) or []
        try:
            pk = list(adox_pk) or [r.column_name
                                   for r in cur.primaryKeys(table=nom)]
        except Exception:
            pk = list(adox_pk) or _detecter_pk_ac(list(champs))
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM [{nom}]").fetchone()[0]
        except Exception:
            n = 0
        try:
            data = [tuple(r) for r in cur.execute(f"SELECT * FROM [{nom}]")]
        except Exception:
            data = []
        st["tables"][nom] = {"champs": champs, "pk": pk, "lignes": n, "data": data}
    # Relations réelles via ADOX (le pilote ACE refuse SQLForeignKeys/IM001).
    # Quand ADOX répond, on le CROIT même s'il ne trouve aucune relation (la
    # liste vide est une réponse : les relations ont été retirées dans Access).
    if adox is not None:
        st["relations"] = adox.get("fk") or []
    else:
        # Repli : colonnes partagées qui sont clé primaire chez l'une des tables
        # (heuristique — ne reflète PAS les relations réelles d'Access).
        st["relations"] = _relations_partagees(st)
    # Lecture des requêtes enregistrées (vues). On matérialise la liste des
    # noms AVANT tout cur.execute : itérer cur.tables() revient à parcourir la
    # même ligne de résultats du curseur, et une exécution intermédiaire
    # (ex. MSysObjects, interdite sans droits) la détruit → repli access_parser
    # qui, lui, ne lit PAS les requêtes (« Requêtes : 0 »).
    # Le SQL n'est pas lisible par ODBC (MSysObjects sans droit) ; on le laisse
    # vide → la comparaison porte sur l'existence et les RÉSULTATS (Q001/Q002/Q004).
    vues = [v.table_name for v in cur.tables(tableType="VIEW")]
    for q in vues:
        st["requetes"][q] = ""
    return st


def lire_access_mdbtools(chemin):
    if not shutil.which("mdb-tables"):
        raise RuntimeError("mdbtools absent (sudo apt install mdbtools)")
    st = {"tables": {}, "relations": [], "requetes": {}, "moteur": "mdbtools"}
    noms = subprocess.run(["mdb-tables", "-1", chemin], capture_output=True,
                          text=True).stdout.split()
    schema = subprocess.run(["mdb-schema", chemin], capture_output=True,
                            text=True).stdout
    for nom in noms:
        bloc = re.search(rf'CREATE TABLE \[{re.escape(nom)}\]\s*\((.*?)\);',
                         schema, re.S)
        champs = {}
        if bloc:
            for l in bloc.group(1).splitlines():
                m = re.match(r"\s*\[(.+?)\]\s+(.+?)(,|\s*$)", l.strip())
                if m:
                    champs[m.group(1)] = {"type": _type(m.group(2)),
                                          "taille": _taille(m.group(2)),
                                          "obligatoire": "NOT NULL" in l.upper()}
        export = subprocess.run(["mdb-export", chemin, nom], capture_output=True,
                                text=True).stdout
        lignes_tab = list(csv.reader(io.StringIO(export)))
        st["tables"][nom] = {"champs": champs, "pk": [],
                             "lignes": max(len(lignes_tab) - 1, 0),
                             "data": [tuple(r) for r in lignes_tab[1:]]}
    for m in re.finditer(r"ALTER TABLE \[(.+?)\].*?FOREIGN KEY \(\[(.+?)\]\).*?"
                         r"REFERENCES \[(.+?)\]\s*\(\[(.+?)\]\)", schema, re.S):
        st["relations"].append({"table": m.group(1), "champ": m.group(2),
                                "table_ref": m.group(3), "champ_ref": m.group(4)})
    return st


def _texte_ac(v):
    """Les chaînes d'access_parser arrivent en bytes → str."""
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except Exception:
            return v.decode("latin-1", "replace")
    return v


def _inferer_type_ac(valeurs):
    non_nul = [v for v in valeurs if v is not None]
    if not non_nul:
        return "Texte"
    if all(isinstance(v, int) for v in non_nul):
        return "EntierLong"
    if all(isinstance(v, float) for v in non_nul):
        return "Reel"
    return "Texte"


def _detecter_pk_ac(colonnes):
    for c in colonnes:
        cn = c.lower().replace(" ", "").replace("_", "")
        if re.fullmatch(r"(id|code|ref|num).*", cn) or cn.endswith("id"):
            return [c]
    return []


def lire_access_python(chemin):
    """Repli pur Python (access_parser) : tables/champs/lignes lus, clés par
    convention de nom, relations reconstruites par colonnes partagées.
    Limites : requêtes non lues → axe Requêtes neutralisé ; types inférés."""
    from access_parser import AccessParser
    p = AccessParser(chemin)
    st = {"tables": {}, "relations": [], "requetes": {}, "moteur": "access_parser"}
    for nom in p.catalog:
        if nom.startswith("MSys") or re.fullmatch(r"f_[0-9A-Fa-f]{32}_Data", nom):
            continue
        try:
            tab = p.parse_table(nom)
        except Exception:
            continue
        if not tab:
            continue
        champs = {}
        for c in list(tab):
            vals = [_texte_ac(v) for v in tab[c]]
            champs[c] = {"type": _inferer_type_ac(vals), "taille": None,
                         "obligatoire": False}
        nb = min((len(v) for v in tab.values()), default=0)
        colonnes = list(tab)
        data = [tuple(_texte_ac(tab[c][i]) for c in colonnes)
                for i in range(nb)]
        chp = champs
        st["tables"][nom] = {"champs": chp, "pk": _detecter_pk_ac(list(tab)),
                             "lignes": nb, "data": data}
    st["relations"] = _relations_partagees(st)
    return st


def lire(chemin):
    ext = os.path.splitext(chemin)[1].lower()
    if ext in (".db", ".sqlite", ".sqlite3"):
        return lire_sqlite(chemin)
    if ext in (".accdb", ".mdb"):
        errs = []
        for fn in (lire_access_odbc, lire_access_mdbtools, lire_access_python):
            try:
                return fn(chemin)
            except Exception as e:
                errs.append(str(e))
        raise RuntimeError("lecture impossible : " + " | ".join(errs))
    raise RuntimeError(f"extension non gérée : {ext}")


def executer_requete(chemin, sql):
    """ينفّذ استعلامًا ويُرجع (نجاح، عدد السجلّات، أوّل الصفوف).

    Pour .accdb, un seul connexion est réutilisée par fichier
    (_connexion_access) : ouvrir/fermer une connexion pyodbc à chaque requête
    fait planter le moteur ACE (violation d'accès 0xC0000005 pendant la
    fermeture). Appeler fermer_connexions() en fin de traitement.
    """
    try:
        if os.path.splitext(chemin)[1].lower() in (".db", ".sqlite", ".sqlite3"):
            cx = sqlite3.connect(chemin)
            rows = [tuple(r) for r in cx.execute(sql)]
            cx.close()
        else:
            from adaptateur_access_sql import access_sql
            cx = _connexion_access(chemin)
            qh = access_sql(sql)
            try:
                rows = [tuple(r) for r in cx.cursor().execute(qh).fetchall()]
            except Exception:
                rows = [tuple(r) for r in cx.cursor().execute(sql).fetchall()]
        return True, len(rows), rows[:300]
    except Exception:
        return False, 0, []


def _norm_val(v):
    if v is None:
        return "∅"
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, int):
        return v
    return str(v).strip().lower()


def _score_lignes(l_s, l_e):
    """Similarité de deux ensembles de résultats (crédit partiel) :
        → (lignes communes, fraction 0..1 = communes / max(attendu, obtenu)).
    Les valeurs sont normalisées (casse, espaces, arrondi) pour ne pas pénaliser
    ce qui ne change pas le sens."""
    if not l_s and not l_e:
        return 0, 1.0
    if not l_s or not l_e:
        return 0, 0.0
    a = {tuple(_norm_val(v) for v in r) for r in l_s}
    b = {tuple(_norm_val(v) for v in r) for r in l_e}
    commun = len(a & b)
    return commun, commun / max(len(a), len(b))


_CACHE_ACCES = {}  # abspath → (mtime, taille, connexion pyodbc)


def _connexion_access(chemin):
    """Connexion .accdb réutilisée pour un même fichier — mais SEULEMENT tant
    que le fichier n'a pas changé sur le disque. Le moteur ACE met le catalogue
    (tables/champs/requêtes) en cache par connexion : si le fichier .accdb a
    été modifié (enregistré depuis Access, tables recréées, vues ajoutées…)
    pendant que notre ancienne connexion est encore ouverte, celle-ci répond
    avec un état périmé (tables vides, requêtes en échec). On détecte donc le
    changement (mtime/taille) et on rouvre une connexion neuve.
    Ouverture en Mode=Read : le correcteur ne prend plus le verrou d'écriture
    Jet sur le fichier (Access peut rester ouvert et enregistrer sans blocage).
    DisablePooling=True : coupe le pool du Gestionnaire ODBC qui, lui aussi,
    peut resservir une connexion ACE aux métadonnées périmées."""
    import pyodbc
    cle = os.path.abspath(chemin)
    try:
        m0, s0 = os.path.getmtime(chemin), os.path.getsize(chemin)
    except OSError:
        m0, s0 = 0, 0
    entree = _CACHE_ACCES.get(cle)
    if entree is not None and (entree[0], entree[1]) != (m0, s0):
        try:
            entree[2].close()
        except Exception:
            pass
        _CACHE_ACCES.pop(cle, None)
        entree = None
    if entree is None:
        pil = [d for d in pyodbc.drivers() if "Access" in d][0]
        cx = pyodbc.connect(
            f"DRIVER={{{pil}}};DBQ={cle};Mode=Read;DisablePooling=True;")
        _CACHE_ACCES[cle] = (m0, s0, cx)
    return _CACHE_ACCES[cle][2]


def fermer_connexions():
    """Ferme explicitement toutes les connexions .accdb en cache (→ désamorcer
    le crash du moteur ACE à la fermeture de l'interpréteur)."""
    for _, _, cx in list(_CACHE_ACCES.values()):
        try:
            cx.close()
        except Exception:
            pass
    _CACHE_ACCES.clear()
    _ADOX_CACHE.clear()


# ---------------------------------------------------------------------------
# Clés primaires et relations RÉELLES d'un .accdb : le pilote ODBC ACE refuse
# SQLPrimaryKeys et SQLForeignKeys (IM001 — vérifié), et le repli conventionnel
# par noms de colonnes partagées ne reflète jamais les modifications faites
# dans Access (ajout/suppression d'une relation ne change rien à la correction).
# ADOX lit les vraies clés, mais un Dispatch ADOX répété dans ce processus fait
# planter le moteur ACE (violation d'accès 0xC0000005) → on l'exécute dans un
# sous-processus isolé, une fois par fichier (mis en cache par mtime/taille).
# ---------------------------------------------------------------------------
_ADOX_SCRIPT = r"""# -*- coding: utf-8 -*-
import sys, json
from win32com.client import Dispatch
chemin = sys.argv[1]
cat = Dispatch("ADOX.Catalog")
cat.ActiveConnection = ("Provider=Microsoft.ACE.OLEDB.12.0;Mode=Read;"
                        "Data Source=" + chemin + ";")
pk, fk = {}, []
for t in cat.Tables:
    if t.Type != "TABLE" or t.Name.startswith("MSys"):
        continue
    nom = t.Name
    for k in t.Keys:
        try:
            if k.Type == 1:                # adKeyPrimary
                pk.setdefault(nom, [])
                for c in k.Columns:
                    if c.Name not in pk[nom]:
                        pk[nom].append(c.Name)
            elif k.Type == 2:              # adKeyForeign
                for c in k.Columns:
                    if c.RelatedColumn:
                        fk.append({"table": nom, "champ": c.Name,
                                   "table_ref": k.RelatedTable,
                                   "champ_ref": c.RelatedColumn})
        except Exception:
            continue
print(json.dumps({"pk": pk, "fk": fk}, ensure_ascii=True))
sys.exit(0)
"""

_ADOX_CACHE = {}  # abspath → (mtime, taille, données ADOX)


def _adox_lire(chemin):
    """PK/FK réels d'un .accdb via ADOX. Retourne None si pywin32 est absent
    ou si la lecture échoue (→ repli heuristique côté appelant)."""
    cle = os.path.abspath(chemin)
    try:
        m0, s0 = os.path.getmtime(cle), os.path.getsize(cle)
    except OSError:
        m0, s0 = 0, 0
    entree = _ADOX_CACHE.get(cle)
    if entree is not None and (entree[0], entree[1]) == (m0, s0):
        return entree[2]
    donnees = None
    try:
        r = subprocess.run([sys.executable, "-c", _ADOX_SCRIPT, cle],
                           capture_output=True, text=True, timeout=45)
        if r.returncode == 0:
            donnees = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        donnees = None
    _ADOX_CACHE[cle] = (m0, s0, donnees)
    return donnees


# ---------------------------------------------------------------------------
# 3) المقارنة والتنقيط
# ---------------------------------------------------------------------------
def _rel(r):
    return f"{r['table']}.{r['champ']} → {r['table_ref']}.{r['champ_ref']}"


def comparer(f_eleve, f_solution):
    se, ss = lire(f_eleve), lire(f_solution)
    ecarts = []

    # --- الجداول ---
    for t in ss["tables"]:
        if t not in se["tables"]:
            ecarts.append(Ecart("T001", o=t))
    for t in se["tables"]:
        if t not in ss["tables"]:
            ecarts.append(Ecart("T002", o=t))

    # --- الحقول والمفاتيح والبيانات ---
    verifier_type = _cmp("champs", "verifier_type", True)
    verifier_taille = _cmp("champs", "verifier_taille", True)
    for t, ds in ss["tables"].items():
        de = se["tables"].get(t)
        if not de:
            continue
        for c, cs in ds["champs"].items():
            ce = de["champs"].get(c)
            if not ce:
                ecarts.append(Ecart("C001", o=c, t=t, a=cs["type"]))
                continue
            if verifier_type and ce["type"] != cs["type"]:
                ecarts.append(Ecart("C003", o=c, t=t, a=cs["type"], b=ce["type"]))
            elif verifier_taille and cs["taille"] and ce["taille"] \
                    and ce["taille"] != cs["taille"]:
                ecarts.append(Ecart("C004", o=c, t=t, a=cs["taille"], b=ce["taille"]))
        for c in de["champs"]:
            if c not in ds["champs"]:
                ecarts.append(Ecart("C002", o=c, t=t))
        if sorted(de["pk"]) != sorted(ds["pk"]):
            ecarts.append(Ecart("P001", t=t, a=", ".join(ds["pk"]) or "—",
                                b=", ".join(de["pk"]) or "—"))
        if de["lignes"] != ds["lignes"]:
            ecarts.append(Ecart("D001", t=t, a=ds["lignes"], b=de["lignes"]))

    # --- البيانات (المُدخَلة) : مقارنة القيم جدولًا بجدول — credit partiel ---
    # L'axe « donnees » compare le contenu réel des tables (hors clé primaire).
    # Il ne s'active que si le barème lui donne des points.
    if float(_axes().get("donnees", 0.0) or 0.0) > 0 \
            and _cmp_donnees("valeurs", True):
        for t, ds in ss["tables"].items():
            if t not in se["tables"]:
                continue
            l_s = _donnees_comparees(ss, t)
            l_e = _donnees_comparees(se, t)
            commun, score = _score_lignes(l_s, l_e)
            if score < 1.0:
                ecarts.append(Ecart("D002", t=t, a=ds["lignes"],
                                    b=se["tables"][t]["lignes"], c=commun,
                                    penalite=round(1.0 - score, 3)))

    # --- العلاقات ---
    re_e = {_rel(r) for r in se["relations"]}
    re_s = {_rel(r) for r in ss["relations"]}
    for r in sorted(re_s - re_e):
        ecarts.append(Ecart("R001", a=r))
    for r in sorted(re_e - re_s):
        ecarts.append(Ecart("R002", a=r))

    # --- الاستعلامات (تُنفَّذ وتُقارَن نتائجها — نُقط بجزئية حسب التشابه) ---
    for q, sql_s in ss["requetes"].items():
        if q not in se["requetes"]:
            ecarts.append(Ecart("Q001", o=q))
            continue
        ok_s, n_s, l_s = executer_requete(f_solution, f"SELECT * FROM [{q}]")
        ok_e, n_e, l_e = executer_requete(f_eleve, f"SELECT * FROM [{q}]")
        if not ok_e:
            ecarts.append(Ecart("Q002", o=q, a=n_s, b="erreur", c=0))
            continue
        commun, score = _score_lignes(l_s, l_e)
        if score < 1.0:
            # Crédit partiel : une requête presque juste perd moins de points.
            code = "Q004" if n_e == n_s else "Q002"
            perd = (1.0 - score) * TEXTES[code]["p"]
            ecarts.append(Ecart(code, o=q, a=n_s, b=n_e, c=commun,
                                penalite=round(perd, 3)))
        elif re.sub(r"\s+", " ", (se["requetes"][q] or "").lower()) != \
                re.sub(r"\s+", " ", (sql_s or "").lower()):
            ecarts.append(Ecart("Q003", o=q))

    # --- النقطة ---
    # Le poids des axes vient du barème (barème v2 « somme_axes » + répartition
    # proportionnelle = même modèle que la v1). Les pénalités sans poids propre
    # sont comptées relativement au nombre d'éléments attendus par axe.
    attendu = {"tables": len(ss["tables"]),
               "champs": sum(len(d["champs"]) for d in ss["tables"].values()),
               "cles": len(ss["tables"]),
               "relations": max(len(ss["relations"]), 1),
               "requetes": max(len(ss["requetes"]), 1),
               "donnees": sum(1 for d in ss["tables"].values() if d["lignes"])}
    notes = {}
    for axe, total in _axes().items():
        perdu = sum(e.penalite for e in ecarts if e.axe == axe)
        # الخصم نسبيّ إلى حجم المطلوب حتّى لا يُعاقَب تمرين صغير مرّتين
        maxi = max(attendu.get(axe, 1), 1)
        notes[axe] = round(max(0.0, total * (1 - perdu / maxi)), 2)
    note = round(sum(notes.values()), 2)
    mention = next((m for s, m in _seuils_mentions() if note >= s),
                   _seuils_mentions()[-1][1])
    r = {"note": note, "mention": mention, "axes": notes, "ecarts": ecarts,
         "eleve": se, "solution": ss, "attendu": attendu}

    # En mode barème v2, on peut avoir un détail des règles (codes v2) pour le
    # rapport — conservé tel quel si les règles sont couplées aux écarts.
    r["bareme"] = bareme.nom() if bareme.chemin() != "(défaut interne)" else "Standard"
    return r


# ---------------------------------------------------------------------------
# 4) التقارير
# ---------------------------------------------------------------------------
def afficher(r, fichier=""):
    U = langues.U
    print("\n" + "=" * 80)
    print(f"🗄  {fichier}   —   📊 {U('note_finale')} : {r['note']} / 20   "
          f"({r['mention'].split('—')[0].strip()})")
    print("=" * 80)
    libelles = {"tables": "Tables", "champs": "Champs / types",
                "donnees": "Données", "cles": "Clés primaires",
                "relations": "Relations", "requetes": "Requêtes"}
    for axe, total in _axes().items():
        print(f"{libelles.get(axe, axe):<32}{r['axes'][axe]:>8} / {total}")
    print("-" * 80)
    print(f"{'Total':<32}{r['note']:>8} / 20")

    print(f"\n📐 Structure comparée")
    print(f"   Tables      : élève {len(r['eleve']['tables']):>3}   "
          f"solution {len(r['solution']['tables']):>3}")
    print(f"   Champs      : élève "
          f"{sum(len(d['champs']) for d in r['eleve']['tables'].values()):>3}   "
          f"solution {r['attendu']['champs']:>3}")
    print(f"   Relations   : élève {len(r['eleve']['relations']):>3}   "
          f"solution {len(r['solution']['relations']):>3}")
    print(f"   Requêtes    : élève {len(r['eleve']['requetes']):>3}   "
          f"solution {len(r['solution']['requetes']):>3}")

    if not r["ecarts"]:
        print("\n✅ Aucune différence.")
        return
    print(f"\n🔍 Écarts ({len(r['ecarts'])})")
    for e in r["ecarts"]:
        print(f"  {e.icone} [{e.code}] {e.message}")
        print(f"      💡 {e.cause}")
        print(f"      ✅ {e.correction}")


def exporter_excel(chemin, rapports, solution=""):
    """rapports : [(nom_fichier, resultat_comparer), ...]"""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    ENT = Font(name="Arial", bold=True, color="FFFFFF")
    FOND = PatternFill("solid", fgColor="1F3864")
    N = Font(name="Arial")
    C = Alignment(horizontal="center", vertical="center")

    def entete(ws, cols, larg):
        for j, (t, l) in enumerate(zip(cols, larg), 1):
            c = ws.cell(1, j, t)
            c.font, c.fill, c.alignment = ENT, FOND, C
            ws.column_dimensions[get_column_letter(j)].width = l
        ws.freeze_panes = "A2"

    wb = Workbook()
    ws = wb.active
    ws.title = "Notes"
    abd = _axes()
    LIB = {"tables": "Tables", "champs": "Champs", "donnees": "Données",
           "cles": "Clés", "relations": "Relations", "requetes": "Requêtes"}
    cols = ["#", "Fichier", "Note /20", "Mention"]
    larg = [5, 26, 10, 15]
    for axe in abd:
        cols.append(f"{LIB.get(axe, axe)} /{abd[axe]:g}")
        larg.append(10)
    cols.append("Écarts")
    larg.append(9)
    entete(ws, cols, larg)
    for i, (nom, r) in enumerate(sorted(rapports, key=lambda x: -x[1]["note"]), 2):
        vals = [i - 1, nom, r["note"], r["mention"].split("—")[0].strip()]
        for axe in abd:
            vals.append(r["axes"].get(axe, 0))
        vals.append(len(r["ecarts"]))
        for j, v in enumerate(vals, 1):
            c = ws.cell(i, j, v)
            c.font, c.alignment = N, C
    n = len(rapports)
    ws.cell(n + 3, 2, "Moyenne").font = ENT
    ws.cell(n + 3, 3, f"=IFERROR(AVERAGE(C2:C{n + 1}),0)").number_format = "0.00"

    # مقارنة البنى جنبًا إلى جنب
    wc = wb.create_sheet("Comparaison")
    entete(wc, ["Fichier", "Objet", "Élève", "Solution", "Identique ?"],
           [24, 20, 12, 12, 13])
    i = 2
    for nom, r in rapports:
        paires = [("Tables", len(r["eleve"]["tables"]), len(r["solution"]["tables"])),
                  ("Champs", sum(len(d["champs"]) for d in r["eleve"]["tables"].values()),
                   r["attendu"]["champs"]),
                  ("Relations", len(r["eleve"]["relations"]),
                   len(r["solution"]["relations"])),
                  ("Requêtes", len(r["eleve"]["requetes"]),
                   len(r["solution"]["requetes"]))]
        for obj, a, b in paires:
            for j, v in enumerate((nom, obj, a, b, "OUI" if a == b else "NON"), 1):
                c = wc.cell(i, j, v)
                c.font, c.alignment = N, (C if j > 1 else Alignment(horizontal="left"))
            i += 1

    we = wb.create_sheet("Écarts")
    entete(we, ["Fichier", "Code", "Gravité", "Axe", "Objet", "Message", "Cause",
                "Correction"], [22, 8, 13, 12, 20, 44, 56, 50])
    i = 2
    freq = {}
    for nom, r in rapports:
        for e in r["ecarts"]:
            freq[e.code] = freq.get(e.code, 0) + 1
            for j, v in enumerate((nom, e.code, e.gravite, e.axe, str(e.objet),
                                   e.message, e.cause, e.correction), 1):
                c = we.cell(i, j, v)
                c.font = N
                c.alignment = Alignment(vertical="center", wrap_text=(j >= 6))
            i += 1

    wf = wb.create_sheet("Fréquences")
    entete(wf, ["Code", "Occurrences", "Copies concernées", "Pénalité"], [10, 14, 20, 12])
    for i, (code, nb) in enumerate(sorted(freq.items(), key=lambda x: -x[1]), 2):
        copies = sum(1 for _, r in rapports if any(e.code == code for e in r["ecarts"]))
        for j, v in enumerate((code, nb, copies, TEXTES[code]["p"]), 1):
            c = wf.cell(i, j, v)
            c.font, c.alignment = N, C

    wb.save(chemin)
    return chemin


def diagnostic():
    out = [f"OS : {os.name}", "sqlite3 : ✅ (.db toujours lisible)"]
    try:
        import pyodbc
        pil = [d for d in pyodbc.drivers() if "Access" in d]
        out.append("pyodbc : ✅   pilotes Access : " + (", ".join(pil) or "❌ aucun"))
    except ImportError:
        out.append("pyodbc : ❌ (pip install pyodbc)")
    out.append("mdbtools : " + ("✅" if shutil.which("mdb-tables") else
                                "❌ (sudo apt install mdbtools)"))
    try:
        import access_parser  # noqa: F401
        out.append("access_parser : ✅ (repli pur Python, sans relations/requêtes)")
    except ImportError:
        out.append("access_parser : ❌ (pip install access-parser)")
    try:
        import win32com.client  # noqa: F401
        out.append("pywin32 : ✅ (clés primaires + relations réelles lues via ADOX)")
    except ImportError:
        out.append("pywin32 : ❌ (pip install pywin32  → relations limitées à l'heuristique)")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Correction de bases Access / SQLite")
    ap.add_argument("cible", nargs="?", help="fichier élève ou dossier de copies")
    ap.add_argument("-s", "--solution")
    ap.add_argument("--excel")
    ap.add_argument("--bareme", help="fichier barème JSON ou nom de profil "
                                     "(ex. --bareme baremes/access_v2.json)")
    ap.add_argument("--lang", choices=list(langues.LANGUES), default=langues.langue())
    ap.add_argument("--diagnostic", action="store_true")
    a = ap.parse_args()

    if a.diagnostic:
        print(diagnostic())
        return
    if not a.cible or not a.solution:
        ap.error("cible et --solution requis")
    langues.definir_langue(a.lang)
    if a.bareme:
        try:
            bareme.charger_profil(a.bareme)
            print(f"⚖  {bareme.nom()}  ({bareme.chemin()})")
        except FileNotFoundError:
            pass

    cibles = ([f for ext in ("*.accdb", "*.mdb", "*.db")
               for f in sorted(glob.glob(os.path.join(a.cible, ext)))]
              if os.path.isdir(a.cible) else [a.cible])
    cibles = [c for c in cibles
              if os.path.realpath(c) != os.path.realpath(a.solution)]

    rapports = []
    for c in cibles:
        try:
            r = comparer(c, a.solution)
            rapports.append((os.path.basename(c), r))
            afficher(r, os.path.basename(c))
        except Exception as e:
            print(f"⚠️ {c} : {e}", file=sys.stderr)

    if a.excel and rapports:
        print("\n💾 " + exporter_excel(a.excel, rapports, a.solution))

    fermer_connexions()


if __name__ == "__main__":
    main()
    # Le pilote ACE peut lever une violation d'accès PENDANT la fermeture de
    # l'interpréteur (déchargement DLL) — tout le travail est déjà terminé,
    # on sort sans démonter l'interpréteur (ne pas utiliser os._exit ailleurs :
    # il court-circuite les buffers, d'où les flush ci-dessus).
    sys.stdout.flush()
    sys.stderr.flush()
    import os as _os
    _os._exit(0)
