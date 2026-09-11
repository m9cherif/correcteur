CREATE TABLE Eleve (IdEleve INTEGER PRIMARY KEY, Nom VARCHAR(40) NOT NULL,
                    Prenom VARCHAR(40), DateNaiss DATE, Classe VARCHAR(10));
CREATE TABLE Matiere (IdMatiere INTEGER PRIMARY KEY, Libelle VARCHAR(30) NOT NULL,
                      Coefficient INTEGER);
CREATE TABLE Note (IdNote INTEGER PRIMARY KEY, IdEleve INTEGER, IdMatiere INTEGER,
                   Valeur REAL, DateEval DATE,
  FOREIGN KEY (IdEleve) REFERENCES Eleve(IdEleve),
  FOREIGN KEY (IdMatiere) REFERENCES Matiere(IdMatiere));
INSERT INTO Eleve VALUES (1,'Belhaj','Amina','2008-03-12','3A'),(2,'Karimi','Omar','2008-07-01','3A'),(3,'Nasri','Lina','2008-11-23','3B');
INSERT INTO Matiere VALUES (1,'Maths',4),(2,'Informatique',3),(3,'Francais',2);
INSERT INTO Note VALUES (1,1,1,17.5,'2026-01-10'),(2,1,2,19,'2026-01-12'),(3,2,1,8,'2026-01-10'),(4,2,2,12,'2026-01-12'),(5,3,1,14,'2026-01-10'),(6,3,3,11,'2026-01-15');
CREATE VIEW R1_MoyenneParEleve AS
  SELECT e.Nom, e.Prenom, ROUND(AVG(n.Valeur),2) AS Moyenne
  FROM Eleve e JOIN Note n ON n.IdEleve=e.IdEleve GROUP BY e.IdEleve;
CREATE VIEW R2_ElevesEnEchec AS
  SELECT Nom, Prenom FROM Eleve e
  WHERE (SELECT AVG(Valeur) FROM Note WHERE IdEleve=e.IdEleve) < 10;
CREATE VIEW R3_NotesInformatique AS
  SELECT e.Nom, n.Valeur FROM Note n JOIN Eleve e ON e.IdEleve=n.IdEleve
  JOIN Matiere m ON m.IdMatiere=n.IdMatiere WHERE m.Libelle='Informatique';
