-- 02_rania.db → Access
-- Access ▸ Créer ▸ Création de requête ▸ fermer l'assistant ▸
--   bouton « Mode SQL » ▸ coller UNE instruction ▸ Exécuter (!)
-- Les CREATE VIEW deviennent des requêtes : gardez exactement
-- les noms R1_MoyenneParEleve, R2_ElevesEnEchec, R3_NotesInformatique

CREATE TABLE [Eleve] (
  [IdEleve] LONG,
  [Nom] TEXT(20) NOT NULL,
  [Prenom] TEXT(40),
  [DateNaiss] TEXT(20),
  [Classe] TEXT(10)
);

CREATE TABLE [Matiere] (
  [IdMatiere] AUTOINCREMENT,
  [Libelle] TEXT(30) NOT NULL,
  [Coefficient] LONG,
  CONSTRAINT PK_Matiere PRIMARY KEY ([IdMatiere])
);

CREATE TABLE [Note] (
  [IdNote] AUTOINCREMENT,
  [IdEleve] LONG,
  [IdMatiere] LONG,
  [Valeur] DOUBLE,
  CONSTRAINT PK_Note PRIMARY KEY ([IdNote])
);

CREATE TABLE [Brouillon] (
  [X] LONG
);

INSERT INTO [Eleve] ([IdEleve], [Nom], [Prenom], [DateNaiss], [Classe]) VALUES (1, 'Belhaj', 'Amina', #2008-03-12#, '3A');

INSERT INTO [Eleve] ([IdEleve], [Nom], [Prenom], [DateNaiss], [Classe]) VALUES (2, 'Karimi', 'Omar', #2008-07-01#, '3A');

INSERT INTO [Eleve] ([IdEleve], [Nom], [Prenom], [DateNaiss], [Classe]) VALUES (3, 'Nasri', 'Lina', #2008-11-23#, '3B');

INSERT INTO [Matiere] ([IdMatiere], [Libelle], [Coefficient]) VALUES (1, 'Maths', 4);

INSERT INTO [Matiere] ([IdMatiere], [Libelle], [Coefficient]) VALUES (2, 'Informatique', 3);

INSERT INTO [Matiere] ([IdMatiere], [Libelle], [Coefficient]) VALUES (3, 'Francais', 2);

INSERT INTO [Note] ([IdNote], [IdEleve], [IdMatiere], [Valeur]) VALUES (1, 1, 1, 17.5);

INSERT INTO [Note] ([IdNote], [IdEleve], [IdMatiere], [Valeur]) VALUES (2, 1, 2, 19.0);

INSERT INTO [Note] ([IdNote], [IdEleve], [IdMatiere], [Valeur]) VALUES (3, 2, 1, 8.0);

INSERT INTO [Note] ([IdNote], [IdEleve], [IdMatiere], [Valeur]) VALUES (4, 2, 2, 12.0);

CREATE VIEW [R1_MoyenneParEleve] AS
SELECT e.Nom, e.Prenom, Avg(n.Valeur) AS Moyenne FROM Eleve AS e, Note n GROUP BY e.Nom, e.Prenom;

CREATE VIEW [R2_ElevesEnEchec] AS
SELECT Nom, Prenom FROM Eleve;

CREATE VIEW [R3_NotesInformatique] AS
SELECT e.Nom, n.Valeur FROM Note AS n INNER JOIN Eleve AS e ON e.IdEleve=n.IdEleve
  INNER JOIN Matiere AS m ON m.IdMatiere=n.IdMatiere WHERE m.Libelle='Informatique';

