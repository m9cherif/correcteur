CREATE TABLE Eleve (IdEleve INTEGER, Nom VARCHAR(20) NOT NULL, Prenom VARCHAR(40),
                    DateNaiss VARCHAR(20), Classe VARCHAR(10));
CREATE TABLE Matiere (IdMatiere INTEGER PRIMARY KEY, Libelle VARCHAR(30) NOT NULL,
                      Coefficient INTEGER);
CREATE TABLE Note (IdNote INTEGER PRIMARY KEY, IdEleve INTEGER, IdMatiere INTEGER,
                   Valeur REAL);
CREATE TABLE Brouillon (X INTEGER);
INSERT INTO Eleve VALUES (1,'Belhaj','Amina','2008-03-12','3A'),(2,'Karimi','Omar','2008-07-01','3A'),(3,'Nasri','Lina','2008-11-23','3B');
INSERT INTO Matiere VALUES (1,'Maths',4),(2,'Informatique',3),(3,'Francais',2);
INSERT INTO Note VALUES (1,1,1,17.5),(2,1,2,19),(3,2,1,8),(4,2,2,12);
CREATE VIEW R1_MoyenneParEleve AS
  SELECT e.Nom, e.Prenom, AVG(n.Valeur) AS Moyenne FROM Eleve e, Note n GROUP BY e.IdEleve;
CREATE VIEW R2_ElevesEnEchec AS SELECT Nom, Prenom FROM Eleve;
CREATE VIEW R3_NotesInformatique AS
  SELECT e.Nom, n.Valeur FROM Note n JOIN Eleve e ON e.IdEleve=n.IdEleve
  JOIN Matiere m ON m.IdMatiere=n.IdMatiere WHERE m.Libelle='Informatique';
