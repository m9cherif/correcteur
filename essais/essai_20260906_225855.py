# note=20.0 date=20260906_225855 vu_solution=False (correction)
def moyenne(notes):
    if not notes:
        return 0
    return sum(notes) / len(notes)


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
