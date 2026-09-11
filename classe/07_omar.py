def moyenne(notes):
    if not notes:
        return 0
    return sum(notes) / len(notes)

def mention(moy):
    if moy >= 16: return "Tres bien"
    if moy >= 14: return "Bien"
    if moy >= 10: return "Passable"
    return "Insuffisant"

def admis(notes):
    return moyenne(notes) >= 10
