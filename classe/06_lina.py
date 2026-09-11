def moyenne(notes):
    total = 0
    i = 0
    while i < len(notes):
        total += notes[i]
    return total / len(notes) if notes else 0

def mention(moy):
    if moy >= 16:
        return "Excellent"
    if moy >= 14:
        return "Bien"
    if moy >= 10:
        return "Passable"
    return "Insuffisant"

def admis(notes, seuil=10):
    return moyenne(notes) >= seuil
