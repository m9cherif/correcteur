#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
langues.py — لغة الشرح (i18n)
==============================
كل نصوص الأخطاء والشروح والتصحيحات وواجهة التقارير في مكان واحد.

الاستعمال من الكود:
    import langues
    langues.definir_langue("fr")
    m, e, c = langues.R("W103", sym="==", remp="is")   # نصّ القاعدة
    print(langues.U("note_finale"))                    # نصّ الواجهة

اختيار اللغة (بالأولوية):
    1. الخيار  --lang ar|fr|en  في سطر الأوامر
    2. متغيّر البيئة  ANALYSEUR_LANG=fr
    3. الافتراضي: ar

إضافة لغة جديدة: أضف مفتاحها في LANGUES ثم أضف "xx" داخل كل قاعدة
وكل مفتاح واجهة. أيّ نصّ ناقص يعود تلقائيًّا إلى العربية.
"""

import os
import sys

if sys.platform == "win32":
    # La console Windows (code page cp1252) ne peut pas encoder les emojis des
    # messages ; on force UTF-8 pour éviter le plantage UnicodeEncodeError.
    for _flux in (sys.stdout, sys.stderr):
        try:
            if _flux is not None and getattr(_flux, "reconfigure", None) \
                    and (_flux.encoding or "").lower() not in ("utf-8", "utf8"):
                _flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

LANGUES = {"ar": "العربية", "fr": "Français", "en": "English"}
SECOURS = "ar"                      # اللغة الاحتياطية عند نقص ترجمة
_courante = os.environ.get("ANALYSEUR_LANG", SECOURS)


def definir_langue(code: str) -> str:
    global _courante
    if code in LANGUES:
        _courante = code
    return _courante


def langue() -> str:
    return _courante


# ---------------------------------------------------------------------------
# نصوص القواعد:  t = عنوان مختصر (للسلّم) | m = الرسالة | e = السبب | c = التصحيح
# ---------------------------------------------------------------------------
REGLES = {
    "E001": {
        "ar": {"t": "خطأ صياغة — الملف لا يعمل إطلاقًا",
               "m": "خطأ صياغة: {msg}",
               "e": "المترجم لم يستطع تحليل هذا السطر، لذا لا يعمل الملف كلّه.",
               "c": "راجع الصياغة في هذا الموضع."},
        "fr": {"t": "Erreur de syntaxe — le fichier ne s'exécute pas",
               "m": "Erreur de syntaxe : {msg}",
               "e": "L'interpréteur ne peut pas analyser cette ligne, donc tout le "
                    "fichier est inutilisable.",
               "c": "Vérifiez la syntaxe à cet endroit."},
        "en": {"t": "Syntax error — file does not run at all",
               "m": "Syntax error: {msg}",
               "e": "The parser cannot read this line, so the whole file fails.",
               "c": "Check the syntax at this position."}},
    "E001.colon": {
        "ar": {"e": "الجمل المركّبة (if/for/def…) يجب أن تنتهي بنقطتين ':'.",
               "c": "أضف ':' في نهاية السطر."},
        "fr": {"e": "Les instructions composées (if/for/def…) doivent finir par ':'.",
               "c": "Ajoutez ':' à la fin de la ligne."},
        "en": {"e": "Compound statements (if/for/def…) must end with a colon ':'.",
               "c": "Add ':' at the end of the line."}},
    "E001.print": {
        "ar": {"e": "في بايثون 3 صار print دالّة وليست تعليمة كما في بايثون 2.",
               "c": "ضع الوسائط بين قوسين: print(...)"},
        "fr": {"e": "En Python 3, print est une fonction, plus une instruction.",
               "c": "Mettez les arguments entre parenthèses : print(...)"},
        "en": {"e": "In Python 3 print is a function, not a statement.",
               "c": "Wrap the arguments in parentheses: print(...)"}},
    "E001.eq": {
        "ar": {"e": "استُعمل معامل إسناد '=' في مكان يتطلّب مقارنة '==' أو العكس.",
               "c": "استعمل '==' للمقارنة و'=' للإسناد."},
        "fr": {"e": "Un '=' d'affectation est utilisé là où '==' est attendu (ou l'inverse).",
               "c": "Utilisez '==' pour comparer et '=' pour affecter."},
        "en": {"e": "Assignment '=' used where comparison '==' is required (or vice versa).",
               "c": "Use '==' to compare and '=' to assign."}},

    "E002": {
        "ar": {"t": "رفضه المفسّر الحقيقي (py_compile)",
               "m": "خطأ ترجمة من المفسّر {py}: {msg}",
               "e": "المفسّر المستهدف نفسه رفض الملف؛ قد يكون بناءً غير مدعوم في هذه "
                    "النسخة من بايثون (match، walrus، f-string متداخلة…).",
               "c": "صحّح البناء أو استعمل نسخة بايثون أحدث."},
        "fr": {"t": "Refusé par l'interpréteur réel (py_compile)",
               "m": "Erreur de compilation ({py}) : {msg}",
               "e": "L'interpréteur cible refuse le fichier ; syntaxe peut-être non "
                    "supportée par cette version de Python (match, walrus…).",
               "c": "Corrigez la syntaxe ou utilisez une version de Python plus récente."},
        "en": {"t": "Rejected by the real interpreter (py_compile)",
               "m": "Compile error ({py}): {msg}",
               "e": "The target interpreter itself rejects the file; the syntax may be "
                    "unsupported in this Python version (match, walrus…).",
               "c": "Fix the syntax or use a newer Python version."}},
    "W111": {
        "ar": {"t": "تحذير صياغة من المفسّر (SyntaxWarning)",
               "m": "تحذير من المفسّر: {msg}",
               "e": "المفسّر نفسه ينبّه إلى بناء صحيح شكلًا لكنّه شبه مؤكّد أنّه خطأ "
                    "(مثل 'is' مع قيمة حرفية، أو تسلسل هروب مجهول).",
               "c": "اتّبع اقتراح المفسّر المذكور في الرسالة."},
        "fr": {"t": "Avertissement de syntaxe de l'interpréteur",
               "m": "Avertissement de l'interpréteur : {msg}",
               "e": "Python signale une construction valide mais presque sûrement "
                    "fautive ('is' avec un littéral, séquence d'échappement inconnue…).",
               "c": "Suivez la suggestion donnée dans le message."},
        "en": {"t": "Interpreter syntax warning",
               "m": "Interpreter warning: {msg}",
               "e": "Python flags syntax that is legal but almost certainly a mistake "
                    "('is' with a literal, unknown escape sequence…).",
               "c": "Follow the suggestion in the message."}},
    "E102": {
        "ar": {"t": "وسيط افتراضي قابل للتغيير (liste=[])",
               "m": "وسيط افتراضي قابل للتغيير في الدالة '{nom}'",
               "e": "القيمة الافتراضية تُنشأ مرّة واحدة فقط، فتتراكم البيانات بين "
                    "الاستدعاءات وتُنتج نتائج غير متوقّعة.",
               "c": "استعمل None كقيمة افتراضية: def f(x=None): x = [] if x is None else x"},
        "fr": {"t": "Argument par défaut mutable (liste=[])",
               "m": "Argument par défaut mutable dans la fonction '{nom}'",
               "e": "La valeur par défaut est créée une seule fois : les données "
                    "s'accumulent entre les appels et produisent des résultats imprévus.",
               "c": "Utilisez None : def f(x=None): x = [] if x is None else x"},
        "en": {"t": "Mutable default argument (list=[])",
               "m": "Mutable default argument in function '{nom}'",
               "e": "The default is created once, so data accumulates across calls "
                    "and gives surprising results.",
               "c": "Use None instead: def f(x=None): x = [] if x is None else x"}},

    "E104": {
        "ar": {"t": "قسمة على صفر", "m": "قسمة على صفر",
               "e": "تُطلق ZeroDivisionError أثناء التنفيذ وتوقف البرنامج.",
               "c": "تحقّق من المقام قبل القسمة: if d != 0: ..."},
        "fr": {"t": "Division par zéro", "m": "Division par zéro",
               "e": "Déclenche ZeroDivisionError à l'exécution et arrête le programme.",
               "c": "Vérifiez le dénominateur : if d != 0: ..."},
        "en": {"t": "Division by zero", "m": "Division by zero",
               "e": "Raises ZeroDivisionError at runtime and stops the program.",
               "c": "Check the denominator first: if d != 0: ..."}},

    "E108": {
        "ar": {"t": "خلط Tab ومسافات في الإزاحة",
               "m": "خلط بين المسافات و Tab في الإزاحة",
               "e": "بايثون 3 يمنع الخلط ويُطلق TabError.",
               "c": "استعمل 4 مسافات فقط في كامل الملف."},
        "fr": {"t": "Mélange tabulations / espaces",
               "m": "Mélange d'espaces et de tabulations dans l'indentation",
               "e": "Python 3 l'interdit et lève TabError.",
               "c": "N'utilisez que 4 espaces dans tout le fichier."},
        "en": {"t": "Mixed tabs and spaces",
               "m": "Mixed spaces and tabs in indentation",
               "e": "Python 3 forbids mixing and raises TabError.",
               "c": "Use 4 spaces everywhere in the file."}},

    "W101": {
        "ar": {"t": "except: بدون تحديد نوع الاستثناء",
               "m": "استعمال 'except:' بدون تحديد نوع الاستثناء",
               "e": "يلتقط حتى KeyboardInterrupt و SystemExit ويُخفي الأخطاء الحقيقية.",
               "c": "حدّد النوع، مثلاً: except Exception as e:"},
        "fr": {"t": "except: sans type d'exception",
               "m": "Utilisation de 'except:' sans préciser l'exception",
               "e": "Capture même KeyboardInterrupt et SystemExit et masque les vraies erreurs.",
               "c": "Précisez le type : except Exception as e:"},
        "en": {"t": "Bare except: without exception type",
               "m": "Bare 'except:' without an exception type",
               "e": "It swallows even KeyboardInterrupt and SystemExit and hides real bugs.",
               "c": "Name the type: except Exception as e:"}},

    "W103": {
        "ar": {"t": "مقارنة None بـ == بدل is",
               "m": "مقارنة None بـ '{sym}'",
               "e": "None كائن وحيد، والمقارنة بالهوية أدقّ وأسرع ولا تتأثّر بإعادة "
                    "تعريف __eq__.",
               "c": "استعمل '{remp} None' بدل '{sym} None'."},
        "fr": {"t": "Comparaison à None avec == au lieu de is",
               "m": "Comparaison à None avec '{sym}'",
               "e": "None est un singleton : la comparaison d'identité est plus sûre "
                    "et n'est pas altérée par __eq__.",
               "c": "Utilisez '{remp} None' au lieu de '{sym} None'."},
        "en": {"t": "Comparing to None with == instead of is",
               "m": "Comparison to None using '{sym}'",
               "e": "None is a singleton; identity comparison is safer and unaffected "
                    "by a custom __eq__.",
               "c": "Use '{remp} None' instead of '{sym} None'."}},

    "W105": {
        "ar": {"t": "إسناد بلا أثر (x = x)", "m": "إسناد بلا أثر: {nom} = {nom}",
               "e": "السطر لا يغيّر شيئًا؛ غالبًا خطأ مطبعي.",
               "c": "احذف السطر أو صحّح اسم المتغيّر."},
        "fr": {"t": "Affectation sans effet (x = x)", "m": "Affectation sans effet : {nom} = {nom}",
               "e": "La ligne ne change rien ; c'est souvent une faute de frappe.",
               "c": "Supprimez la ligne ou corrigez le nom de la variable."},
        "en": {"t": "Self-assignment with no effect (x = x)", "m": "No-op assignment: {nom} = {nom}",
               "e": "The line changes nothing; usually a typo.",
               "c": "Delete the line or fix the variable name."}},

    "W106": {
        "ar": {"t": "open() بدون with", "m": "استعمال open() بدون 'with'",
               "e": "إذا وقع استثناء قبل close() يبقى الملف مفتوحًا وتُهدر الموارد.",
               "c": "استعمل: with open(...) as f:"},
        "fr": {"t": "open() sans with", "m": "Utilisation de open() sans 'with'",
               "e": "Si une exception survient avant close(), le fichier reste ouvert.",
               "c": "Utilisez : with open(...) as f:"},
        "en": {"t": "open() without with", "m": "Using open() without 'with'",
               "e": "If an exception occurs before close(), the file stays open.",
               "c": "Use: with open(...) as f:"}},

    "W107": {
        "ar": {"t": "استيراد غير مستعمل", "m": "استيراد غير مستعمل: '{nom}'",
               "e": "يُثقل الملف ويُبطئ الإقلاع دون فائدة.",
               "c": "احذف استيراد '{nom}' أو استعمله."},
        "fr": {"t": "Import inutilisé", "m": "Import inutilisé : '{nom}'",
               "e": "Alourdit le fichier et ralentit le démarrage sans aucun bénéfice.",
               "c": "Supprimez l'import '{nom}' ou utilisez-le."},
        "en": {"t": "Unused import", "m": "Unused import: '{nom}'",
               "e": "Adds weight and slows start-up for nothing.",
               "c": "Remove the '{nom}' import or use it."}},

    "W109": {
        "ar": {"t": "سطر أطول من 99 حرفًا", "m": "سطر طويل ({n} حرفًا)",
               "e": "يصعّب القراءة والمراجعة (PEP 8 يوصي بـ 79–99).",
               "c": "قسّم السطر أو استخرج متغيّرًا وسيطًا."},
        "fr": {"t": "Ligne de plus de 99 caractères", "m": "Ligne trop longue ({n} caractères)",
               "e": "Nuit à la lisibilité et à la relecture (PEP 8 : 79–99).",
               "c": "Coupez la ligne ou extrayez une variable intermédiaire."},
        "en": {"t": "Line longer than 99 characters", "m": "Long line ({n} characters)",
               "e": "Hurts readability and review (PEP 8 suggests 79–99).",
               "c": "Split the line or extract an intermediate variable."}},

    "W110": {
        "ar": {"t": "استثناء مُبتلَع بصمت (except…: pass)",
               "m": "استثناء مُبتلَع بصمت (except … : pass)",
               "e": "الأخطاء تختفي دون أثر فيصعب التشخيص لاحقًا.",
               "c": "سجّل الخطأ على الأقل: logging.exception(e)"},
        "fr": {"t": "Exception avalée en silence (except…: pass)",
               "m": "Exception ignorée silencieusement (except … : pass)",
               "e": "Les erreurs disparaissent sans trace, le diagnostic devient impossible.",
               "c": "Journalisez au minimum : logging.exception(e)"},
        "en": {"t": "Silently swallowed exception (except…: pass)",
               "m": "Exception silently ignored (except … : pass)",
               "e": "Errors vanish without a trace, making diagnosis impossible.",
               "c": "At least log it: logging.exception(e)"}},
}

# ---------------------------------------------------------------------------
# نصوص الواجهة والتقارير
# ---------------------------------------------------------------------------
UI = {
    "m_fichier":     {"ar": "ملف", "fr": "Fichier", "en": "File"},
    "m_edition":     {"ar": "تحرير", "fr": "Édition", "en": "Edit"},
    "m_execution":   {"ar": "تشغيل", "fr": "Exécution", "en": "Run"},
    "m_analyse":     {"ar": "تحليل", "fr": "Analyse", "en": "Analysis"},
    "m_correction":  {"ar": "تصحيح", "fr": "Correction", "en": "Grading"},
    "m_classe":      {"ar": "القسم", "fr": "Classe", "en": "Class"},
    "m_interp":      {"ar": "المفسّر", "fr": "Interpréteur", "en": "Interpreter"},
    "m_affichage":   {"ar": "عرض", "fr": "Affichage", "en": "View"},
    "m_aide":        {"ar": "مساعدة", "fr": "Aide", "en": "Help"},
    "app_ide":       {"ar": "بايثون للمبتدئين", "fr": "Python Débutant",
                      "en": "Python for Beginners"},
    "app_corr":      {"ar": "مصحّح المحاولات", "fr": "Correcteur de copies",
                      "en": "Submission grader"},
    "bt_nouveau":    {"ar": "جديد", "fr": "Nouveau", "en": "New"},
    "bt_enr_sous":   {"ar": "حفظ باسم", "fr": "Enregistrer sous", "en": "Save as"},
    "bt_fermer":     {"ar": "إغلاق", "fr": "Fermer", "en": "Close"},
    "bt_annuler":    {"ar": "تراجع", "fr": "Annuler", "en": "Undo"},
    "bt_retablir":   {"ar": "إعادة", "fr": "Rétablir", "en": "Redo"},
    "bt_commenter":  {"ar": "تعليق", "fr": "Commenter", "en": "Comment"},
    "bt_arreter":    {"ar": "إيقاف", "fr": "Arrêter", "en": "Stop"},
    "bt_console":    {"ar": "طرفية تفاعلية", "fr": "Console interactive",
                      "en": "Interactive shell"},
    "bt_effacer":    {"ar": "مسح", "fr": "Effacer", "en": "Clear"},
    "bt_variables":  {"ar": "المتغيّرات", "fr": "Variables", "en": "Variables"},
    "bt_raccourcis": {"ar": "الاختصارات", "fr": "Raccourcis", "en": "Shortcuts"},
    "bt_apropos":    {"ar": "حول", "fr": "À propos", "en": "About"},
    "bt_theme":      {"ar": "المظهر", "fr": "Thème", "en": "Theme"},
    "bt_choisir_sol": {"ar": "اختيار الحلّ", "fr": "Choisir la solution",
                       "en": "Pick solution"},
    "bt_choisir_tst": {"ar": "اختيار الاختبارات", "fr": "Choisir les tests",
                       "en": "Pick tests"},
    "bt_choisir_enn": {"ar": "اختيار النصّ", "fr": "Choisir l'énoncé",
                       "en": "Pick task text"},
    "bt_dossier":    {"ar": "مجلّد القسم", "fr": "Dossier de la classe",
                      "en": "Class folder"},
    "bt_lot":        {"ar": "تصحيح القسم", "fr": "Corriger la classe",
                      "en": "Grade the class"},
    "tab_console":   {"ar": "الطرفية", "fr": "Console", "en": "Console"},
    "tab_vars":      {"ar": "المتغيّرات", "fr": "Variables", "en": "Variables"},
    "tab_assist":    {"ar": "المساعد", "fr": "Assistant", "en": "Assistant"},
    "tab_classe":    {"ar": "القسم", "fr": "Classe", "en": "Class"},
    "c_nom":         {"ar": "الاسم", "fr": "Nom", "en": "Name"},
    "c_type":        {"ar": "النوع", "fr": "Type", "en": "Type"},
    "c_valeur":      {"ar": "القيمة", "fr": "Valeur", "en": "Value"},
    "sans_titre":    {"ar": "بلا عنوان", "fr": "Sans titre", "en": "Untitled"},
    "exec_ok":       {"ar": "انتهى التنفيذ بنجاح", "fr": "Exécution terminée sans erreur",
                      "en": "Finished with no error"},
    "assist_titre":  {"ar": "شرح الخطأ", "fr": "Explication de l'erreur",
                      "en": "Error explanation"},
    "col_q":         {"ar": "الجودة", "fr": "Qualité", "en": "Quality"},
    "col_r":         {"ar": "النتائج", "fr": "Résultats", "en": "Results"},
    "col_s":         {"ar": "البنية", "fr": "Structure", "en": "Structure"},
    "copie":         {"ar": "محاولة", "fr": "copie", "en": "copy"},
    "sous_interp":   {"ar": "المفسّر المستعمَل في الترجمة والتنفيذ والتصحيح",
                      "fr": "Interpréteur utilisé pour compiler, exécuter et corriger",
                      "en": "Interpreter used to compile, run and grade"},
    "sous_langue":   {"ar": "لغة رسائل الأخطاء والشروح والتقارير",
                      "fr": "Langue des messages d'erreur, explications et rapports",
                      "en": "Language of error messages, explanations and reports"},
    "sous_exo":      {"ar": "ملفّات التمرين — الحلّ إجباري للتصحيح والتنقيط",
                      "fr": "Fichiers du TP — la solution est requise pour noter",
                      "en": "Exercise files — the solution is required for grading"},
    "sous_lot":      {"ar": "اختر مجلّد نسخ التلاميذ ثم اضغط تصحيح",
                      "fr": "Choisissez le dossier des copies puis lancez la correction",
                      "en": "Pick the submissions folder then start grading"},
    "bt_demo":       {"ar": "تحميل تمرين تجريبي", "fr": "Charger le TP de démo",
                      "en": "Load demo exercise"},
    "c_mention":     {"ar": "التقدير", "fr": "Mention", "en": "Grade"},
    "c_num":         {"ar": "#", "fr": "#", "en": "#"},
    "pret":          {"ar": "جاهز", "fr": "Prêt", "en": "Ready"},
    "langue_expl":   {"ar": "لغة الشرح", "fr": "Langue des explications",
                      "en": "Explanation language"},
    "tab_config":    {"ar": "الإعداد", "fr": "Configuration", "en": "Setup"},
    "tab_lot":       {"ar": "تصحيح القسم", "fr": "Correction de la classe",
                      "en": "Grade the class"},
    "dossier":       {"ar": "مجلّد المحاولات", "fr": "Dossier des copies",
                      "en": "Submissions folder"},
    "moyenne":       {"ar": "المعدّل", "fr": "Moyenne", "en": "Average"},
    "reussite":      {"ar": "ناجحون", "fr": "Admis", "en": "Passing"},
    "tab_compat":    {"ar": "التوافق", "fr": "Compatibilité", "en": "Compatibility"},
    "bt_scan":       {"ar": "بحث عن المفسّرات", "fr": "Détecter les interpréteurs",
                      "en": "Scan interpreters"},
    "bt_parcourir":  {"ar": "اختيار python.exe", "fr": "Choisir python.exe",
                      "en": "Pick python.exe"},
    "bt_compat":     {"ar": "اختبر على كل النسخ", "fr": "Tester sur toutes les versions",
                      "en": "Test on all versions"},
    "c_interp":      {"ar": "المفسّر", "fr": "Interpréteur", "en": "Interpreter"},
    "c_compile":     {"ar": "الترجمة", "fr": "Compile", "en": "Compiles"},
    "c_exec":        {"ar": "التنفيذ", "fr": "Exécution", "en": "Runs"},
    "c_ms":          {"ar": "الزمن", "fr": "Durée", "en": "Time"},
    "c_sortie":      {"ar": "الخرج", "fr": "Sortie", "en": "Output"},
    "interp_actif":  {"ar": "المفسّر المستعمَل", "fr": "Interpréteur actif",
                      "en": "Active interpreter"},
    "interp_ok":     {"ar": "تمّ تغيير المفسّر", "fr": "Interpréteur changé",
                      "en": "Interpreter switched"},
    "interp_ko":     {"ar": "مسار غير صالح لمفسّر بايثون",
                      "fr": "Chemin d'interpréteur Python invalide",
                      "en": "Not a valid Python interpreter"},
    "interp_aucun":  {"ar": "لم يُعثر على مفسّرات أخرى.",
                      "fr": "Aucun autre interpréteur détecté.",
                      "en": "No other interpreter found."},
    "interpreteur":  {"ar": "المفسّر", "fr": "Interpréteur", "en": "Interpreter"},
    "compile_ok":    {"ar": "الترجمة نجحت", "fr": "Compilation réussie",
                      "en": "Compiles fine"},
    "titre_app":     {"ar": "محرّر بايثون", "fr": "Éditeur Python", "en": "Python editor"},
    "bt_analyser":   {"ar": "تحليل", "fr": "Analyser", "en": "Analyse"},
    "bt_executer":   {"ar": "تنفيذ", "fr": "Exécuter", "en": "Run"},
    "bt_corriger":   {"ar": "صحّح ونقّط", "fr": "Corriger & noter", "en": "Grade"},
    "bt_evaluer":    {"ar": "قيّم وصدّر", "fr": "Évaluer + PDF", "en": "Evaluate + PDF"},
    "bt_solution":   {"ar": "الحلّ", "fr": "Solution", "en": "Solution"},
    "bt_telecharger": {"ar": "تنزيل المشروح", "fr": "Télécharger annoté",
                       "en": "Download annotated"},
    "bt_enregistrer": {"ar": "حفظ", "fr": "Enregistrer", "en": "Save"},
    "bt_ouvrir":     {"ar": "فتح ملف", "fr": "Ouvrir", "en": "Open"},
    "bt_formater":   {"ar": "تنسيق", "fr": "Formater", "en": "Format"},
    "tab_notes":     {"ar": "الملاحظات", "fr": "Remarques", "en": "Findings"},
    "tab_run":       {"ar": "التنفيذ", "fr": "Sortie", "en": "Output"},
    "tab_tests":     {"ar": "الاختبارات", "fr": "Tests", "en": "Tests"},
    "tab_bareme":    {"ar": "السلّم", "fr": "Barème", "en": "Scale"},
    "tab_sol":       {"ar": "الحلّ", "fr": "Solution", "en": "Solution"},
    "tab_enonce":    {"ar": "نصّ التمرين", "fr": "Énoncé", "en": "Task"},
    "tab_hist":      {"ar": "المحاولات", "fr": "Historique", "en": "History"},
    "ph_stdin":      {"ar": "إدخال stdin (اختياري)", "fr": "Entrée stdin (option)",
                      "en": "stdin input (optional)"},
    "msg_analyser":  {"ar": "اضغط «تحليل».", "fr": "Cliquez sur « Analyser ».",
                      "en": "Click “Analyse”."},
    "msg_corriger":  {"ar": "اضغط «صحّح ونقّط».", "fr": "Cliquez sur « Corriger & noter ».",
                      "en": "Click “Grade”."},
    "msg_running":   {"ar": "… جارٍ التنفيذ", "fr": "… exécution en cours",
                      "en": "… running"},
    "msg_conf_sol":  {"ar": "سيُسجَّل أنّك اطّلعت على الحلّ. متابعة؟",
                      "fr": "Votre consultation de la solution sera enregistrée. Continuer ?",
                      "en": "Your viewing of the solution will be logged. Continue?"},
    "msg_no_sol":    {"ar": "لا يوجد حلّ نموذجي محمّل.", "fr": "Aucune solution chargée.",
                      "en": "No reference solution loaded."},
    "msg_saved":     {"ar": "✔ حُفظت المحاولة", "fr": "✔ Essai enregistré",
                      "en": "✔ Attempt saved"},
    "msg_vide":      {"ar": "لا محاولات بعد.", "fr": "Aucun essai pour l'instant.",
                      "en": "No attempts yet."},
    "st_lignes":     {"ar": "أسطر", "fr": "lignes", "en": "lines"},
    "aide":          {"ar": "Ctrl+↵ تحليل · F5 تنفيذ · Ctrl+S حفظ · Ctrl+/ تعليق · Tab إزاحة",
                      "fr": "Ctrl+↵ analyser · F5 exécuter · Ctrl+S enregistrer · Ctrl+/ commenter",
                      "en": "Ctrl+↵ analyse · F5 run · Ctrl+S save · Ctrl+/ comment"},
    "erreur":        {"ar": "خطأ", "fr": "Erreur", "en": "Error"},
    "avertissement": {"ar": "تحذير", "fr": "Avertissement", "en": "Warning"},
    "cause":         {"ar": "السبب", "fr": "Cause", "en": "Why"},
    "fix":           {"ar": "التصحيح", "fr": "Correction", "en": "Fix"},
    "suggestion":    {"ar": "الاقتراح", "fr": "Suggestion", "en": "Suggested"},
    "ligne":         {"ar": "السطر", "fr": "Ligne", "en": "Line"},
    "fichier":       {"ar": "الملف", "fr": "Fichier", "en": "File"},
    "remarques":     {"ar": "ملاحظة", "fr": "remarque(s)", "en": "finding(s)"},
    "aucun":         {"ar": "لا توجد مشاكل.", "fr": "Aucun problème détecté.",
                      "en": "No problems found."},
    "aucun_deduit":  {"ar": "لا خصم — لم تُنتهك أيّ قاعدة. ✅",
                      "fr": "Aucune pénalité — aucune règle enfreinte. ✅",
                      "en": "No penalty — no rule broken. ✅"},
    "rapport":       {"ar": "تقرير التحليل الآلي", "fr": "Rapport d'analyse automatique",
                      "en": "Automatic analysis report"},
    "nb_err":        {"ar": "عدد الأخطاء", "fr": "Erreurs", "en": "Errors"},
    "nb_warn":       {"ar": "عدد التحذيرات", "fr": "Avertissements", "en": "Warnings"},
    "legende":       {"ar": "❌ = خطأ ومكانه   💡 = السبب   ✅ = التصحيح المقترح",
                      "fr": "❌ = erreur   💡 = cause   ✅ = correction proposée",
                      "en": "❌ = error   💡 = cause   ✅ = suggested fix"},
    "note_finale":   {"ar": "النقطة النهائية", "fr": "Note finale", "en": "Final score"},
    "note":          {"ar": "النقطة", "fr": "Note", "en": "Score"},
    "bareme_titre":  {"ar": "سلّم التنقيط المطبَّق — نبدأ من 20 ونخصم:",
                      "fr": "Barème appliqué — on part de 20 et on retranche :",
                      "en": "Applied grading scale — start at 20 and subtract:"},
    "c_code":        {"ar": "الرمز", "fr": "Code", "en": "Code"},
    "c_regle":       {"ar": "الملاحظة", "fr": "Règle", "en": "Rule"},
    "c_nb":          {"ar": "العدد", "fr": "Nb", "en": "Count"},
    "c_unite":       {"ar": "×الخصم", "fr": "×pénal.", "en": "×pen."},
    "c_deduit":      {"ar": "المخصوم", "fr": "Retiré", "en": "Deducted"},
    "c_plafond":     {"ar": "السقف", "fr": "Plafond", "en": "Cap"},
    "total_deduit":  {"ar": "مجموع الخصم", "fr": "Total retiré", "en": "Total deducted"},
    "calcul":        {"ar": "20 − الخصم = النقطة", "fr": "20 − pénalités = note",
                      "en": "20 − penalties = score"},
    "note_bas":      {"ar": "ملاحظة: لكل قاعدة سقف خصم حتى لا يُفسد خطأ متكرّر النقطة "
                            "كلّها، والنقطة لا تنزل تحت 0.",
                      "fr": "Note : chaque règle a un plafond pour qu'une erreur répétée "
                            "ne détruise pas toute la note ; la note ne descend pas sous 0.",
                      "en": "Note: each rule has a cap so one repeated mistake cannot "
                            "destroy the whole score; the score never goes below 0."},
    "sortie":        {"ar": "الملف المشروح", "fr": "Fichier annoté", "en": "Annotated file"},
    "corrige":       {"ar": "السطر بعد التصحيح", "fr": "Ligne corrigée", "en": "Corrected line"},
    "original":      {"ar": "الأصل", "fr": "original", "en": "original"},
    # المصحّح
    "axe":           {"ar": "المحور", "fr": "Axe", "en": "Criterion"},
    "sur":           {"ar": "من", "fr": "sur", "en": "of"},
    "total":         {"ar": "المجموع", "fr": "Total", "en": "Total"},
    "ax_qualite":    {"ar": "(أ) جودة الكود", "fr": "(a) Qualité du code",
                      "en": "(a) Code quality"},
    "ax_tests":      {"ar": "(ب) صحّة النتائج", "fr": "(b) Exactitude des résultats",
                      "en": "(b) Correct results"},
    "ax_structure":  {"ar": "(ج) المطابقة البنيوية", "fr": "(c) Conformité structurelle",
                      "en": "(c) Structural conformity"},
    "tests":         {"ar": "الاختبارات", "fr": "Tests", "en": "Tests"},
    "structure":     {"ar": "البنية", "fr": "Structure", "en": "Structure"},
    "sur_code":      {"ar": "ملاحظات على الكود", "fr": "Remarques sur le code",
                      "en": "Code findings"},
    "attendu":       {"ar": "المنتظَر", "fr": "Attendu", "en": "Expected"},
    "obtenu":        {"ar": "المحصَّل", "fr": "Obtenu", "en": "Got"},
    "solution":      {"ar": "الحلّ النموذجي", "fr": "Solution de référence",
                      "en": "Reference solution"},
    "diff":          {"ar": "الفرق بين المحاولة والحلّ",
                      "fr": "Différence essai / solution", "en": "Diff attempt vs solution"},
    "fn_manquante":  {"ar": "الدالة '{nom}' مفقودة عند التلميذ.",
                      "fr": "La fonction '{nom}' est absente de la copie.",
                      "en": "Function '{nom}' is missing from the submission."},
    "fn_args":       {"ar": "'{nom}': عدد الوسائط {a} بدل {b}.",
                      "fr": "'{nom}' : {a} argument(s) au lieu de {b}.",
                      "en": "'{nom}': {a} argument(s) instead of {b}."},
    "fn_noms":       {"ar": "'{nom}': أسماء الوسائط مختلفة (مقبول لكن يُفضَّل التطابق).",
                      "fr": "'{nom}' : noms d'arguments différents (toléré, mais à aligner).",
                      "en": "'{nom}': different argument names (tolerated, better to match)."},
    "fn_extra":      {"ar": "دوال إضافية عند التلميذ: {liste}",
                      "fr": "Fonctions supplémentaires : {liste}",
                      "en": "Extra functions in submission: {liste}"},
    "exec_complet":  {"ar": "تنفيذ الملف كاملًا", "fr": "Exécution complète du fichier",
                      "en": "Whole-file execution"},
    "timeout":       {"ar": "تجاوز المهلة ({s}ث) — حلقة لا نهائية؟",
                      "fr": "Délai dépassé ({s}s) — boucle infinie ?",
                      "en": "Timeout ({s}s) — infinite loop?"},
    "exception":     {"ar": "استثناء", "fr": "exception", "en": "exception"},
}

# التقديرات حسب النقطة
MENTIONS = {
    "ar": [(18, "ممتاز — كود نظيف وجاهز للإنتاج"), (16, "جيد جدًا — ملاحظات تجميلية فقط"),
           (14, "جيد — تحسينات مستحسنة"), (12, "مقبول — يحتاج مراجعة"),
           (10, "متوسط — أخطاء تستوجب التصحيح"),
           (0, "ضعيف — إعادة كتابة أجزاء من الكود ضرورية")],
    "fr": [(18, "Excellent — code propre, prêt pour la production"),
           (16, "Très bien — remarques cosmétiques seulement"),
           (14, "Bien — améliorations conseillées"), (12, "Passable — à revoir"),
           (10, "Moyen — erreurs à corriger"),
           (0, "Insuffisant — réécriture de certaines parties nécessaire")],
    "en": [(18, "Excellent — clean, production-ready code"),
           (16, "Very good — only cosmetic remarks"), (14, "Good — improvements advised"),
           (12, "Fair — needs review"), (10, "Average — errors to fix"),
           (0, "Weak — parts of the code must be rewritten")],
}


# ---------------------------------------------------------------------------
def _choisir(dico: dict) -> dict:
    return dico.get(_courante) or dico.get(SECOURS) or {}


def R(code: str, **kw):
    """يُرجع (message, explication, correction) لقاعدة، مترجَمة ومملوءة."""
    base = _choisir(REGLES.get(code, {}))
    return (base.get("m", code).format(**kw),
            base.get("e", "").format(**kw),
            base.get("c", "").format(**kw))


def titre(code: str) -> str:
    """العنوان المختصر المستعمل في جدول السلّم."""
    return _choisir(REGLES.get(code, {})).get("t", code)


def U(cle: str, **kw) -> str:
    d = UI.get(cle, {})
    return (d.get(_courante) or d.get(SECOURS) or cle).format(**kw)


def mentions() -> list:
    return MENTIONS.get(_courante, MENTIONS[SECOURS])

# ---------------------------------------------------------------------------
# شرح الاستثناءات الشائعة أثناء التنفيذ (المساعد التربوي)
# ---------------------------------------------------------------------------
EXCEPTIONS = {
    "ZeroDivisionError": {
        "ar": ("قسمة على صفر.", "تحقّق من المقام قبل القسمة: if d != 0: ..."),
        "fr": ("Division par zéro.", "Testez le dénominateur : if d != 0: ..."),
        "en": ("Division by zero.", "Check the denominator first: if d != 0: ...")},
    "NameError": {
        "ar": ("اسم غير معرَّف — استُعمل متغيّر أو دالّة قبل إنشائها (أو خطأ مطبعي).",
               "تأكّد من كتابة الاسم ومن تعريفه قبل استعماله."),
        "fr": ("Nom inconnu — variable ou fonction utilisée avant d'exister (ou faute de frappe).",
               "Vérifiez l'orthographe et définissez le nom avant de l'utiliser."),
        "en": ("Unknown name — variable or function used before it exists (or a typo).",
               "Check the spelling and define it before use.")},
    "TypeError": {
        "ar": ("نوع غير متوافق — مثل جمع نصّ مع عدد، أو عدد وسائط خاطئ.",
               "حوّل الأنواع (int(x), str(x)) أو راجع وسائط الدالّة."),
        "fr": ("Types incompatibles — addition texte + nombre, ou mauvais nombre d'arguments.",
               "Convertissez (int(x), str(x)) ou vérifiez les arguments."),
        "en": ("Incompatible types — text + number, or wrong argument count.",
               "Convert with int(x)/str(x) or check the arguments.")},
    "IndexError": {
        "ar": ("فهرس خارج المجال — عنصر غير موجود في القائمة.",
               "تحقّق من الطول: if i < len(liste)، وتذكّر أنّ الفهرسة تبدأ من 0."),
        "fr": ("Indice hors limites — l'élément n'existe pas dans la liste.",
               "Vérifiez : if i < len(liste) ; l'indexation commence à 0."),
        "en": ("Index out of range — no such element in the list.",
               "Check with if i < len(list); indexing starts at 0.")},
    "KeyError": {
        "ar": ("مفتاح غير موجود في القاموس.",
               "استعمل dico.get(cle) أو تحقّق: if cle in dico."),
        "fr": ("Clé absente du dictionnaire.",
               "Utilisez dico.get(cle) ou testez : if cle in dico."),
        "en": ("Key not found in the dictionary.",
               "Use dict.get(key) or test with: if key in dict.")},
    "ValueError": {
        "ar": ("قيمة غير صالحة للعملية — مثل int(\"abc\").",
               "تحقّق من القيمة قبل التحويل، أو استعمل try/except ValueError."),
        "fr": ("Valeur invalide pour l'opération — par exemple int(\"abc\").",
               "Vérifiez la valeur avant conversion, ou try/except ValueError."),
        "en": ("Invalid value for the operation — e.g. int(\"abc\").",
               "Validate before converting, or use try/except ValueError.")},
    "AttributeError": {
        "ar": ("الكائن لا يملك هذه الخاصّية أو الطريقة.",
               "تأكّد من نوع الكائن؛ قد تكون القيمة None."),
        "fr": ("L'objet n'a pas cet attribut ou cette méthode.",
               "Vérifiez le type de l'objet ; la valeur est peut-être None."),
        "en": ("The object has no such attribute or method.",
               "Check the object's type; the value may be None.")},
    "IndentationError": {
        "ar": ("إزاحة خاطئة.", "استعمل 4 مسافات لكل مستوى، ولا تخلط Tab بالمسافات."),
        "fr": ("Indentation incorrecte.",
               "4 espaces par niveau, sans mélanger tabulations et espaces."),
        "en": ("Bad indentation.", "Use 4 spaces per level; never mix tabs and spaces.")},
    "ModuleNotFoundError": {
        "ar": ("الوحدة غير مثبَّتة أو الاسم خاطئ.",
               "ثبّتها: pip install <nom>، أو صحّح الاسم."),
        "fr": ("Module non installé ou mal orthographié.",
               "Installez-le : pip install <nom>, ou corrigez le nom."),
        "en": ("Module not installed or misspelled.",
               "Install it: pip install <name>, or fix the name.")},
    "RecursionError": {
        "ar": ("تكرار ذاتي بلا نهاية.", "أضف شرط توقّف واضحًا للدالّة."),
        "fr": ("Récursion infinie.", "Ajoutez une condition d'arrêt claire."),
        "en": ("Infinite recursion.", "Add a clear stopping condition.")},
    "FileNotFoundError": {
        "ar": ("الملف غير موجود في المسار المحدَّد.",
               "تحقّق من الاسم والمسار، واستعمل مسارًا مطلقًا عند الشكّ."),
        "fr": ("Fichier introuvable au chemin indiqué.",
               "Vérifiez le nom et le chemin ; utilisez un chemin absolu au besoin."),
        "en": ("File not found at the given path.",
               "Check name and path; use an absolute path if unsure.")},
    "UnboundLocalError": {
        "ar": ("متغيّر محلّي استُعمل قبل إسناد قيمة له داخل الدالّة.",
               "أسند قيمة أوّلية، أو استعمل global إن كان متغيّرًا عامًّا."),
        "fr": ("Variable locale utilisée avant affectation dans la fonction.",
               "Initialisez-la, ou déclarez global si elle est globale."),
        "en": ("Local variable used before assignment inside the function.",
               "Initialise it, or declare it global if it is global.")},
}


def exception(nom: str):
    """يُرجع (شرح، تصحيح) لاستثناء، أو None إن كان مجهولًا."""
    d = EXCEPTIONS.get(nom)
    if not d:
        return None
    return d.get(_courante) or d.get(SECOURS)
