#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convertir_en_accdb.py — تحويل قواعد التجربة إلى ملفّات .accdb حقيقية
=====================================================================
النسخ التجريبية في bd/ مكتوبة بصيغة SQLite لأنّها تعمل في كل نظام.
هذا السكربت يحوّلها إلى Access حقيقي على جهاز ويندوز.

    pip install pyodbc msaccessdb        (ويندوز + Microsoft Access Database Engine)
    python convertir_en_accdb.py bd/                → bd_accdb/*.accdb
    python convertir_en_accdb.py bd/ --sql-seulement → ملفّات .sql بلهجة Access

وضعان:
  • إن توفّر محرّك ACE : يُنشئ ملفّ .accdb كاملًا (جداول + بيانات + علاقات + استعلامات)
  • إن لم يتوفّر (لينكس/Termux أو ويندوز بلا ACE) : يكتب لكل نسخة ملفّ .sql
    بلهجة Access جاهزًا للّصق في: Créer ▸ Création de requête ▸ Mode SQL
    (تعليمة واحدة في كل مرّة، ثمّ زرّ Exécuter)

تكافؤ الأنواع المطبَّق
    INTEGER PRIMARY KEY → AUTOINCREMENT PRIMARY KEY (NuméroAuto)
    INTEGER → LONG · REAL → DOUBLE · VARCHAR(n) → TEXT(n) · DATE → DATETIME
"""

import argparse
import glob
import os
import re
import sqlite3
import sys

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)
from adaptateur_access_sql import access_sql

# ---------------------------------------------------------------------------
def type_access(t: str, pk: bool = False) -> str:
    t = (t or "").upper()
    if pk and t.startswith("INT"):
        return "AUTOINCREMENT"
    if t.startswith("INT"):
        return "LONG"
    if t.startswith(("REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL")):
        return "DOUBLE"
    if t.startswith(("DATE", "TIME")):
        return "DATETIME"
    if t.startswith(("VARCHAR", "CHAR", "TEXT")):
        n = "".join(c for c in t if c.isdigit())
        return f"TEXT({n})" if n else "TEXT(255)"
    return "TEXT(255)"


def _decouper(liste: str) -> list:
    """يقسّم قائمة SELECT على الفواصل من المستوى الأعلى فقط."""
    out, prof, cur = [], 0, ""
    for ch in liste:
        if ch == "(":
            prof += 1
        elif ch == ")":
            prof -= 1
        if ch == "," and prof == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


AGREGATS = ("avg(", "sum(", "count(", "min(", "max(", "round(", "first(", "last(")


def adapter_sql_access(corps: str) -> str:
    """يقرّب SQL من لهجة Access/Jet :
       JOIN → INNER JOIN · alias → AS alias · GROUP BY complet · Round/Avg."""
    c = re.sub(r"(?<!INNER )(?<!LEFT )(?<!RIGHT )\bJOIN\b", "INNER JOIN", corps,
               flags=re.I)
    c = re.sub(r"\b(FROM|INNER JOIN|LEFT JOIN|RIGHT JOIN)\s+(\w+)\s+(?!AS\b|ON\b|"
               r"WHERE\b|GROUP\b|ORDER\b|INNER\b|LEFT\b|RIGHT\b)(\w+)\b",
               r"\1 \2 AS \3", c, flags=re.I)
    c = c.replace("ROUND(", "Round(").replace("AVG(", "Avg(")

    # Access يفرض ذكر كل الحقول غير المجمَّعة في GROUP BY
    m = re.search(r"SELECT\s+(.*?)\s+FROM", c, re.I | re.S)
    g = re.search(r"\bGROUP BY\b(.*?)(\bORDER BY\b|$)", c, re.I | re.S)
    if m and g:
        simples = [x for x in _decouper(m.group(1))
                   if not any(a in x.lower() for a in AGREGATS)]
        simples = [re.split(r"\s+AS\s+", x, flags=re.I)[0].strip() for x in simples]
        if simples:
            c = c[:g.start()] + "GROUP BY " + ", ".join(simples) + c[g.end(1):]
    return c


def _valeur(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    # تاريخ ISO → صيغة Access  #YYYY-MM-DD#
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return f"#{s}#"
    return f"'{s}'"


def instructions(db_sqlite: str) -> list:
    """يقرأ قاعدة SQLite ويُنتج تعليمات SQL بلهجة Access."""
    cx = sqlite3.connect(db_sqlite)
    cur = cx.cursor()
    tables, vues, sql = [], [], []
    connus = set()

    for nom, typ, texte in cur.execute(
            "SELECT name, type, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"):
        (vues if typ == "view" else tables).append((nom, texte))

    for nom, _ in tables:
        connus.add(nom.lower())
        connus.update(c[1].lower() for c in cur.execute(f'PRAGMA table_info("{nom}")'))

    # 1) الجداول
    for nom, _ in tables:
        cols, pk = [], []
        for _, cn, ct, notnull, _d, ipk in cur.execute(f'PRAGMA table_info("{nom}")'):
            morceau = f"[{cn}] {type_access(ct, bool(ipk))}"
            if notnull and not ipk:
                morceau += " NOT NULL"
            cols.append(morceau)
            if ipk:
                pk.append(cn)
        if pk:
            cols.append("CONSTRAINT PK_%s PRIMARY KEY (%s)"
                        % (nom, ", ".join(f"[{c}]" for c in pk)))
        sql.append(f"CREATE TABLE [{nom}] (\n  " + ",\n  ".join(cols) + "\n)")

    # 2) البيانات
    for nom, _ in tables:
        colonnes = [c[1] for c in cur.execute(f'PRAGMA table_info("{nom}")')]
        for ligne in cur.execute(f'SELECT * FROM "{nom}"'):
            sql.append("INSERT INTO [%s] (%s) VALUES (%s)" % (
                nom, ", ".join(f"[{c}]" for c in colonnes),
                ", ".join(_valeur(v) for v in ligne)))

    # 3) العلاقات (مع السلامة المرجعية)
    for nom, _ in tables:
        for r in cur.execute(f'PRAGMA foreign_key_list("{nom}")'):
            sql.append(
                f"ALTER TABLE [{nom}] ADD CONSTRAINT FK_{nom}_{r[3]} "
                f"FOREIGN KEY ([{r[3]}]) REFERENCES [{r[2]}] ([{r[4]}])")

    # 4) الاستعلامات — CREATE VIEW يصبح استعلامًا مسجَّلًا في Access
    for nom, texte in vues:
        m = re.search(r"\bAS\b", texte or "", re.I)
        if not m:
            continue
        corps = adapter_sql_access(texte[m.end():].strip().rstrip(";"))
        corps = access_sql(corps, connus)
        sql.append(f"CREATE VIEW [{nom}] AS\n{corps}")

    cx.close()
    return sql


# ---------------------------------------------------------------------------
def _nom_view_sans_crochets(instruction):
    """Le pilote ACE rejette « CREATE VIEW [N] » via ODBC ; le nom doit être
    nu (CREATE VIEW N AS ...). Access l'accepte aussi en Mode SQL manuel."""
    if not instruction.lstrip().upper().startswith("CREATE VIEW"):
        return instruction
    m = re.match(r"^CREATE\s+VIEW\s*\[([^\]]+)\]\s+(AS\b.*)$",
                 instruction, re.I | re.S)
    return "CREATE VIEW %s %s" % (m.group(1), m.group(2)) if m else instruction


def creer_accdb(cible: str, sql: list) -> str:
    import pyodbc
    import msaccessdb
    pil = [d for d in pyodbc.drivers() if "Access" in d]
    if not pil:
        raise RuntimeError("moteur ACE absent")
    if os.path.exists(cible):
        os.remove(cible)
    msaccessdb.create(cible)
    cx = pyodbc.connect(f"DRIVER={{{pil[0]}}};DBQ={os.path.abspath(cible)};")
    cur = cx.cursor()
    for s in sql:
        try:
            cur.execute(_nom_view_sans_crochets(s))
        except Exception as e:
            print(f"   ⚠️ {s.splitlines()[0][:60]}… : {e}", file=sys.stderr)
    cx.commit()
    cx.close()
    return cible


def ecrire_sql(cible: str, sql: list, source: str) -> str:
    with open(cible, "w", encoding="utf-8") as f:
        f.write(f"-- {os.path.basename(source)} → Access\n"
                "-- Access ▸ Créer ▸ Création de requête ▸ fermer l'assistant ▸\n"
                "--   bouton « Mode SQL » ▸ coller UNE instruction ▸ Exécuter (!)\n"
                "-- Les CREATE VIEW deviennent des requêtes : gardez exactement\n"
                "-- les noms R1_MoyenneParEleve, R2_ElevesEnEchec, R3_NotesInformatique\n\n")
        for s in sql:
            f.write(s + ";\n\n")
    return cible


def disponible() -> bool:
    try:
        import pyodbc
        import msaccessdb  # noqa: F401
        return bool([d for d in pyodbc.drivers() if "Access" in d])
    except ImportError:
        return False


def main():
    ap = argparse.ArgumentParser(description="SQLite → Access (.accdb)")
    ap.add_argument("source", help="fichier .db ou dossier contenant des .db")
    ap.add_argument("-o", "--out", default="bd_accdb")
    ap.add_argument("--sql-seulement", action="store_true")
    a = ap.parse_args()

    fichiers = (sorted(glob.glob(os.path.join(a.source, "**", "*.db"), recursive=True))
                if os.path.isdir(a.source) else [a.source])
    if not fichiers:
        sys.exit("aucun .db trouvé")

    os.makedirs(a.out, exist_ok=True)
    mode_accdb = disponible() and not a.sql_seulement
    print(f"Mode : {'.accdb réel (moteur ACE détecté)' if mode_accdb else 'SQL seulement'}"
          f"   →   {a.out}/")
    if not mode_accdb and not a.sql_seulement:
        print("   ℹ️ ACE/pyodbc absents : génération des scripts SQL à coller dans Access.\n"
              "      (Windows : pip install pyodbc msaccessdb + Access Database Engine)")

    for f in fichiers:
        sql = instructions(f)
        nom = os.path.splitext(os.path.basename(f))[0]
        if mode_accdb:
            c = creer_accdb(os.path.join(a.out, nom + ".accdb"), sql)
        else:
            c = ecrire_sql(os.path.join(a.out, nom + ".accdb.sql"), sql, f)
        print(f"  ✔ {os.path.basename(c):<28} {len(sql)} instructions")

    if mode_accdb:
        print("\nCorriger ensuite :\n"
              f"  python correcteur_access.py {a.out} -s {a.out}/solution.accdb --lang fr")


if __name__ == "__main__":
    main()
