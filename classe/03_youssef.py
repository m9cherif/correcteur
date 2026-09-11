import random

def moyenne(notes):
    if len(notes) == 0:
        return 0
    total = 0
    for n in notes:
        total = total + n
    return total / len(notes)

def mention(moy):
    if moy >= 16:
        return "Excellent"
    elif moy >= 14:
        return "Bien"
    elif moy >= 10:
        return "Passable"
    else:
        return "Insuffisant"

def admis(notes, seuil=10, journal=[]):
    journal.append(notes)
    return moyenne(notes) >= seuil
