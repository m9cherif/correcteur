#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyseur.py — محلّل أخطاء ملفات بايثون (متعدّد اللغات)
========================================================
  1. كشف أخطاء الصياغة والأخطاء المنطقية والأسلوبية.
  2. إدراج تعليقات داخل الملف: ❌ الخطأ · 💡 السبب · ✅ التصحيح.
  3. نقطة على 20 مع سلّم التنقيط.

لغة الشرح (ar / fr / en) — كل النصوص في langues.py:
    python analyseur.py mon_fichier.py --lang fr
    ANALYSEUR_LANG=en python analyseur.py mon_fichier.py

الاستعمال:
    python analyseur.py mon_fichier.py
    python analyseur.py mon_fichier.py -o resultat.py --lang fr
    python analyseur.py mon_fichier.py --fix
"""

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import List, Optional

import langues
import bareme
from langues import R, U, titre

ERREUR, AVERT = "erreur", "avertissement"     # قيم داخلية ثابتة (لا تُترجَم)


# ---------------------------------------------------------------------------
# 1) بنية تمثيل الخطأ الواحد
# ---------------------------------------------------------------------------
@dataclass
class Probleme:
    ligne: int
    code: str
    message: str
    explication: str
    correction: str
    ligne_corrigee: Optional[str] = None
    gravite: str = ERREUR              # ERREUR أو AVERT

    @property
    def icone(self) -> str:
        return "❌" if self.gravite == ERREUR else "⚠️"

    @property
    def gravite_txt(self) -> str:
        return U("erreur") if self.gravite == ERREUR else U("avertissement")


def _p(ligne, code, gravite=ERREUR, corrigee=None, **kw) -> Probleme:
    """يبني Probleme بنصوص مترجَمة انطلاقًا من رمز القاعدة."""
    m, e, c = R(code, **kw)
    return Probleme(ligne, code.split(".")[0], m, e, c, corrigee, gravite)


# ---------------------------------------------------------------------------
# 2) أخطاء الصياغة
# ---------------------------------------------------------------------------
def verifier_syntaxe(source: str, chemin: str) -> List[Probleme]:
    try:
        ast.parse(source, filename=chemin)
        return []
    except SyntaxError as e:
        ligne, texte = e.lineno or 1, (e.text or "").rstrip()
        msg = e.msg or "syntax"
        variante, corrigee = None, None

        if ("expected ':'" in msg or "invalid syntax" in msg) and re.match(
                r"\s*(if|for|while|def|class|elif|else|try|except|finally|with)\b", texte) \
                and not texte.rstrip().endswith(":"):
            variante, corrigee = "E001.colon", texte.rstrip() + ":"

        if "Missing parentheses in call to 'print'" in msg:
            variante = "E001.print"
            m = re.match(r"(\s*)print\s+(.*)", texte)
            if m:
                corrigee = f"{m.group(1)}print({m.group(2).rstrip()})"

        if "cannot assign to literal" in msg:
            variante = "E001.eq"

        base = _p(ligne, "E001", ERREUR, corrigee, msg=msg)
        if variante:                       # شرح أدقّ حسب الحالة
            _, ex, co = R(variante)
            base.explication, base.correction = ex, co
        return [base]


# ---------------------------------------------------------------------------
# 3) الفحص عبر شجرة AST
# ---------------------------------------------------------------------------
class Inspecteur(ast.NodeVisitor):
    def __init__(self, lignes: List[str]):
        self.lignes = lignes
        self.problemes: List[Probleme] = []
        self.imports = {}
        self.noms_utilises = set()

    def visit_Import(self, node):
        for a in node.names:
            self.imports[(a.asname or a.name).split(".")[0]] = node.lineno
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for a in node.names:
            if a.name != "*":
                self.imports[a.asname or a.name] = node.lineno
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.noms_utilises.add(node.id)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.type is None:
            self.problemes.append(_p(node.lineno, "W101", AVERT,
                                     self._indent(node.lineno) + "except Exception as e:"))
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        for d in node.args.defaults + [x for x in node.args.kw_defaults if x]:
            if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                self.problemes.append(_p(node.lineno, "E102", ERREUR, nom=node.name))
        self.generic_visit(node)

    def visit_Compare(self, node):
        for op, comp in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) \
                    and comp.value is None:
                sym = "==" if isinstance(op, ast.Eq) else "!="
                remp = "is" if isinstance(op, ast.Eq) else "is not"
                src = self._src(node.lineno)
                self.problemes.append(_p(
                    node.lineno, "W103", AVERT,
                    src.replace(f"{sym} None", f"{remp} None") if src else None,
                    sym=sym, remp=remp))
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) \
                and isinstance(node.right, ast.Constant) and node.right.value == 0:
            self.problemes.append(_p(node.lineno, "E104", ERREUR))
        self.generic_visit(node)

    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Name) \
                and node.targets[0].id == node.value.id:
            self.problemes.append(_p(node.lineno, "W105", AVERT,
                                     nom=node.targets[0].id))
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == "open" \
                and not getattr(node, "_dans_with", False):
            self.problemes.append(_p(node.lineno, "W106", AVERT))
        self.generic_visit(node)

    def visit_With(self, node):
        for item in node.items:
            for n in ast.walk(item.context_expr):
                n._dans_with = True
        self.generic_visit(node)

    def _src(self, ligne: int) -> str:
        return self.lignes[ligne - 1].rstrip("\n") if 0 < ligne <= len(self.lignes) else ""

    def _indent(self, ligne: int) -> str:
        s = self._src(ligne)
        return s[:len(s) - len(s.lstrip())]


def verifier_ast(source: str, lignes: List[str]) -> List[Probleme]:
    insp = Inspecteur(lignes)
    insp.visit(ast.parse(source))
    for nom, ln in insp.imports.items():
        if nom in insp.noms_utilises:
            continue
        reste = "\n".join(l for i, l in enumerate(lignes, 1) if i != ln)
        if not re.search(rf"\b{re.escape(nom)}\b", reste):
            insp.problemes.append(_p(ln, "W107", AVERT, nom=nom))
    return insp.problemes


# ---------------------------------------------------------------------------
# 4) فحوص نصّية سطرًا بسطر
# ---------------------------------------------------------------------------
def verifier_lignes(lignes: List[str]) -> List[Probleme]:
    out = []
    for i, ligne in enumerate(lignes, 1):
        nue = ligne.rstrip("\n")
        if "\t" in nue and "    " in nue:
            out.append(_p(i, "E108", ERREUR, nue.replace("\t", "    ")))
        if len(nue) > 99:
            out.append(_p(i, "W109", AVERT, n=len(nue)))
        if re.search(r"\bexcept\b.*:\s*pass\s*$", nue):
            out.append(_p(i, "W110", AVERT))
    return out


# ---------------------------------------------------------------------------
# 4-bis) الترجمة الحقيقية عبر python.exe (py_compile)
# ---------------------------------------------------------------------------
def detecter_python() -> str:
    """يعيد مسار مفسّر بايثون الحقيقي (python.exe على ويندوز إن وُجد)."""
    for cand in (os.environ.get("PYTHON_EXE"), "python.exe", "python3", "python", "py"):
        if not cand:
            continue
        chemin = shutil.which(cand)
        if chemin:
            return chemin
    return sys.executable


PYTHON = detecter_python()


def version_python(py: str = None) -> str:
    py = py or PYTHON
    try:
        r = subprocess.run([py, "-V"], capture_output=True, text=True, timeout=10)
        return (r.stdout or r.stderr).strip()
    except Exception:
        return "?"


_RE_LIGNE = re.compile(r'File "(?P<f>[^"]+)", line (?P<n>\d+)')


def _py_compile(py: str, chemin: str, strict: bool):
    """يشغّل py_compile في المفسّر الحقيقي؛ strict يحوّل SyntaxWarning إلى خطأ."""
    env = dict(os.environ, PYTHONPYCACHEPREFIX=tempfile.gettempdir(),
               PYTHONIOENCODING="utf-8")
    cmd = [py] + (["-W", "error::SyntaxWarning"] if strict else []) + \
        ["-m", "py_compile", chemin]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=env)


def verifier_compilation(chemin: str, py: str = None) -> List[Probleme]:
    """يمرّر الملف على المفسّر الحقيقي (python.exe) عبر py_compile:
       • خطأ ترجمة فعلي        → E002 (خاصّ بنسخة بايثون المستهدَفة)
       • SyntaxWarning فقط     → W111 (بناء صحيح لكنّه شبه مؤكّد أنّه خطأ)"""
    py = py or PYTHON
    try:
        normal = _py_compile(py, chemin, strict=False)
    except Exception as e:
        return [Probleme(1, "E002", f"py_compile: {e}", "", "", None, ERREUR)]

    def _ligne(err: str) -> int:
        no = 1
        for l in err.splitlines():
            t = _RE_LIGNE.search(l)
            if t and os.path.basename(t.group("f")) == os.path.basename(chemin):
                no = int(t.group("n"))
        return no

    def _msg(err: str) -> str:
        lignes = [l.strip() for l in err.splitlines() if l.strip()]
        return lignes[-1] if lignes else "compile error"

    if normal.returncode != 0:
        err = normal.stderr or ""
        return [_p(_ligne(err), "E002", ERREUR,
                   py=os.path.basename(py), msg=_msg(err)[:200])]

    try:
        strict = _py_compile(py, chemin, strict=True)
    except Exception:
        return []
    if strict.returncode != 0:
        err = strict.stderr or ""
        msg = _msg(err)
        for pref in ("SyntaxWarning:", "SyntaxError:"):
            if pref in msg:
                msg = msg.split(pref, 1)[1].strip()
        return [_p(_ligne(err), "W111", AVERT, msg=msg[:200])]
    return []


def compiler_source(source: str, py: str = None) -> List[Probleme]:
    """نفس الشيء انطلاقًا من نصّ في الذاكرة (يستعمله IDE)."""
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
    f.write(source)
    f.close()
    try:
        probs = verifier_compilation(f.name, py)
    finally:
        try:
            os.unlink(f.name)
            pyc = f.name + "c"
            os.path.exists(pyc) and os.unlink(pyc)
        except OSError:
            pass
    return probs


# ---------------------------------------------------------------------------
# 5) التنقيط على 20
# ---------------------------------------------------------------------------
# السلّم لم يعد ثابتًا هنا: يأتي من bareme.py (ملفّ JSON قابل للتعديل)
BAREME = bareme.regles()          # يبقى للتوافق مع الكود القديم


def calculer_note_max():
    return bareme.note_max()


def mentions_actives():
    """يمزج حدود السلّم (bareme.seuils) بنصوص التقديرات (langues)."""
    textes = [m for _, m in langues.mentions()]
    seuils = bareme.seuils() + [0]
    return list(zip(seuils[:len(textes)], textes))


def calculer_note(problemes: List[Probleme]):
    """يطبّق السلّم الحالي: قواعد نشِطة، سقف لكل قاعدة، تسامح، خطأ قاتل."""
    global BAREME
    BAREME = bareme.regles()
    maxi = bareme.note_max()

    compte = {}
    for p in problemes:
        if p.code in BAREME:                      # قاعدة معطَّلة = تُشرح ولا تُنقِص
            compte[p.code] = compte.get(p.code, 0) + 1

    # التسامح: تُعفى أوّل N تحذيرات (الأخفّ خصمًا أوّلًا)
    reste = bareme.tolerance()
    if reste:
        for code in sorted(compte, key=lambda c: BAREME[c][0]):
            if not code.startswith("W"):
                continue
            pris = min(reste, compte[code])
            compte[code] -= pris
            reste -= pris
            if not reste:
                break

    detail, total = [], 0.0
    for code, (unite, plafond) in BAREME.items():
        n = compte.get(code, 0)
        if n:
            applique = min(n * unite, plafond)
            total += applique
            detail.append((code, titre(code), n, unite, applique, plafond))

    detail.sort(key=lambda d: -d[4])
    note = max(0.0, maxi - total)
    if bareme.erreur_fatale() and any(p.gravite == ERREUR and p.code in ("E001", "E002")
                                      for p in problemes):
        note = 0.0
    note = round(note, bareme.arrondi())
    mention = next((m for seuil, m in mentions_actives() if note >= seuil),
                   langues.mentions()[-1][1])
    return note, mention, detail


def bloc_note(note: float, mention: str, detail) -> List[str]:
    L = [f"📊 {U('note_finale')} : {note} / {bareme.note_max():g}   ({mention})",
         f"⚖  {U('c_regle')} : {bareme.nom()}   ({len(bareme.regles())} règles actives"
         + (f", tolérance {bareme.tolerance()}" if bareme.tolerance() else "") + ")",
         "", U("bareme_titre"),
         f"{U('c_code'):<7}{U('c_regle'):<42}{U('c_nb'):>6}"
         f"{U('c_unite'):>8}{U('c_deduit'):>9}{U('c_plafond'):>8}",
         "-" * 80]
    if not detail:
        L.append(U("aucun_deduit"))
    for code, lib, n, unite, applique, plafond in detail:
        lib = lib if len(lib) <= 40 else lib[:39] + "…"
        L.append(f"{code:<7}{lib:<42}{n:>6}{unite:>8}{applique:>9.2f}{plafond:>8}")
    L += ["-" * 80,
          f"{U('total_deduit'):<55}{sum(d[4] for d in detail):>9.2f}",
          f"{bareme.note_max():g} − {U('total_deduit').lower()} = "
          f"{U('note').lower():<38}{note:>9.2f}", "", U("note_bas")]
    return L


# ---------------------------------------------------------------------------
# 6) توليد الملف المشروح
# ---------------------------------------------------------------------------
def annoter(lignes: List[str], problemes: List[Probleme], nom: str,
            appliquer: bool = False) -> str:
    par_ligne = {}
    for p in problemes:
        par_ligne.setdefault(p.ligne, []).append(p)

    err = sum(1 for p in problemes if p.gravite == ERREUR)
    note, mention, detail = calculer_note(problemes)

    entete = ["=" * 75, f"{U('rapport')} — {nom}",
              f"{U('nb_err')}: {err} | {U('nb_warn')}: {len(problemes) - err}",
              f"📊 {U('note')}: {note} / 20  →  {mention}",
              U("legende"), "=" * 75] + bloc_note(note, mention, detail) + ["=" * 75]
    sortie = ["\n".join("# " + l for l in entete), ""]

    for i, ligne in enumerate(lignes, 1):
        contenu = ligne.rstrip("\n")
        probs = par_ligne.get(i, [])
        if probs:
            ind = contenu[:len(contenu) - len(contenu.lstrip())]
            sortie.append(f"{ind}# " + "-" * 60)
            for p in probs:
                sortie.append(f"{ind}# {p.icone} [{p.code}] {U('ligne')} {p.ligne}: {p.message}")
                sortie.append(f"{ind}# 💡 {U('cause')}: {p.explication}")
                sortie.append(f"{ind}# ✅ {U('fix')}: {p.correction}")
                if p.ligne_corrigee:
                    sortie.append(f"{ind}# ✅ {U('corrige')}:")
                    sortie.append(f"{ind}#     {p.ligne_corrigee.strip()}")
            sortie.append(f"{ind}# " + "-" * 60)
            corrigee = next((p.ligne_corrigee for p in probs if p.ligne_corrigee), None)
            if appliquer and corrigee:
                sortie.append(corrigee)
                sortie.append(f"{ind}# ({U('original')}) {contenu.strip()}")
                continue
        sortie.append(contenu)
    return "\n".join(sortie) + "\n"


def rapport_console(problemes: List[Probleme], chemin: str) -> None:
    note, mention, detail = calculer_note(problemes)
    if not problemes:
        print(f"✅ {chemin}: {U('aucun')}")
        print(f"📊 {U('note')}: {note} / 20 ({mention})")
        return

    print(f"\n📄 {U('fichier')}: {chemin} — {len(problemes)} {U('remarques')}\n" + "=" * 80)
    for p in sorted(problemes, key=lambda x: x.ligne):
        print(f"{p.icone} {U('ligne')} {p.ligne:>4} [{p.code}] {p.message}")
        print(f"   💡 {U('cause')}   : {p.explication}")
        print(f"   ✅ {U('fix')} : {p.correction}")
        if p.ligne_corrigee:
            print(f"   ➜ {U('suggestion')} : {p.ligne_corrigee.strip()}")
        print("-" * 80)
    print("\n" + "=" * 80)
    for l in bloc_note(note, mention, detail):
        print(l)
    print("=" * 80)


# ---------------------------------------------------------------------------
# 7) الواجهة البرمجية ونقطة الدخول
# ---------------------------------------------------------------------------
def analyser_source(source: str, nom: str = "<memoire>",
                    py: Optional[str] = None) -> List[Probleme]:
    """يحلّل نصًّا مصدريًّا مباشرة — يستعمله correcteur.py و ide.py.
    py: مسار python.exe لإجراء ترجمة حقيقية (None = تخطّي هذه الخطوة)."""
    lignes = source.splitlines()
    problemes = verifier_syntaxe(source, nom)
    if not problemes:
        problemes += verifier_ast(source, lignes)
    problemes += verifier_lignes(lignes)
    if py:
        vus = {(p.ligne, p.code) for p in problemes}
        for p in compiler_source(source, py):
            if (p.ligne, p.code) not in vus:
                problemes.append(p)
    return problemes


def analyser(chemin: str, sortie: Optional[str] = None, appliquer: bool = False,
             py: Optional[str] = None) -> List[Probleme]:
    with open(chemin, encoding="utf-8") as f:
        source = f.read()
    problemes = analyser_source(source, chemin)
    if py:
        vus = {(p.ligne, p.code) for p in problemes}
        problemes += [p for p in verifier_compilation(chemin, py)
                      if (p.ligne, p.code) not in vus]
    rapport_console(problemes, chemin)

    if sortie is None:
        base, ext = os.path.splitext(chemin)
        sortie = f"{base}_annote{ext}"
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(annoter(source.splitlines(), problemes,
                        os.path.basename(chemin), appliquer))
    print(f"\n💾 {U('sortie')}: {sortie}")
    return problemes


def main() -> int:
    ap = argparse.ArgumentParser(description="محلّل أخطاء بايثون مع شرح وتصحيح ونقطة")
    ap.add_argument("fichier")
    ap.add_argument("-o", "--out")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--bareme", help="ملفّ سلّم JSON أو اسم ملفّ تعريف "
                                     "(standard / debutant / examen / algorithmique)")
    ap.add_argument("--python", nargs="?", const=PYTHON, default=PYTHON,
                    help="مسار python.exe للترجمة الحقيقية (py_compile). "
                         "استعمل --python \"\" لتعطيلها")
    ap.add_argument("--lang", choices=list(langues.LANGUES), default=langues.langue(),
                    help="لغة الشرح: ar (افتراضي) | fr | en")
    a = ap.parse_args()

    langues.definir_langue(a.lang)
    if a.bareme:
        bareme.charger_profil(a.bareme)
        print(f"⚖  {U('c_regle')} : {bareme.nom()}  ({bareme.chemin()})")
    if not os.path.isfile(a.fichier):
        print(f"❌ {U('fichier')}: {a.fichier} ✗", file=sys.stderr)
        return 2
    py = a.python or None
    if py:
        print(f"🐍 {U('interpreteur')}: {py}  ({version_python(py)})")
    problemes = analyser(a.fichier, a.out, a.fix, py)
    return 1 if any(p.gravite == ERREUR for p in problemes) else 0


if __name__ == "__main__":
    sys.exit(main())
