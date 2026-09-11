#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
correcteur.py — تصحيح محاولة التلميذ بمقارنتها بالحلّ النموذجي
================================================================
يجمع بين ثلاثة محاور، والمجموع على 20:

    (أ) جودة الكود        6 نقاط   ← من analyseur.py (أخطاء وتحذيرات)
    (ب) صحّة النتائج      10 نقاط  ← تنفيذ اختبارات ومقارنتها بالحلّ
    (ج) المطابقة البنيوية 4 نقاط   ← وجود الدوال المطلوبة بنفس الوسائط

الاستعمال:
    python correcteur.py essai_eleve.py -s solution.py
    python correcteur.py essai_eleve.py -s solution.py -t tests.json
    python correcteur.py essai_eleve.py -s solution.py --montrer-solution

صيغة tests.json (اختياري — إن غاب تُولَّد الاختبارات من الحلّ):
[
  {"fonction": "ajouter", "args": [2, 3]},
  {"fonction": "diviser", "args": [10, 2]},
  {"stdin": "5\\n", "nom": "تنفيذ كامل"}
]
لا حاجة لكتابة النتيجة المنتظَرة: تُؤخذ من الحلّ النموذجي.
"""

import argparse
import ast
import difflib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from typing import Any, Dict, List, Optional, Tuple

import langues
import bareme
from langues import U
from analyseur import (analyser_source, calculer_note, bloc_note,
                       detecter_python, version_python)

TIMEOUT = 5                  # ثوانٍ لكل تنفيذ
PYTHON = detecter_python()   # python.exe الحقيقي (يمكن تغييره بـ --python)
def PT(axe):
    """وزن المحور من السلّم الحالي (قابل للتعديل بلا لمس الكود)."""
    return bareme.axes().get(axe, 0.0)


PT_QUALITE, PT_TESTS, PT_STRUCTURE = 6.0, 10.0, 4.0   # للتوافق فقط


# ---------------------------------------------------------------------------
# 1) تنفيذ معزول (subprocess) — لا نُشغّل كود التلميذ داخل مفسّرنا
# ---------------------------------------------------------------------------
RUNNER = textwrap.dedent("""
    import importlib.util, json, sys, io, contextlib
    chemin, fonction, args = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
    spec = importlib.util.spec_from_file_location("m_eleve", chemin)
    mod = importlib.util.module_from_spec(spec)
    tampon = io.StringIO()
    try:
        with contextlib.redirect_stdout(tampon):
            spec.loader.exec_module(mod)
            if fonction:
                f = getattr(mod, fonction)
                res = f(*args)
            else:
                res = None
        print("@@RES@@" + json.dumps(
            {"ok": True, "valeur": repr(res), "sortie": tampon.getvalue()},
            ensure_ascii=False))
    except Exception as e:
        print("@@RES@@" + json.dumps(
            {"ok": False, "erreur": f"{type(e).__name__}: {e}",
             "sortie": tampon.getvalue()}, ensure_ascii=False))
""")


def executer(chemin: str, fonction: Optional[str] = None,
             args: Optional[list] = None, stdin: str = "") -> Dict[str, Any]:
    """ينفّذ ملفًا (ودالّة منه اختياريًّا) ويُرجع النتيجة والمخرجات."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(RUNNER)
        runner = f.name
    try:
        p = subprocess.run(
            [PYTHON, runner, chemin, fonction or "",
             json.dumps(args or [], ensure_ascii=False)],
            input=stdin, capture_output=True, text=True, timeout=TIMEOUT)
        for l in p.stdout.splitlines():
            if l.startswith("@@RES@@"):
                return json.loads(l[7:])
        return {"ok": False, "erreur": (p.stderr or "لا نتيجة").strip()[:300],
                "sortie": p.stdout}
    except subprocess.TimeoutExpired:
        return {"ok": False, "erreur": U("timeout", s=TIMEOUT), "sortie": ""}
    finally:
        os.unlink(runner)


# ---------------------------------------------------------------------------
# 2) استخراج البنية (الدوال ووسائطها)
# ---------------------------------------------------------------------------
def signatures(source: str) -> Dict[str, List[str]]:
    out = {}
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return out
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[n.name] = [a.arg for a in n.args.args]
    return out


def tests_auto(sig_solution: Dict[str, List[str]]) -> List[dict]:
    """يولّد اختبارًا لكل دالة في الحلّ عندما لا يوفّر الأستاذ ملف اختبارات."""
    normaux = {0: 2, 1: 3, 2: 5, 3: 7}
    tests = []
    for nom, params in sig_solution.items():
        if nom.startswith("_"):
            continue
        n = len(params)
        jeux = [[normaux.get(i, 1) for i in range(n)]]       # حالة عادية
        if n:
            jeux.append([0] * n)                              # حالة حدّية: أصفار
            jeux.append([-4] + [normaux.get(i, 1) for i in range(1, n)])  # سالب
        for args in jeux:
            tests.append({"fonction": nom, "args": args,
                          "nom": f"{nom}({', '.join(map(str, args))})"})
    tests.append({"stdin": "", "nom": U("exec_complet")})
    return tests


# ---------------------------------------------------------------------------
# 3) المحاور الثلاثة
# ---------------------------------------------------------------------------
def axe_qualite(source_eleve: str) -> Tuple[float, list, list]:
    problemes = analyser_source(source_eleve, "essai_eleve.py", py=PYTHON)
    note20, mention, detail = calculer_note(problemes)
    return round(note20 / bareme.note_max() * PT("qualite"), 2), problemes, detail


def axe_tests(f_eleve: str, f_solution: str, tests: List[dict]):
    resultats = []
    for t in tests:
        attendu = executer(f_solution, t.get("fonction"), t.get("args"),
                           t.get("stdin", ""))
        obtenu = executer(f_eleve, t.get("fonction"), t.get("args"),
                          t.get("stdin", ""))
        if t.get("fonction"):
            if not attendu.get("ok"):
                # الحلّ نفسه يُطلق استثناءً: نقبل نفس نوع الاستثناء عند التلميذ
                type_att = str(attendu.get("erreur", "")).split(":")[0]
                type_obt = str(obtenu.get("erreur", "")).split(":")[0]
                ok = (not obtenu.get("ok")) and type_att == type_obt
                att = f"{U('exception')} {type_att}"
                obt = (f"{U('exception')} {type_obt}" if not obtenu.get("ok")
                       else obtenu.get("valeur"))
                resultats.append({"nom": t.get("nom") or "test", "reussi": bool(ok),
                                  "attendu": att, "obtenu": obt})
                continue
            ok = obtenu.get("ok") and obtenu.get("valeur") == attendu.get("valeur")
            att, obt = attendu.get("valeur"), obtenu.get("valeur")
        else:
            ok = (obtenu.get("ok") and attendu.get("ok")
                  and obtenu.get("sortie", "").strip() == attendu.get("sortie", "").strip())
            att, obt = attendu.get("sortie", "").strip(), obtenu.get("sortie", "").strip()
        resultats.append({
            "nom": t.get("nom") or t.get("fonction") or "test",
            "reussi": bool(ok),
            "attendu": att,
            "obtenu": obt if obtenu.get("ok") else f"⛔ {obtenu.get('erreur')}",
        })
    if not resultats:
        return 0.0, resultats
    reussis = sum(1 for r in resultats if r["reussi"])
    return round(reussis / len(resultats) * PT("tests"), 2), resultats


def axe_structure(src_eleve: str, src_solution: str):
    se, ss = signatures(src_eleve), signatures(src_solution)
    remarques = []
    total_s = PT("structure")
    if not ss:
        return total_s, []
    points = 0.0
    part = total_s / len(ss)
    for nom, params in ss.items():
        if nom not in se:
            remarques.append("❌ " + U("fn_manquante", nom=nom))
        elif len(se[nom]) != len(params):
            points += part / 2
            remarques.append("⚠️ " + U("fn_args", nom=nom, a=len(se[nom]),
                                        b=len(params)))
        else:
            points += part
            if se[nom] != params:
                remarques.append("ℹ️ " + U("fn_noms", nom=nom))
    extra = set(se) - set(ss)
    if extra:
        remarques.append("ℹ️ " + U("fn_extra", liste=", ".join(sorted(extra))))
    return round(min(points, total_s), 2), remarques


# ---------------------------------------------------------------------------
# 4) التصحيح الكامل
# ---------------------------------------------------------------------------
def corriger(f_eleve: str, f_solution: str,
             f_tests: Optional[str] = None) -> Dict[str, Any]:
    src_e = open(f_eleve, encoding="utf-8").read()
    src_s = open(f_solution, encoding="utf-8").read()

    tests = json.load(open(f_tests, encoding="utf-8")) if f_tests \
        else tests_auto(signatures(src_s))

    n_q, problemes, detail_q = axe_qualite(src_e)
    n_t, resultats = axe_tests(f_eleve, f_solution, tests)
    n_s, remarques = axe_structure(src_e, src_s)

    note = round(n_q + n_t + n_s, 2)
    diff = list(difflib.unified_diff(
        src_e.splitlines(), src_s.splitlines(),
        fromfile="محاولة التلميذ", tofile="الحلّ النموذجي", lineterm="", n=2))

    return {"note": note, "qualite": n_q, "tests": n_t, "structure": n_s,
            "problemes": problemes, "detail_qualite": detail_q,
            "resultats": resultats, "remarques": remarques, "diff": diff,
            "solution": src_s}


def afficher(r: Dict[str, Any], montrer_solution: bool = False) -> None:
    print("\n" + "=" * 80)
    print(f"📊 {U('note_finale')} : {r['note']} / 20")
    print("=" * 80)
    print(f"{U('axe'):<38}{U('note'):>10}{U('sur'):>8}")
    print("-" * 80)
    print(f"{U('ax_qualite'):<38}{r['qualite']:>10}{PT('qualite'):>8}")
    print(f"{U('ax_tests'):<38}{r['tests']:>10}{PT('tests'):>8}")
    print(f"{U('ax_structure'):<38}{r['structure']:>10}{PT('structure'):>8}")
    print("-" * 80)
    print(f"{U('total'):<38}{r['note']:>10}{bareme.note_max():>8g}")

    print(f"\n🧪 {U('tests')}:")
    for t in r["resultats"]:
        print(f"  {'✅' if t['reussi'] else '❌'} {t['nom']}")
        if not t["reussi"]:
            print(f"      {U('attendu')} : {t['attendu']}")
            print(f"      {U('obtenu')} : {t['obtenu']}")

    if r["remarques"]:
        print(f"\n🏗️  {U('structure')}:")
        for m in r["remarques"]:
            print("  " + m)

    if r["problemes"]:
        print(f"\n🔍 {U('sur_code')}:")
        for p in sorted(r["problemes"], key=lambda x: x.ligne):
            print(f"  {p.icone} {U('ligne')} {p.ligne} [{p.code}] {p.message}")
            print(f"      💡 {p.explication}")
            print(f"      ✅ {p.correction}")

    if montrer_solution:
        print(f"\n📘 {U('solution')}:\n" + "-" * 80)
        print(r["solution"])
        print("-" * 80 + f"\n🔀 {U('diff')}:")
        for l in r["diff"]:
            print("  " + l)
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="تصحيح محاولة تلميذ مقابل حلّ نموذجي")
    ap.add_argument("essai", help="ملف محاولة التلميذ")
    ap.add_argument("-s", "--solution", required=True, help="ملف الحلّ النموذجي")
    ap.add_argument("-t", "--tests", help="ملف اختبارات JSON (اختياري)")
    ap.add_argument("--montrer-solution", action="store_true",
                    help="عرض الحلّ والفرق بعد التصحيح")
    ap.add_argument("--json", help="حفظ التقرير بصيغة JSON")
    ap.add_argument("--bareme", help="ملفّ سلّم JSON أو اسم ملفّ تعريف")
    ap.add_argument("--python", default=PYTHON,
                    help="مسار python.exe المستعمل للترجمة والتنفيذ")
    ap.add_argument("--lang", choices=list(langues.LANGUES), default=langues.langue(),
                    help="لغة الشرح: ar | fr | en")
    a = ap.parse_args()
    langues.definir_langue(a.lang)
    if a.bareme:
        bareme.charger_profil(a.bareme)
        print(f"⚖  {bareme.nom()}  ({bareme.chemin()})")
    globals()["PYTHON"] = a.python
    print(f"🐍 {U('interpreteur')}: {a.python}  ({version_python(a.python)})")

    for f in (a.essai, a.solution):
        if not os.path.isfile(f):
            print(f"❌ الملف غير موجود: {f}", file=sys.stderr)
            return 2

    r = corriger(a.essai, a.solution, a.tests)
    afficher(r, a.montrer_solution)

    if a.json:
        brut = {k: v for k, v in r.items() if k != "problemes"}
        brut["problemes"] = [p.__dict__ for p in r["problemes"]]
        json.dump(brut, open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"💾 التقرير: {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
