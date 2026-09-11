#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adaptateur_access_sql.py — SQL standard SQLite → dialecte Access/Jet exécutable
================================================================================
Le moteur ACE, tel qu'invoqué par ODBC/OLE DB sur un fichier .accdb, refuse :
  • les identifiants nus dans les jointures (il faut [Élève].Nom, …) ;
  • les enchaînements INNER JOIN non parenthésés (il faut ((A JOIN B) JOIN C)).

Ce module réécrit un SELECT pour qu'il soit accepté par ACE, en restant
idempotent (un SQL déjà crocheté/parenthésé n'est pas modifié).

    access_sql(requete, connus=None)
        connus : ensemble (minuscules) des noms de tables et colonnes connus ;
                 prolonge la mise-entre-crochets des identifiants nus.

Utilisé par bd/convertir_en_accdb.py (vues stockées) et
correcteur_access.py (exécution des requêtes) pour rester cohérents.
"""

import re

# Mots réservés / fonctions : jamais mis entre crochets.
_MOTS_RESERVES = frozenset("""
    select from where group by order as on inner join left right outer full
    and or not in is null exists between like distinct top asc desc having
    union all into values set update delete insert table view create
    alter add constraint primary key foreign references name
    avg count sum min max round first last format date now today
    stdev stdevp var varp abs int len mid chr space fix exp log
    sqr cos sin tan atn iif nz cdbl cint cstr clng cdate isnull
""".split())

_FIN_SEGMENT = frozenset(("where", "group", "order", "having", "union"))


def _decouper_mots(sql):
    """Découpe (type, texte) en respectant chaînes '…' / "…", identifiants [..],
    nombres et ponctuation. Le texte du jeton n'est jamais modifié."""
    out = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch.isspace():
            j = i + 1
            while j < n and sql[j].isspace():
                j += 1
            out.append(("espace", sql[i:j]))
            i = j
        elif ch in "'\"":
            j = i + 1
            while j < n:
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(("texte", sql[i:j]))
            i = j
        elif ch == "[":
            j = sql.find("]", i + 1)
            if j < 0:
                j = n - 1
            out.append(("crochet", sql[i:j + 1]))
            i = j + 1
        elif ch.isdigit():
            j = i + 1
            while j < n and (sql[j].isdigit() or sql[j] in ".,eE+-"):
                j += 1
            out.append(("nombre", sql[i:j]))
            i = j
        elif ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] in "_$"):
                j += 1
            out.append(("mot", sql[i:j]))
            i = j
        else:
            out.append(("signe", ch))
            i += 1
    return out


def _entre_crochets(sql, connus):
    """Met entre crochets les identifiants nus connus et ceux suivis de '.'."""
    if not connus:
        connus = set()
    out = []
    prev = None  # dernier jeton non espace
    for typ, txt in _decouper_mots(sql):
        if typ == "mot":
            bas = txt.lower()
            if prev == "." or (bas in connus and bas not in _MOTS_RESERVES):
                typ, txt = "crochet", "[" + txt + "]"
        out.append((typ, txt))
        if typ not in ("espace",):
            prev = txt
    return out


def _relire(toks):
    return "".join(t for _, t in toks)


def _mot_index(s, mot):
    m = re.search(r"\b" + re.escape(mot) + r"\b", s, re.I)
    return m.start() if m else -1


def _segmenter(clause):
    """Découpe la clause FROM en segments commençant chacun par un mot-clé de
    jointure : [table alias], "INNER JOIN t2 AS a2 ON cond", … None si la
    clause est déjà parenthésée (forme Access) ou absente."""
    if clause.lstrip()[:1] == "(":
        return None
    n = len(clause)
    bornes = []
    i, prof = 0, 0
    while i < n:
        ch = clause[i]
        if ch == "(":
            prof += 1
            i += 1
            continue
        if ch == ")":
            prof = max(prof - 1, 0)
            i += 1
            continue
        if prof == 0 and (clause[i].isalpha() or clause[i] == "_"):
            m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", clause[i:], re.I)
            mot = m.group(0).lower()
            if mot == "join":
                bornes.append((i, i + m.end()))
                i += m.end()
                continue
            if mot in ("inner", "left", "right", "outer"):
                j = i + m.end()
                while j < n and clause[j].isspace():
                    j += 1
                if clause[j:j + 4].lower() == "join":
                    bornes.append((i, j + 4))
                    i = j + 4
                    continue
                i += m.end()
                continue
            i = i + m.end()
            continue
        i += 1
    if not bornes:
        return [clause]
    segs = [clause[:bornes[0][0]]]
    for k, (db, _fin) in enumerate(bornes):
        suivant = bornes[k + 1][0] if k + 1 < len(bornes) else n
        segs.append(clause[db:suivant])
    return segs


def _parenth_joins(sql):
    """Parenthèse la suite de FROM quand plusieurs JOIN s'enchaînent (ACE le
    réclame). Les formes déjà parenthésées sont laissées telles quelles."""
    if "JOIN" not in sql.upper():
        return sql
    i = _mot_index(sql, "from")
    if i < 0:
        return sql
    deb = i + len("from")
    prof, fin = 0, len(sql)
    j = deb
    while j < len(sql):
        ch = sql[j]
        if ch == "(":
            prof += 1
        elif ch == ")":
            prof = max(prof - 1, 0)
        elif prof == 0 and (ch.isalpha() or ch == "_"):
            m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", sql[j:], re.I)
            if m and m.group(0).lower() in _FIN_SEGMENT:
                fin = j
                break
            j = j + m.end() if m else j + 1
            continue
        j += 1
    segs = _segmenter(sql[deb:fin])
    if not segs or len(segs) <= 2:  # 0 ou 1 jointure
        return sql
    premier = segs[0].strip()
    joins = [s.strip() for s in segs[1:]]
    chaine = premier + " " + joins[0]
    for j in joins[1:]:
        chaine = "(" + chaine + ") " + j
    return sql[:deb] + " " + chaine + " " + sql[fin:]


def access_sql(sql, connus=None):
    """Version de sql exécutable par le moteur Access/Jet (idempotente)."""
    if not sql:
        return sql
    return _parenth_joins(_relire(_entre_crochets(sql, connus)))