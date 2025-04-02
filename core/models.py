from django.db import models

class Etablissement(models.Model):
    nom = models.CharField(max_length=200)
    adresse = models.TextField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    annee_scolaire_active = models.CharField(max_length=10, default="2024-2025")  # Ex: "2024-2025"
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    
    def __str__(self):
        return self.nom

class InspectionAcademique(models.Model):
    nom = models.CharField(max_length=200)
    
    def __str__(self):
        return self.nom

class Niveau(models.Model):
    nom = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    ordre = models.IntegerField(default=0)
    
    def __str__(self):
        return self.nom
    
    class Meta:
        ordering = ['ordre']

class Classe(models.Model):
    nom = models.CharField(max_length=50)
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE, related_name='classes')
    effectif = models.IntegerField(default=0)
    annee_scolaire = models.CharField(max_length=10, default="2024-2025")  # Ex: "2024-2025"
    
    def __str__(self):
        return self.nom
    
    class Meta:
        ordering = ['niveau__ordre', 'nom']

class ImportFichier(models.Model):
    SEMESTRE_CHOICES = [
        (1, 'Semestre 1'),
        (2, 'Semestre 2'),
    ]
    STATUS_CHOICES = [
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('erreur', 'Erreur'),
    ]
    
    titre = models.CharField(max_length=200)
    fichier = models.FileField(upload_to='imports/')
    semestre = models.IntegerField(choices=SEMESTRE_CHOICES)
    date_import = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=10, choices=STATUS_CHOICES, default='en_cours')
    erreur_message = models.TextField(blank=True, null=True)
    annee_scolaire = models.CharField(max_length=10)
    
    def __str__(self):
        return f"{self.titre} (Semestre {self.semestre}, {self.statut})"
    
    class Meta:
        ordering = ['-date_import']

class MoyenneEleve(models.Model):
    import_fichier = models.ForeignKey(ImportFichier, on_delete=models.CASCADE, related_name='moyennes')
    nom_eleve = models.CharField(max_length=100)
    prenom_eleve = models.CharField(max_length=100, blank=True, null=True)
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='moyennes')
    moyenne_generale = models.FloatField()
    rang = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.nom_eleve} {self.prenom_eleve or ''} - {self.moyenne_generale}"
    
    class Meta:
        ordering = ['-moyenne_generale']

class MoyenneDiscipline(models.Model):
    eleve = models.ForeignKey(MoyenneEleve, on_delete=models.CASCADE, related_name='disciplines')
    nom_discipline = models.CharField(max_length=100)
    moyenne = models.FloatField()
    
    def __str__(self):
        return f"{self.eleve.nom_eleve} - {self.nom_discipline}: {self.moyenne}"
    
    # Ajoutez ceci à models.py

class DonneesMoyennesEleves(models.Model):
    """Stockage des données du tableau 'Moyennes eleves'"""
    import_fichier = models.ForeignKey(ImportFichier, on_delete=models.CASCADE, related_name='donnees_moyennes')
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100, blank=True, null=True)
    classe = models.CharField(max_length=50, blank=True, null=True)
    moyenne_generale = models.FloatField(null=True)
    # Ajoutez ici d'autres colonnes qui apparaissent régulièrement dans le tableau Moyennes eleves
    # Par exemple :
    rang_classe = models.IntegerField(null=True, blank=True)
    effectif_classe = models.IntegerField(null=True, blank=True)
    # Pour les colonnes supplémentaires ou variables, nous utiliserons un champ JSON
    donnees_additionnelles = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.nom} {self.prenom or ''} - {self.moyenne_generale}"
    
    class Meta:
        ordering = ['-moyenne_generale']
        verbose_name = "Données moyennes élèves"
        verbose_name_plural = "Données moyennes élèves"

class DonneesDetailleesEleves(models.Model):
    """Stockage des données du tableau 'Données détaillées'"""
    import_fichier = models.ForeignKey(ImportFichier, on_delete=models.CASCADE, related_name='donnees_detaillees')
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100, blank=True, null=True)
    classe = models.CharField(max_length=50, blank=True, null=True)
    # Pour les colonnes de disciplines qui sont variables, nous utiliserons un champ JSON
    disciplines = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.nom} {self.prenom or ''}"
    
    class Meta:
        verbose_name = "Données détaillées élèves"
        verbose_name_plural = "Données détaillées élèves"