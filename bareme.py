#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bareme.py — سلّم التنقيط: قابل للتعديل، متعدّد الملفّات، بلا لمس الكود
=====================================================================
قبلُ كان السلّم ثابتًا داخل analyseur.py. الآن هو ملفّ JSON يمكن للأستاذ
تعديله أو الاحتفاظ بعدّة نسخ منه (TP عادي، امتحان صارم، مبتدئون…).

    import bareme
    bareme.charger("baremes/examen.json")     # أو bareme.charger_profil("examen")
    bareme.axes()        -> {"qualite": 6, "tests": 10, "structure": 4}
    bareme.regles()      -> {"E102": (3.0, 6.0), ...}   (النشِطة فقط)
    bareme.seuils()      -> [18, 16, 14, 12, 10]
    bareme.sauver("baremes/mon_bareme.json")
    bareme.profils()     -> ["Standard", "examen", "debutant", ...]

الصيغة v2 (تُكشف وتُوحَّد تلقائيًّا)
    يمكن للملفّ أن يكون بصيغة v2 — note/tolerance في كائنات، axes_bd بمفتاح
    « points », seuils قاموسًا بأسماء التقديرات، وregles مع description/cumulable.
    يُوحَّد كلّ ذلك إلى الصيغة الداخلية دون لمس الكود؛ تُحفَظ الأقسام الإضافية
    (ponderation, comparaison, calcul, donnees, rapport) للاستعمال من المصحّحات.
    مثال: baremes/access_v2.json

كل ما يغيّره الأستاذ:
    note_max      : 20 افتراضيًّا (يمكن 10 أو 100)
    axes          : وزن كل محور في التصحيح مقابل الحلّ (المجموع = note_max)
    axes_bd       : أوزان تصحيح قواعد البيانات
    regles        : لكل قاعدة {actif, penalite, plafond}
                    actif=false → تُكشف وتُشرح لكنّها لا تُنقِص النقطة
    seuils        : حدود التقديرات (النصوص تأتي مترجَمة من langues.py)
    tolerance     : عدد التحذيرات المسموح بها قبل بدء الخصم (0 = بلا تسامح)
    erreur_fatale : إن كان صحيحًا، خطأ صياغة واحد يُنزل النقطة إلى 0
"""

import json
import os
import sys

if sys.platform == "win32":
    for _flux in (sys.stdout, sys.stderr):
        try:
            if _flux is not None and getattr(_flux, "reconfigure", None) \
                    and (_flux.encoding or "").lower() not in ("utf-8", "utf8"):
                _flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baremes")

# ---------------------------------------------------------------------------
DEFAUT = {
    "nom": "Standard",
    "description": "Barème par défaut — TP noté ordinaire",
    "note_max": 20.0,
    "arrondi": 2,
    "tolerance": 0,
    "erreur_fatale": False,
    "axes": {"qualite": 6.0, "tests": 10.0, "structure": 4.0},
    "axes_bd": {"tables": 4.0, "champs": 4.0, "donnees": 2.0, "cles": 2.0,
                "relations": 4.0, "requetes": 4.0},
    "seuils": [18, 16, 14, 12, 10],
    "regles": {
        "E001": {"actif": True, "penalite": 8.0, "plafond": 8.0},
        "E002": {"actif": True, "penalite": 8.0, "plafond": 8.0},
        "E102": {"actif": True, "penalite": 3.0, "plafond": 6.0},
        "E104": {"actif": True, "penalite": 3.0, "plafond": 6.0},
        "E108": {"actif": True, "penalite": 2.0, "plafond": 4.0},
        "W101": {"actif": True, "penalite": 1.5, "plafond": 4.5},
        "W110": {"actif": True, "penalite": 1.5, "plafond": 4.5},
        "W103": {"actif": True, "penalite": 1.0, "plafond": 3.0},
        "W105": {"actif": True, "penalite": 1.0, "plafond": 3.0},
        "W106": {"actif": True, "penalite": 1.0, "plafond": 3.0},
        "W111": {"actif": True, "penalite": 1.0, "plafond": 3.0},
        "W107": {"actif": True, "penalite": 0.5, "plafond": 2.0},
        "W109": {"actif": True, "penalite": 0.25, "plafond": 2.0},
    },
}

_courant = json.loads(json.dumps(DEFAUT))     # نسخة عميقة
_chemin = None


# ---------------------------------------------------------------------------
# 1) كشف الصيغة v2 وتوحيدها إلى الصيغة الداخلية v1
# ---------------------------------------------------------------------------
def _est_v2(d: dict) -> bool:
    """يكشف ما إذا كان القاموس بصيغة v2 (تحوّل note/tolerance/axes_bd/…)."""
    return isinstance(d.get("note"), dict) or "ponderation" in d \
        or "comparaison" in d or "calcul" in d


def _normaliser_v2(d: dict) -> dict:
    """يحوّل صيغة v2 إلى الصيغة الداخلية v1 (متوافق مع الكود القديم)."""
    out = dict(d)

    # note: {"min", "max", "arrondi", "mode"} → note_max, arrondi
    n = out.pop("note", {})
    if isinstance(n, dict):
        out["note_max"] = float(n.get("max", 20.0))
        out["arrondi"] = int(n.get("arrondi", 2))
    if "version" in out:
        del out["version"]

    # tolerance: {"active", "valeur"} → tolerance (entier)
    t = out.get("tolerance")
    if isinstance(t, dict):
        out["tolerance"] = int(t.get("valeur", 0)) if t.get("active") else 0

    # axes_bd: {"tables": {"points": 4, "obligatoire": true, ...}} → {"tables": 4.0}
    # Les axes v2 « types_champs » et « cles_primaires » sont fusionnés dans les
    # axes internes « champs » et « cles » (le moteur de comparaison ne les
    # sépare pas) — la somme des points reste égale à note_max.
    abd = out.get("axes_bd")
    if isinstance(abd, dict):
        nv = {}
        fusion_v2 = {"types_champs": "champs", "cles_primaires": "cles"}
        for k, v in abd.items():
            points = float(v["points"]) if isinstance(v, dict) and "points" in v \
                else float(v)
            cible = fusion_v2.get(k, k)
            nv[cible] = nv.get(cible, 0.0) + points
        out["axes_bd"] = nv
        out["_axes_bd_v2"] = abd    # section v2 brute (obligatoire, methode…)

        # donnees: {"active", "points", "comparer"} → axe interne « donnees »
        # Le nombre de points est prélevé sur l'axe « champs » pour que la
        # somme des axes reste égale à note_max (les données ne font pas partie
        # de l'en-tête mais de la saisie, qui dépend des champs).
        d = out.get("donnees")
        if isinstance(d, dict) and d.get("active") \
                and (d.get("points") or 0) > 0 and "donnees" not in nv:
            pts = float(d.get("points", 0.0))
            pris = min(pts, nv.get("champs", 0.0))
            nv["champs"] = nv.get("champs", 0.0) - pris
            nv["donnees"] = pris

    # seuils: {"excellent": {"minimum": 18}, ...} → [18, 16, 14, 12, 10]
    s = out.get("seuils")
    if isinstance(s, dict):
        seuils_tries = sorted(
            [(v.get("minimum", 0), v.get("mention", k))
             for k, v in s.items()],
            key=lambda x: -x[0])
        out["seuils"] = [x[0] for x in seuils_tries]
        # Conserver les mentions v2 pour rapport éventuel
        out["_seuils_mentions"] = {k: v for k, v in s.items()}

    # axes: barème BD uniquement → axes Python mis à 0
    if "axes" not in out:
        out["axes"] = {"qualite": 0.0, "tests": 0.0, "structure": 0.0}

    # Conserver les sections v2 supplémentaires (comparaison, calcul, rapport,
    # donnees, ponderation) telles quelles pour usage par correcteur_access
    return out


def _fusionner(d: dict, base: dict = None) -> dict:
    """يدمج d فوق base (افتراضي DEFAUT) بمجamعتها العميقة."""
    base = json.loads(json.dumps(base or DEFAUT))
    for k, v in (d or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)
        else:
            base[k] = v
    return base


# ---------------------------------------------------------------------------
def actif() -> dict:
    return _courant


def nom() -> str:
    return _courant.get("nom", "?")


def chemin() -> str:
    return _chemin or "(défaut interne)"


def definir(d: dict) -> dict:
    """يدمج قاموسًا فوق السلّم الحالي (يُستعمل من محرّر الواجهة).
    يكشف تلقائيًّا الصيغة v2 ويوحّدها."""
    global _courant
    internes = {k: v for k, v in (d or {}).items() if k.startswith("_")}
    if _est_v2(d):
        d = _normaliser_v2(d)
        internes.update({k: v for k, v in d.items() if k.startswith("_")})
    _courant = _fusionner(d)
    for k, v in internes.items():
        _courant[k] = v
    return _courant


def charger(fichier: str) -> dict:
    global _chemin
    with open(fichier, encoding="utf-8") as f:
        d = json.load(f)
    _chemin = fichier
    return definir(d)


def charger_profil(nom_profil: str) -> dict:
    for c in (os.path.join(DOSSIER, f"{nom_profil}.json"), nom_profil,
              f"{nom_profil}.json"):
        if os.path.isfile(c):
            return charger(c)
    raise FileNotFoundError(f"barème introuvable : {nom_profil}")


def sauver(fichier: str = None) -> str:
    global _chemin
    fichier = fichier or _chemin or os.path.join(DOSSIER, "mon_bareme.json")
    os.makedirs(os.path.dirname(os.path.abspath(fichier)), exist_ok=True)
    # On n'enregistre pas les clés internes (« _... » : seuils v2, axes v2 bruts)
    visible = {k: v for k, v in _courant.items() if not k.startswith("_")}
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(visible, f, ensure_ascii=False, indent=2)
    _chemin = fichier
    return fichier


def profils() -> list:
    """[(nom_affiché, chemin), ...] لكل ملفّات baremes/*.json"""
    out = [("Standard (interne)", "")]
    if os.path.isdir(DOSSIER):
        for f in sorted(os.listdir(DOSSIER)):
            if f.endswith(".json"):
                c = os.path.join(DOSSIER, f)
                try:
                    with open(c, encoding="utf-8") as fh:
                        out.append((json.load(fh).get("nom", f[:-5]), c))
                except Exception:
                    out.append((f[:-5], c))
    return out


def reinitialiser() -> dict:
    global _chemin
    _chemin = None
    return definir({})


# ---------------------------------------------------------------------------
# واجهات القراءة التي تستعملها بقيّة الوحدات
# ---------------------------------------------------------------------------
def regles() -> dict:
    """{code: (penalite, plafond)} — القواعد المعطَّلة تُستبعَد."""
    return {c: (float(d.get("penalite", 0)), float(d.get("plafond", 0)))
            for c, d in _courant["regles"].items() if d.get("actif", True)}


def regle_active(code: str) -> bool:
    return _courant["regles"].get(code, {}).get("actif", True)


def axes() -> dict:
    return dict(_courant["axes"])


def axes_bd() -> dict:
    return dict(_courant["axes_bd"])


def axes_bd_v2() -> dict:
    """Section « axes_bd » brute (v2) : {axe: {points, obligatoire, methode}}.
    Vide si le barème courant n'est pas en v2."""
    return dict(_courant.get("_axes_bd_v2", {}))


def note_max() -> float:
    return float(_courant.get("note_max", 20))


def arrondi() -> int:
    return int(_courant.get("arrondi", 2))


def tolerance() -> int:
    return int(_courant.get("tolerance", 0))


def erreur_fatale() -> bool:
    return bool(_courant.get("erreur_fatale", False))


def seuils() -> list:
    return list(_courant.get("seuils", DEFAUT["seuils"]))


def seuils_mentions() -> list:
    """Liste [(minimum, mention)] à partir de la section v2 « seuils » ou des
    mentions traduites de langues.py (repli)."""
    m = _courant.get("_seuils_mentions")
    if m:
        return sorted([(float(v["minimum"]), v["mention"])
                       for k, v in m.items()], key=lambda x: -x[0])
    return langues_mentions_traduites()


def langues_mentions_traduites() -> list:
    try:
        import langues
        return list(langues.mentions())
    except Exception:
        return _courant.get("_seuils_mentions_fr", [])


def ponderation() -> dict:
    """Section v2 « ponderation » ({} si absente)."""
    return _courant.get("ponderation", {})


def comparaison() -> dict:
    return _courant.get("comparaison", {})


def calcul() -> dict:
    return _courant.get("calcul", {})


def donnees() -> dict:
    return _courant.get("donnees", {})


def rapport_config() -> dict:
    return _courant.get("rapport", {})


# ---------------------------------------------------------------------------
# ملفّات تعريف جاهزة تُنشأ عند أوّل استعمال
# ---------------------------------------------------------------------------
PRETS = {
    "debutant": {
        "nom": "Débutant (indulgent)",
        "description": "Début d'année : le style n'est pas encore sanctionné.",
        "tolerance": 3,
        "axes": {"qualite": 3.0, "tests": 13.0, "structure": 4.0},
        "seuils": [16, 14, 12, 10, 8],
        "regles": {c: {"actif": not c.startswith("W"),
                       "penalite": v["penalite"] / 2, "plafond": v["plafond"] / 2}
                   for c, v in DEFAUT["regles"].items()},
    },
    "examen": {
        "nom": "Examen (strict)",
        "description": "Épreuve notée : tout compte, une erreur de syntaxe est fatale.",
        "tolerance": 0,
        "erreur_fatale": True,
        "axes": {"qualite": 7.0, "tests": 9.0, "structure": 4.0},
        "seuils": [18, 16, 14, 12, 10],
        "regles": {c: {"actif": True, "penalite": v["penalite"] * 1.5,
                       "plafond": v["plafond"] * 1.5}
                   for c, v in DEFAUT["regles"].items()},
    },
    "algorithmique": {
        "nom": "Algorithmique (résultats d'abord)",
        "description": "Seule la justesse des résultats compte vraiment.",
        "axes": {"qualite": 2.0, "tests": 16.0, "structure": 2.0},
        "regles": {c: {"actif": c.startswith("E"), "penalite": v["penalite"],
                       "plafond": v["plafond"]} for c, v in DEFAUT["regles"].items()},
    },
}


def creer_profils_prets(dossier: str = None) -> list:
    """يكتب ملفّات التعريف الجاهزة إن لم تكن موجودة."""
    dossier = dossier or DOSSIER
    os.makedirs(dossier, exist_ok=True)
    faits = []
    for cle, d in PRETS.items():
        c = os.path.join(dossier, f"{cle}.json")
        if not os.path.isfile(c):
            fusion = json.loads(json.dumps(DEFAUT))
            for k, v in d.items():
                if isinstance(v, dict) and isinstance(fusion.get(k), dict):
                    fusion[k].update(v)
                else:
                    fusion[k] = v
            with open(c, "w", encoding="utf-8") as f:
                json.dump(fusion, f, ensure_ascii=False, indent=2)
            faits.append(c)
    std = os.path.join(dossier, "standard.json")
    if not os.path.isfile(std):
        with open(std, "w", encoding="utf-8") as f:
            json.dump(DEFAUT, f, ensure_ascii=False, indent=2)
        faits.append(std)
    return faits


if __name__ == "__main__":
    print("📁", DOSSIER)
    for c in creer_profils_prets():
        print("  + créé :", os.path.basename(c))
    print("\nProfils disponibles :")
    for n, c in profils():
        print(f"  • {n:<34} {c}")
    print(f"\nBarème courant : {nom()}  ·  axes {axes()}  ·  "
          f"{len(regles())} règles actives")
