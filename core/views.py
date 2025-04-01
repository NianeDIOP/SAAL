from django.shortcuts import render, redirect
from django.contrib import messages
import pandas as pd
from .models import Etablissement, InspectionAcademique, Niveau, Classe, ImportFichier, MoyenneEleve, MoyenneDiscipline
from django.shortcuts import render, redirect, get_object_or_404

def accueil(request):
    """
    Vue pour la page d'accueil
    """
    context = {
        'title': 'Système d\'Analyse Académique Local',
    }
    return render(request, 'core/accueil.html', context)

def configuration(request):
    """
    Vue pour la page de configuration initiale
    """
    # Récupérer ou créer les objets de configuration
    etablissement, _ = Etablissement.objects.get_or_create(id=1)
    inspection, _ = InspectionAcademique.objects.get_or_create(id=1)
    
    # Récupérer tous les niveaux et classes
    niveaux = Niveau.objects.all()
    classes = Classe.objects.filter(annee_scolaire=etablissement.annee_scolaire_active)
    
    # Déterminer l'onglet actif (pour rediriger vers la même section après soumission)
    active_tab = request.session.get('active_tab', 'etablissement')
    
    # Traiter les soumissions de formulaires
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        # Formulaire établissement
        if form_type == 'etablissement':
            etablissement.nom = request.POST.get('nom')
            etablissement.adresse = request.POST.get('adresse', '')
            etablissement.telephone = request.POST.get('telephone', '')
            etablissement.email = request.POST.get('email', '')
            
            if 'logo' in request.FILES:
                etablissement.logo = request.FILES['logo']
                
            etablissement.save()
            messages.success(request, "Informations de l'établissement mises à jour avec succès.")
            request.session['active_tab'] = 'etablissement'
        
        # Formulaire inspection
        elif form_type == 'inspection':
            inspection.nom = request.POST.get('nom')
            inspection.save()
            messages.success(request, "Nom de l'inspection académique mis à jour avec succès.")
            request.session['active_tab'] = 'inspection'
        
        # Formulaire année scolaire
        elif form_type == 'annee_scolaire':
            annee = request.POST.get('annee')
            if annee:
                etablissement.annee_scolaire_active = annee
                etablissement.save()
                messages.success(request, f"Année scolaire {annee} définie comme active.")
            request.session['active_tab'] = 'annee_scolaire'
        
        # Formulaire nouveau niveau
        elif form_type == 'niveau':
            Niveau.objects.create(
                nom=request.POST.get('nom'),
                description=request.POST.get('description', ''),
                ordre=request.POST.get('ordre', 0)
            )
            messages.success(request, "Niveau ajouté avec succès.")
            request.session['active_tab'] = 'niveaux'
            
        # Formulaire édition niveau
        elif form_type == 'edit_niveau':
            niveau_id = request.POST.get('niveau_id')
            niveau = Niveau.objects.get(id=niveau_id)
            niveau.nom = request.POST.get('nom')
            niveau.description = request.POST.get('description', '')
            niveau.ordre = request.POST.get('ordre', 0)
            niveau.save()
            messages.success(request, "Niveau mis à jour avec succès.")
            request.session['active_tab'] = 'niveaux'
        
        # Formulaire nouvelle classe
        elif form_type == 'classe':
            niveau_id = request.POST.get('niveau')
            if niveau_id:
                niveau = Niveau.objects.get(id=niveau_id)
                Classe.objects.create(
                    nom=request.POST.get('nom'),
                    niveau=niveau,
                    effectif=request.POST.get('effectif', 0),
                    annee_scolaire=etablissement.annee_scolaire_active
                )
                messages.success(request, "Classe ajoutée avec succès.")
            request.session['active_tab'] = 'classes'
        
        return redirect('core:configuration')
    
    context = {
        'etablissement': etablissement,
        'inspection': inspection,
        'niveaux': niveaux,
        'classes': classes,
        'active_tab': active_tab,
    }
    
    return render(request, 'core/configuration.html', context)

def semestre1_accueil(request):
    """
    Vue d'accueil pour le module Semestre 1
    """
    # Récupérer l'établissement
    etablissement = Etablissement.objects.first()
    
    # Récupérer les dernières importations
    imports = ImportFichier.objects.filter(
        semestre=1, 
        annee_scolaire=etablissement.annee_scolaire_active if etablissement else "2024-2025"
    ).order_by('-date_import')[:5]
    
    context = {
        'etablissement': etablissement,
        'imports': imports,
    }
    
    return render(request, 'core/semestre1/accueil.html', context)

import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Etablissement, Classe, ImportFichier, MoyenneEleve, MoyenneDiscipline

def semestre1_importation(request):
    """
    Vue pour l'importation et le nettoyage des fichiers Excel du Semestre 1
    """
    etablissement = Etablissement.objects.first()
    annee_scolaire = etablissement.annee_scolaire_active if etablissement else "2024-2025"
    classes = Classe.objects.filter(annee_scolaire=annee_scolaire)
    imports = ImportFichier.objects.filter(semestre=1, annee_scolaire=annee_scolaire)
    
    if request.method == 'POST' and request.FILES.get('fichier_excel'):
        titre = request.POST.get('titre', 'Import sans titre')
        fichier_excel = request.FILES['fichier_excel']
        classe_id = request.POST.get('classe')
        
        import_fichier = ImportFichier.objects.create(
            titre=titre,
            fichier=fichier_excel,
            semestre=1,
            annee_scolaire=annee_scolaire,
            statut='en_cours'
        )
        
        try:
            import pandas as pd
            
            xls = pd.ExcelFile(fichier_excel)
            
            # --- 1) Lecture de l'onglet "Moyennes eleves"
            df_moyennes = pd.read_excel(
                xls,
                sheet_name="Moyennes eleves",
                skiprows=range(11),  # Ignore les 11 premières lignes
                header=0
            )
            
            # --- 2) Lecture de l'onglet "Données détaillées"
            df_detail = pd.read_excel(
                xls,
                sheet_name="Données détaillées",
                skiprows=range(8),  # Ignore les 8 premières lignes
                header=[0, 1]  # Lit les 2 premières lignes comme en-têtes (fusionnées)
            )
            
            # --- 3) Extraire les noms des disciplines et remplacer "Unnamed"
            disciplines = df_detail.columns.get_level_values(0).tolist()
            sous_colonnes = df_detail.columns.get_level_values(1).tolist()
            
            for i in range(len(disciplines)):
                if "Unnamed" in disciplines[i]:  
                    disciplines[i] = disciplines[i - 1]  # Remplace par le nom précédent (qui est valide)
            
            # --- 4) Sélectionner les 3 premières colonnes (Infos élèves)
            info_colonnes = df_detail.iloc[:, :3]
            info_colonnes.columns = [col[0] for col in info_colonnes.columns]
            
            # --- 5) Sélectionner uniquement les colonnes "Moy D" et récupérer leurs positions
            colonnes_moy_d = [i for i, col in enumerate(sous_colonnes) if col == "Moy D"]
            df_detail_moy_d = df_detail.iloc[:, colonnes_moy_d]
            noms_moy_d = [disciplines[i] for i in colonnes_moy_d]
            df_detail_moy_d.columns = noms_moy_d
            
            # --- 6) Fusionner les infos élèves avec les moyennes "Moy D"
            df_final = pd.concat([info_colonnes, df_detail_moy_d], axis=1)
            
            if classe_id:
                classe = Classe.objects.get(id=classe_id)
                
                # Parcourir les données nettoyées et créer des enregistrements
                for index, row in df_final.iterrows():
                    nom = str(row.get('Nom', ''))
                    prenom = str(row.get('Prénom', ''))
                    
                    if nom:  # S'assurer qu'il y a un nom avant de créer un enregistrement
                        # Calculer la moyenne générale
                        moyennes_disciplinaires = []
                        
                        for col in df_final.columns:
                            if col not in ['Nom', 'Prénom', 'Classe']:
                                val = row.get(col)
                                if pd.notna(val) and isinstance(val, (int, float)):
                                    moyennes_disciplinaires.append(val)
                        
                        moyenne_generale = sum(moyennes_disciplinaires) / len(moyennes_disciplinaires) if moyennes_disciplinaires else 0
                        
                        # Créer l'enregistrement de moyenne générale
                        eleve = MoyenneEleve.objects.create(
                            import_fichier=import_fichier,
                            nom_eleve=nom,
                            prenom_eleve=prenom,
                            classe=classe,
                            moyenne_generale=moyenne_generale,
                            rang=0  # Rang à calculer ultérieurement
                        )
                        
                        # Créer les enregistrements de moyennes par discipline
                        for col in df_final.columns:
                            if col not in ['Nom', 'Prénom', 'Classe']:
                                val = row.get(col)
                                if pd.notna(val) and isinstance(val, (int, float)):
                                    MoyenneDiscipline.objects.create(
                                        eleve=eleve,
                                        nom_discipline=col,
                                        moyenne=val
                                    )
            
            import_fichier.statut = 'termine'
            import_fichier.save()
            messages.success(request, "Le fichier a été importé et nettoyé avec succès.")
            
        except Exception as e:
            import_fichier.statut = 'erreur'
            import_fichier.erreur_message = str(e)
            import_fichier.save()
            messages.error(request, f"Une erreur s'est produite lors de l'importation : {str(e)}")
        
        return redirect('core:semestre1_importation')
    
    context = {
        'etablissement': etablissement,
        'classes': classes,
        'imports': imports,
    }
    
    return render(request, 'core/semestre1/importation.html', context)

def semestre1_importation_detail(request, import_id):
    """
    Vue pour afficher les détails d'une importation spécifique
    """
    import_fichier = get_object_or_404(ImportFichier, id=import_id)
    moyennes = MoyenneEleve.objects.filter(import_fichier=import_fichier)
    
    # Récupérer les données originales du fichier Excel importé
    excel_data = None
    if import_fichier.fichier:
        try:
            import pandas as pd
            xls = pd.ExcelFile(import_fichier.fichier.path)
            
            # Lecture de l'onglet "Moyennes eleves"
            df_moyennes = pd.read_excel(xls, sheet_name="Moyennes eleves", skiprows=range(11), header=0)
            
            # Lecture de l'onglet "Données détaillées"
            df_detail = pd.read_excel(xls, sheet_name="Données détaillées", skiprows=range(8), header=[0, 1])
            
            # Traitement pour Données détaillées
            disciplines = df_detail.columns.get_level_values(0).tolist()
            sous_colonnes = df_detail.columns.get_level_values(1).tolist()
            
            for i in range(len(disciplines)):
                if "Unnamed" in disciplines[i]:  
                    disciplines[i] = disciplines[i - 1]
            
            info_colonnes = df_detail.iloc[:, :3]
            info_colonnes.columns = [col[0] for col in info_colonnes.columns]
            
            colonnes_moy_d = [i for i, col in enumerate(sous_colonnes) if col == "Moy D"]
            df_detail_moy_d = df_detail.iloc[:, colonnes_moy_d]
            noms_moy_d = [disciplines[i] for i in colonnes_moy_d]
            df_detail_moy_d.columns = noms_moy_d
            
            df_final = pd.concat([info_colonnes, df_detail_moy_d], axis=1)
            
            # Convertir en dictionnaires pour le template
            moyennes_data = df_moyennes.fillna('').to_dict('records')
            details_data = df_final.fillna('').to_dict('records')
            
            # Récupérer les noms des colonnes pour l'affichage
            moyennes_colonnes = df_moyennes.columns.tolist()
            details_colonnes = df_final.columns.tolist()
            
            excel_data = {
                'moyennes': {
                    'data': moyennes_data,
                    'colonnes': moyennes_colonnes
                },
                'details': {
                    'data': details_data,
                    'colonnes': details_colonnes
                }
            }
            
        except Exception as e:
            print(f"Erreur lors de la lecture du fichier Excel: {e}")
    
    context = {
        'import': import_fichier,
        'moyennes_eleves': moyennes,
        'excel_data': excel_data,
        'active_tab': request.GET.get('tab', 'moyennes')  # Pour gérer l'onglet actif
    }
    
    return render(request, 'core/semestre1/importation_detail.html', context)

def semestre1_importation_delete(request, import_id):
    """
    Vue pour supprimer une importation
    """
    import_fichier = get_object_or_404(ImportFichier, id=import_id)
    
    if request.method == 'POST':
        # Supprimer d'abord les moyennes et disciplines associées
        moyennes = MoyenneEleve.objects.filter(import_fichier=import_fichier)
        for moyenne in moyennes:
            MoyenneDiscipline.objects.filter(eleve=moyenne).delete()
        
        moyennes.delete()
        import_fichier.delete()
        
        messages.success(request, "L'importation a été supprimée avec succès.")
        return redirect('core:semestre1_importation')
    
    context = {
        'import': import_fichier,
    }
    
    return render(request, 'core/semestre1/importation_delete.html', context)