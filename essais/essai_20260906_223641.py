# note=1.2 date=20260906_223641 vu_solution=False (correction)
def moyenne(notes)
    return sum(notes) / len(notes)

def mention(moy):
    if moy >= 16:
        return "Excellent"
    return "Insuffisant"

def admis(notes, seuil=10):
    return moyenne(notes) >= seuil
