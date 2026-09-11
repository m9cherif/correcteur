def moyenne(notes)
    return sum(notes) / len(notes)

def mention(moy):
    if moy >= 16:
        return "Excellent"
    return "Insuffisant"

def admis(notes, seuil=10):
    return moyenne(notes) >= seuil
