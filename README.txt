Projet divisé en DEUX applications graphiques (PyQt5)
=====================================================
Interface : une barre de MENUS en haut ; sous chaque menu, sa rangée de BOUTONS.
Les mêmes actions existent aussi dans la vraie barre de menus (raccourcis clavier).

┌─ APPLICATION 1 : atelier.py — écrire et exécuter (style Thonny amélioré)
│  python atelier.py [fichier.py]
│  Menus : 📄 Fichier · ✏ Édition · ▶ Exécution · 🔍 Assistant ·
│          🐍 Interpréteur · 👁 Affichage · ❓ Aide
│  • éditeur multi-onglets, coloration, numéros de ligne, marques ●
│  • console interactive (REPL) + exécution du fichier dedans (F5)
│  • panneau Variables mis à jour après chaque exécution
│  • Assistant : explique les erreurs (ar/fr/en) + note /20
│  • changement de python.exe à chaud + test sur toutes les versions
│
└─ APPLICATION 2 : correcteur_app.py — corriger, expliquer, noter
   python correcteur_app.py [-s solution.py -t tests.json -e enonce.txt --lang fr]
   Menus : 📄 TP · ✏ Copie · 📊 Corriger & noter · 👥 Correction de la classe ·
           🐍 Interpréteur · 👁 Affichage · ❓ Aide
   • page « Copie »  : éditeur + 8 panneaux (Remarques, Sortie, Tests, Barème,
     Solution + diff, Énoncé, Historique, Compatibilité)
   • page « Classe » : corrige tout un dossier, tableau trié, mention, moyenne,
     export CSV, double-clic = ouvrir la copie avec sa correction
   • bouton « Charger le TP de démo » remplit tout automatiquement

MOTEUR PARTAGÉ
  langues.py · analyseur.py · correcteur.py · interpreteurs.py · ruban.py
  ide_qt.py (widgets réutilisés) · ide.py (version navigateur, Android/Termux)
  lanceur.py (ancien tableau de bord, toujours fonctionnel)

FICHIERS DE TEST
  enonce.txt · solution.py · tests.json (9 tests dont 4 cas limites)
  essai_eleve.py · essai_annote.py
  classe/ : 7 copies (imports inutilisés, > au lieu de >=, argument mutable,
            copie parfaite, erreur de syntaxe, boucle infinie, signature fausse)

RÉSULTAT ATTENDU SUR classe/ :
  n = 7 · Moyenne 14.85/20 · min 1.2 · max 20.0 · méd 16.27 · Admis ≥10 : 6/7

RAPPORT EXCEL (7 feuilles)
  Menu 👥 → bouton « 📊 Excel »  (ou en ligne de commande) :
    python rapport_excel.py classe/ -s solution.py -t tests.json -o notes.xlsx
  Feuilles : Synthèse · Notes · Tests (matrice élève×test) · Détail tests ·
             Erreurs · Fréquences (notion à réexpliquer) · Barème
  Les statistiques sont des FORMULES vivantes : corrigez une note à la main
  dans la feuille Notes, la Synthèse se recalcule.

BASE DE DONNÉES ACCESS (menu 👥 → « 🗄 Access / BD »)
  python rapport_access.py classe/ -s solution.py -t tests.json -o notes.accdb
  python rapport_access.py classe/ -s solution.py --mode sqlite -o notes.db
  python rapport_access.py classe/ -s solution.py --mode csv -o export_csv/
  python rapport_access.py --diagnostic     (que peut faire cette machine ?)
  Tables : Parametres · Eleves · Tests · Resultats · Erreurs · Bareme
  Requêtes : Q_Synthese · Q_ReussiteParTest · Q_FrequenceErreurs ·
             Q_ElevesEnDifficulte
  .accdb exige Windows + Microsoft Access Database Engine (ACE) :
      pip install pyodbc msaccessdb
  Sinon : --mode csv (import direct dans Access) ou --mode sqlite (lien ODBC).

CORRECTION DE BASES DE DONNÉES (Access / SQLite)  —  correcteur_access.py
  python correcteur_access.py bd/eleve2_rania.db -s bd/solution.db --lang fr
  python correcteur_access.py bd/ -s bd/solution.db --excel rapport_bd.xlsx
  python correcteur_access.py --diagnostic
  Compare : tables · champs (nom, type, taille) · clés primaires · relations ·
            requêtes (exécutées et comparées ligne à ligne) · données saisies
            (contenu des tables, hors clé primaire, comparé ligne à ligne)
  Barème /20 : Tables 4 · Champs 4 · Données 2 · Clés 2 · Relations 4 · Requêtes 4
  Rapport Excel : Notes · Comparaison (élève vs solution) · Écarts · Fréquences
  Lecture .accdb : Windows + pip install pyodbc + moteur ACE
                   Linux : sudo apt install mdbtools
                   .db (SQLite) : partout, sans rien installer
  Exemples fournis dans bd/ : solution.db, eleve1_sami.db (18.67), eleve2_rania.db (10.04)

BARÈME MODIFIABLE  —  bareme.py + editeur_bareme.py
  Le barème n'est plus figé dans le code : c'est un fichier JSON dans baremes/.
  python bareme.py                         crée les profils prêts à l'emploi
  --bareme standard|debutant|examen|algorithmique|mon_fichier.json
      (option disponible dans analyseur.py, correcteur.py, correcteur_app.py)
  Dans l'interface : menu « ⚖ Barème » → liste des profils · ✏ Éditer (Ctrl+B)
      · ♻ Recalculer (réapplique le barème à toute la classe)
  L'éditeur permet de régler : note max · tolérance (avertissements gratuits) ·
      « erreur de syntaxe = 0 » · seuils des mentions · poids des 3 axes
      (contrôle que la somme = note max) · pour chaque règle : actif/inactif,
      pénalité, plafond · bouton « Aperçu sur la classe » qui montre l'effet
      du nouveau barème sur les notes avant de l'appliquer.
  Une règle décochée est toujours détectée et expliquée, mais ne coûte rien.

  Effet réel sur la copie 01_ahmed.py :
      Standard 16.27 · Débutant 17.67 · Examen 14.92 · Algorithmique 17.59
      (05_karim.py, erreur de syntaxe : 1.2 en standard, 0.0 en examen)

TOUT EN INTERFACE GRAPHIQUE (aucune ligne de commande nécessaire)
  python correcteur_app.py   →  7 menus, 3 pages :
     📄 TP            fichiers du TP + « Charger le TP de démo »
     ✏ Copie         ouvrir / exécuter / formater / annoter une copie
     📊 Corriger      analyser · corriger & noter · solution · compatibilité
     ⚖ Barème        choisir un profil · éditer (Ctrl+B) · recalculer
     👥 Classe        corriger un dossier · CSV · Excel · Access/BD
     🗄 BD            corriger un dossier de bases .accdb/.db · Excel · Diagnostic
     🐍 Interpréteur  choisir python.exe · scanner · tester toutes les versions
  Page « Bases de données » : tableau des notes + panneau de comparaison
     (Tables/Champs/Relations/Requêtes élève ↔ solution) + tous les écarts expliqués.
  Le bouton « 🔧 Diagnostic » du menu BD dit ce que la machine sait lire/écrire.

INSTALLATION
  pip install PyQt5 openpyxl          # nécessaire
  pip install pyodbc msaccessdb       # seulement pour écrire un .accdb (Windows)
