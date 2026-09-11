#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
interpreteurs.py — اكتشاف مفسّرات بايثون وإدارتها
==================================================
يبحث عن كل نسخ python/python.exe المثبَّتة على الجهاز، يقرأ معلوماتها،
ويسمح بتشغيل نفس الكود على أكثر من نسخة لمقارنة التوافق.

    import interpreteurs as I
    I.scanner()                     # [{chemin, version, ...}, ...]
    I.info("C:/Python312/python.exe")
    I.matrice_compatibilite(source, [c1, c2])

أماكن البحث:
    • PATH (python, python3, python.exe, py, python3.8 … python3.15)
    • ويندوز: py -0p ، C:\\Python3*, Program Files, LocalAppData, Anaconda
    • لينكس/ماك: /usr/bin, /usr/local/bin, ~/.pyenv/versions/*
    • Termux: $PREFIX/bin
    • البيئات الافتراضية في المجلّد الحالي: venv/.venv/env → Scripts|bin
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

_CACHE = {}
WIN = os.name == "nt"

_SONDE = (
    "import json,sys,struct,platform,importlib.util;"
    "print(json.dumps({"
    "'version':platform.python_version(),"
    "'binaire':sys.executable,"
    "'bits':struct.calcsize('P')*8,"
    "'impl':platform.python_implementation(),"
    "'os':platform.system(),"
    "'venv':sys.prefix!=getattr(sys,'base_prefix',sys.prefix),"
    "'prefix':sys.prefix,"
    "'pip':importlib.util.find_spec('pip') is not None,"
    "'pyqt5':importlib.util.find_spec('PyQt5') is not None,"
    "'majeur':sys.version_info[0],'mineur':sys.version_info[1]}))"
)


# ---------------------------------------------------------------------------
def candidats() -> list:
    """كل المسارات المحتمَلة قبل التحقّق."""
    noms = ["python", "python3", "py"] + \
           [f"python3.{m}" for m in range(6, 16)] + \
           (["python.exe", "pythonw.exe"] if WIN else [])
    out = [shutil.which(n) for n in noms]

    motifs = []
    if WIN:
        la = os.environ.get("LOCALAPPDATA", "")
        up = os.environ.get("USERPROFILE", "")
        motifs += [r"C:\Python3*\python.exe",
                   r"C:\Program Files\Python3*\python.exe",
                   r"C:\Program Files (x86)\Python3*\python.exe",
                   os.path.join(la, r"Programs\Python\Python3*\python.exe"),
                   os.path.join(up, r"anaconda3\python.exe"),
                   os.path.join(up, r"miniconda3\python.exe"),
                   r"C:\ProgramData\Anaconda3\python.exe"]
        # مشغّل ويندوز py.exe يعرف كل النسخ المسجَّلة
        try:
            r = subprocess.run(["py", "-0p"], capture_output=True, text=True, timeout=10)
            for l in (r.stdout or "").splitlines():
                p = l.strip().split("*")[-1].strip().strip('"')
                if p.lower().endswith(".exe") and os.path.isfile(p):
                    out.append(p)
        except Exception:
            pass
    else:
        motifs += ["/usr/bin/python3.*", "/usr/local/bin/python3.*",
                   os.path.expanduser("~/.pyenv/versions/*/bin/python"),
                   "/opt/homebrew/bin/python3.*",
                   os.path.join(os.environ.get("PREFIX", "/data/data/com.termux/files/usr"),
                                "bin", "python3*")]

    # بيئات افتراضية في المشروع الحالي
    for env in ("venv", ".venv", "env", ".env"):
        motifs.append(os.path.join(env, "Scripts" if WIN else "bin",
                                   "python.exe" if WIN else "python"))

    for m in motifs:
        out += glob.glob(m)
    return [p for p in out if p]


def info(chemin: str, forcer: bool = False) -> dict:
    """يستجوب مفسّرًا ويُرجع معلوماته (مع ذاكرة مؤقّتة)."""
    cle = os.path.realpath(chemin)
    if not forcer and cle in _CACHE:
        return _CACHE[cle]
    d = {"chemin": chemin, "ok": False, "version": "?", "etiquette": chemin}
    try:
        r = subprocess.run([chemin, "-c", _SONDE], capture_output=True,
                           text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip().startswith("{"):
            d.update(json.loads(r.stdout.strip().splitlines()[-1]), ok=True,
                     chemin=chemin)
            d["etiquette"] = (f"{d['impl']} {d['version']} ({d['bits']}-bit"
                              + (", venv" if d["venv"] else "") + ")")
    except Exception as e:
        d["erreur"] = f"{type(e).__name__}: {e}"
    _CACHE[cle] = d
    return d


def scanner(forcer: bool = False) -> list:
    """قائمة المفسّرات الصالحة، بلا تكرار، مرتّبة من الأحدث إلى الأقدم."""
    vus, out = set(), []
    for c in candidats():
        reel = os.path.realpath(c)
        if reel in vus or not os.path.isfile(reel):
            continue
        vus.add(reel)
        d = info(c, forcer)
        if d["ok"]:
            out.append(d)
    # المفسّر الجاري دائمًا موجود
    if not any(os.path.realpath(d["chemin"]) == os.path.realpath(sys.executable)
               for d in out):
        d = info(sys.executable, forcer)
        d["ok"] and out.append(d)
    out.sort(key=lambda d: (d.get("majeur", 0), d.get("mineur", 0)), reverse=True)
    return out


def valider(chemin: str) -> dict:
    """يتحقّق أنّ المسار المختار مفسّر بايثون صالح."""
    if not chemin or not os.path.isfile(chemin):
        return {"ok": False, "erreur": "fichier introuvable", "chemin": chemin}
    return info(chemin, forcer=True)


# ---------------------------------------------------------------------------
def essayer(chemin: str, source: str, stdin: str = "", timeout: int = 8) -> dict:
    """يترجم ثم ينفّذ نفس الكود على مفسّر معيّن."""
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
    f.write(source)
    f.close()
    env = dict(os.environ, PYTHONPYCACHEPREFIX=tempfile.gettempdir(),
               PYTHONIOENCODING="utf-8")
    res = {"chemin": chemin, "etiquette": info(chemin).get("etiquette", chemin)}
    try:
        c = subprocess.run([chemin, "-m", "py_compile", f.name],
                           capture_output=True, text=True, timeout=timeout, env=env)
        res["compile"] = c.returncode == 0
        res["erreur_compile"] = "" if res["compile"] else \
            (c.stderr or "").strip().splitlines()[-1][:180]

        if res["compile"]:
            import time
            t0 = time.time()
            x = subprocess.run([chemin, "-u", f.name], input=stdin, capture_output=True,
                               text=True, timeout=timeout, env=env)
            res["execute"] = x.returncode == 0
            res["ms"] = int((time.time() - t0) * 1000)
            res["sortie"] = (x.stdout or "").strip()[:400]
            res["erreur"] = (x.stderr or "").strip().splitlines()[-1][:180] \
                if x.returncode else ""
        else:
            res.update(execute=False, ms=0, sortie="", erreur=res["erreur_compile"])
    except subprocess.TimeoutExpired:
        res.update(compile=res.get("compile", False), execute=False, ms=timeout * 1000,
                   sortie="", erreur=f"timeout {timeout}s")
    except Exception as e:
        res.update(compile=False, execute=False, ms=0, sortie="",
                   erreur=f"{type(e).__name__}: {e}")
    finally:
        try:
            os.unlink(f.name)
        except OSError:
            pass
    return res


def matrice_compatibilite(source: str, chemins=None, stdin: str = "") -> list:
    """يشغّل الكود على كل المفسّرات ويُرجع جدول التوافق."""
    chemins = chemins or [d["chemin"] for d in scanner()]
    return [essayer(c, source, stdin) for c in chemins]


if __name__ == "__main__":
    for d in scanner():
        print(f"{'✅' if d['ok'] else '❌'} {d['etiquette']:<38} {d['chemin']}"
              f"{'  [pip]' if d.get('pip') else ''}{'  [PyQt5]' if d.get('pyqt5') else ''}")
