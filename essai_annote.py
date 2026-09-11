# ===========================================================================
# Rapport d'analyse automatique — essai_eleve.py
# Erreurs: 1 | Avertissements: 4
# 📊 Note: 13.5 / 20  →  Passable — à revoir
# ❌ = erreur   💡 = cause   ✅ = correction proposée
# ===========================================================================
# 📊 Note finale : 13.5 / 20   (Passable — à revoir)
# 
# Barème appliqué — on part de 20 et on retranche :
# Code   Règle                                         Nb ×pénal.   Retiré Plafond
# --------------------------------------------------------------------------------
# E102   Argument par défaut mutable (liste=[])         1     3.0     3.00     6.0
# W101   except: sans type d'exception                  1     1.5     1.50     4.5
# W103   Comparaison à None avec == au lieu de is       1     1.0     1.00     3.0
# W107   Import inutilisé                               2     0.5     1.00     2.0
# --------------------------------------------------------------------------------
# Total retiré                                                6.50
# 20 − pénalités = note                                      13.50
# 
# Note : chaque règle a un plafond pour qu'une erreur répétée ne détruise pas toute la note ; la note ne descend pas sous 0.
# ===========================================================================

# ------------------------------------------------------------
# ⚠️ [W107] Ligne 1: Import inutilisé : 'os'
# 💡 Cause: Alourdit le fichier et ralentit le démarrage sans aucun bénéfice.
# ✅ Correction: Supprimez l'import 'os' ou utilisez-le.
# ------------------------------------------------------------
import os
# ------------------------------------------------------------
# ⚠️ [W107] Ligne 2: Import inutilisé : 'math'
# 💡 Cause: Alourdit le fichier et ralentit le démarrage sans aucun bénéfice.
# ✅ Correction: Supprimez l'import 'math' ou utilisez-le.
# ------------------------------------------------------------
import math

def moyenne(notes):
    return sum(notes) / len(notes)

def mention(moy):
    # ------------------------------------------------------------
    # ⚠️ [W103] Ligne 8: Comparaison à None avec '=='
    # 💡 Cause: None est un singleton : la comparaison d'identité est plus sûre et n'est pas altérée par __eq__.
    # ✅ Correction: Utilisez 'is None' au lieu de '== None'.
    # ✅ Ligne corrigée:
    #     if moy is None:
    # ------------------------------------------------------------
    if moy == None:
        return "Insuffisant"
    if moy >= 16: return "Excellent"
    elif moy >= 14: return "Bien"
    elif moy >= 10: return "Passable"
    else: return "Insuffisant"

# ------------------------------------------------------------
# ❌ [E102] Ligne 15: Argument par défaut mutable dans la fonction 'admis'
# 💡 Cause: La valeur par défaut est créée une seule fois : les données s'accumulent entre les appels et produisent des résultats imprévus.
# ✅ Correction: Utilisez None : def f(x=None): x = [] if x is None else x
# ------------------------------------------------------------
def admis(notes, seuil=10, historique=[]):
    historique.append(notes)
    try:
        return moyenne(notes) >= seuil
    # ------------------------------------------------------------
    # ⚠️ [W101] Ligne 19: Utilisation de 'except:' sans préciser l'exception
    # 💡 Cause: Capture même KeyboardInterrupt et SystemExit et masque les vraies erreurs.
    # ✅ Correction: Précisez le type : except Exception as e:
    # ✅ Ligne corrigée:
    #     except Exception as e:
    # ------------------------------------------------------------
    except:
        pass
