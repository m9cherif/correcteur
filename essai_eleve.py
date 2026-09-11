import os
import math

def moyenne(notes):
    return sum(notes) / len(notes)

def mention(moy):
    if moy == None:
        return "Insuffisant"
    if moy >= 16: return "Excellent"
    elif moy >= 14: return "Bien"
    elif moy >= 10: return "Passable"
    else: return "Insuffisant"

def admis(notes, seuil=10, historique=[]):
    historique.append(notes)
    try:
        return moyenne(notes) >= seuil
    except:
        pass
