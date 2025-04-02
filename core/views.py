from django.shortcuts import render, redirect
from django.contrib import messages
import pandas as pd
from .models import Etablissement, InspectionAcademique, Niveau, Classe, ImportFichier, MoyenneEleve, MoyenneDiscipline, DonneesMoyennesEleves, DonneesDetailleesEleves
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
            import json
            
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
            
            # Vérifier si les colonnes nécessaires sont présentes dans info_colonnes
            required_columns = ['Nom']
            missing_columns = [col for col in required_columns if col not in info_colonnes.columns]
            
            if missing_columns:
                raise ValueError(f"Colonnes manquantes dans le fichier: {', '.join(missing_columns)}")
            
            # Vérifier si la colonne 'Prénom' existe, sinon créer une colonne vide
            if 'Prénom' not in info_colonnes.columns:
                info_colonnes['Prénom'] = None
                
            # --- 5) Sélectionner uniquement les colonnes "Moy D" et récupérer leurs positions
            colonnes_moy_d = [i for i, col in enumerate(sous_colonnes) if col == "Moy D"]
            df_detail_moy_d = df_detail.iloc[:, colonnes_moy_d]
            noms_moy_d = [disciplines[i] for i in colonnes_moy_d]
            df_detail_moy_d.columns = noms_moy_d
            
            # --- 6) Fusionner les infos élèves avec les moyennes "Moy D"
            df_final = pd.concat([info_colonnes, df_detail_moy_d], axis=1)
            
            # --- 7) NOUVEAU: Stockage des données complètes dans la base de données
            # Stocker les données du tableau "Moyennes eleves"
            for _, row in df_moyennes.iterrows():
                # Sélectionner les colonnes connues
                nom = str(row.get('Nom', ''))
                prenom = str(row.get('Prénom', '')) if pd.notna(row.get('Prénom')) else None
                classe_nom = str(row.get('Classe', '')) if pd.notna(row.get('Classe')) else None
                
                # Chercher la moyenne générale dans différentes colonnes possibles
                moyenne_generale = None
                for col in ['Moyenne Générale', 'Moyenne générale', 'Moyenne Generale', 'Moyenne', 'Moy Gen']:
                    if col in df_moyennes.columns and pd.notna(row.get(col)):
                        moyenne_generale = float(row.get(col))
                        break
                
                # Chercher le rang
                # Dans la partie où vous cherchez le rang et l'effectif
                # Chercher le rang
                rang = None
                for col in ['Rang', 'rang', 'Rang Classe', 'rang classe']:
                    if col in df_moyennes.columns and pd.notna(row.get(col)):
                        try:
                            # Essayer de convertir en entier directement
                            rang = int(row.get(col))
                        except ValueError:
                            # Si échec, essayer d'extraire seulement les chiffres
                            import re
                            chiffres = re.findall(r'\d+', str(row.get(col)))
                            if chiffres:
                                rang = int(chiffres[0])  # Prendre le premier groupe de chiffres
                        break

                # Chercher l'effectif
                effectif = None
                for col in ['Effectif', 'effectif', 'Effectif Classe', 'effectif classe']:
                    if col in df_moyennes.columns and pd.notna(row.get(col)):
                        try:
                            # Essayer de convertir en entier directement
                            effectif = int(row.get(col))
                        except ValueError:
                            # Si échec, essayer d'extraire seulement les chiffres
                            import re
                            chiffres = re.findall(r'\d+', str(row.get(col)))
                            if chiffres:
                                effectif = int(chiffres[0])  # Prendre le premier groupe de chiffres
                        break
                
                # Créer un dictionnaire avec toutes les autres colonnes
                donnees_additionnelles = {}
                for col in df_moyennes.columns:
                    if col not in ['Nom', 'Prénom', 'Classe', 'Moyenne Générale', 'Moyenne générale', 
                                  'Rang', 'rang', 'Rang Classe', 'rang classe', 
                                  'Effectif', 'effectif', 'Effectif Classe', 'effectif classe']:
                        if pd.notna(row.get(col)):
                            # Convertir les types numpy en types Python natifs pour JSON
                            val = row.get(col)
                            if hasattr(val, 'item'):  # Pour les types numpy
                                val = val.item()
                            donnees_additionnelles[col] = val
                
                # Sauvegarder dans la base de données
                if nom:  # S'assurer qu'il y a un nom
                    DonneesMoyennesEleves.objects.create(
                        import_fichier=import_fichier,
                        nom=nom,
                        prenom=prenom,
                        classe=classe_nom,
                        moyenne_generale=moyenne_generale,
                        rang_classe=rang,
                        effectif_classe=effectif,
                        donnees_additionnelles=donnees_additionnelles
                    )
            
            # Stocker les données du tableau "Données détaillées"
            for _, row in df_final.iterrows():
                nom = str(row.get('Nom', ''))
                prenom = str(row.get('Prénom', '')) if pd.notna(row.get('Prénom')) else None
                classe_nom = str(row.get('Classe', '')) if pd.notna(row.get('Classe')) else None
                
                # Créer un dictionnaire pour les disciplines
                disciplines_dict = {}
                for col in df_final.columns:
                    if col not in ['Nom', 'Prénom', 'Classe']:
                        if pd.notna(row.get(col)):
                            val = row.get(col)
                            if hasattr(val, 'item'):  # Pour les types numpy
                                val = val.item()
                            disciplines_dict[col] = val
                
                # Sauvegarder dans la base de données
                if nom:  # S'assurer qu'il y a un nom
                    DonneesDetailleesEleves.objects.create(
                        import_fichier=import_fichier,
                        nom=nom,
                        prenom=prenom,
                        classe=classe_nom,
                        disciplines=disciplines_dict
                    )
            
            # Continuer avec le code existant pour MoyenneEleve et MoyenneDiscipline
            if classe_id:
                classe = Classe.objects.get(id=classe_id)
                
                # Parcourir les données nettoyées et créer des enregistrements
                for index, row in df_final.iterrows():
                    nom = str(row.get('Nom', ''))
                    prenom = str(row.get('Prénom', '')) if pd.notna(row.get('Prénom')) else None
                    
                    if nom:  # S'assurer qu'il y a un nom avant de créer un enregistrement
                        # Chercher la moyenne générale dans les données stockées
                        moyenne_generale = 0
                        
                        # Chercher dans les DonneesMoyennesEleves
                        if prenom:
                            donnees_eleve = DonneesMoyennesEleves.objects.filter(
                                import_fichier=import_fichier, 
                                nom=nom, 
                                prenom=prenom
                            ).first()
                        else:
                            donnees_eleve = DonneesMoyennesEleves.objects.filter(
                                import_fichier=import_fichier, 
                                nom=nom
                            ).first()
                        
                        if donnees_eleve and donnees_eleve.moyenne_generale:
                            moyenne_generale = donnees_eleve.moyenne_generale
                        else:
                            # Calculer la moyenne générale à partir des moyennes par discipline
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
                
                # Calculer et mettre à jour les rangs
                # Trier les élèves par moyenne décroissante
                eleves_tries = MoyenneEleve.objects.filter(import_fichier=import_fichier, classe=classe).order_by('-moyenne_generale')
                for i, eleve in enumerate(eleves_tries):
                    eleve.rang = i + 1
                    eleve.save()
            
            import_fichier.statut = 'termine'
            import_fichier.save()
            messages.success(request, "Le fichier a été importé et nettoyé avec succès.")
            
        except Exception as e:
            import_fichier.statut = 'erreur'
            import_fichier.erreur_message = str(e)
            import_fichier.save()
            messages.error(request, f"Une erreur s'est produite lors de l'importation : {str(e)}")
            
            # Log plus détaillé pour le débogage
            import traceback
            print(traceback.format_exc())
        
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
        if request.POST.get('confirmer_suppression'):
            # Supprimer les données stockées
            DonneesMoyennesEleves.objects.filter(import_fichier=import_fichier).delete()
            DonneesDetailleesEleves.objects.filter(import_fichier=import_fichier).delete()
            
            # Récupérer d'abord toutes les moyennes associées
            moyennes = MoyenneEleve.objects.filter(import_fichier=import_fichier)
            
            # Pour chaque moyenne, supprimer les disciplines associées
            for moyenne in moyennes:
                MoyenneDiscipline.objects.filter(eleve=moyenne).delete()
            
            # Supprimer les moyennes
            moyennes.delete()
            
            # Essayer de supprimer le fichier physique s'il existe
            if import_fichier.fichier and hasattr(import_fichier.fichier, 'path'):
                import os
                try:
                    if os.path.isfile(import_fichier.fichier.path):
                        os.remove(import_fichier.fichier.path)
                except (PermissionError, OSError) as e:
                    # Journaliser l'erreur mais continuer
                    print(f"Impossible de supprimer le fichier {import_fichier.fichier.path}: {e}")
                    messages.warning(request, f"Le fichier physique n'a pas pu être supprimé (il est peut-être ouvert dans une autre application), mais les données ont bien été effacées de la base.")
            
            # Supprimer l'enregistrement
            import_fichier.delete()
            
            messages.success(request, "L'importation a été supprimée avec succès.")
            return redirect('core:semestre1_importation')
    
    context = {
        'import': import_fichier,
    }
    
    return render(request, 'core/semestre1/importation_delete.html', context)

def semestre1_analyse_moyennes(request):
    """
    Vue pour l'analyse des moyennes du Semestre 1, basée uniquement sur l'onglet 'Moyennes eleves'
    """
    # Récupérer l'établissement et l'année scolaire active
    etablissement = Etablissement.objects.first()
    annee_scolaire = etablissement.annee_scolaire_active if etablissement else "2024-2025"
    
    # Récupérer toutes les classes et niveaux pour les filtres
    classes = Classe.objects.filter(annee_scolaire=annee_scolaire)
    niveaux = Niveau.objects.all()
    
    # Récupérer tous les imports terminés pour le semestre 1
    imports = ImportFichier.objects.filter(
        semestre=1, 
        annee_scolaire=annee_scolaire,
        statut='termine'
    )
    
    # Filtres
    classe_id = request.GET.get('classe')
    niveau_id = request.GET.get('niveau')
    import_id = request.GET.get('import')
    
    # Récupérer les données de "Moyennes eleves" stockées
    donnees_moyennes_query = DonneesMoyennesEleves.objects.filter(
        import_fichier__semestre=1,
        import_fichier__annee_scolaire=annee_scolaire,
        import_fichier__statut='termine'
    )
    
    # Appliquer les filtres
    if import_id:
        donnees_moyennes_query = donnees_moyennes_query.filter(import_fichier_id=import_id)
    
    # Construire la requête MoyenneEleve (pour avoir le lien avec la classe)
    moyennes_query = MoyenneEleve.objects.filter(
        import_fichier__semestre=1,
        import_fichier__annee_scolaire=annee_scolaire,
        import_fichier__statut='termine'
    ).select_related('classe', 'import_fichier')
    
    if classe_id:
        moyennes_query = moyennes_query.filter(classe_id=classe_id)
        # Filtrer donnees_moyennes par correspondance de noms
        noms_eleves = moyennes_query.values_list('nom_eleve', flat=True)
        donnees_moyennes_query = donnees_moyennes_query.filter(nom__in=noms_eleves)
    
    if niveau_id:
        moyennes_query = moyennes_query.filter(classe__niveau_id=niveau_id)
        # Filtrer donnees_moyennes par correspondance de noms
        noms_eleves = moyennes_query.values_list('nom_eleve', flat=True)
        donnees_moyennes_query = donnees_moyennes_query.filter(nom__in=noms_eleves)
    
    if import_id:
        moyennes_query = moyennes_query.filter(import_fichier_id=import_id)
    
    # Ordonner les résultats
    moyennes = moyennes_query.order_by('-moyenne_generale')
    donnees_moyennes = list(donnees_moyennes_query)
    
    # Statistiques générales
    stats = {}
    
    if donnees_moyennes:
        from django.db.models import Avg, Min, Max, Count, Sum, Q
        import pandas as pd
        import json
        
        # 1. Statistiques de base
        total_eleves = len(donnees_moyennes)
        stats['nb_eleves'] = total_eleves
        
        # Calculer le nombre par sexe (si disponible)
        stats['sexe'] = {
            'M': 0,
            'F': 0,
            'non_precise': 0
        }
        
        # Calculer les moyennes
        moyennes_values = [d.moyenne_generale for d in donnees_moyennes if d.moyenne_generale is not None]
        if moyennes_values:
            stats['moyenne_globale'] = sum(moyennes_values) / len(moyennes_values)
            stats['min_moyenne'] = min(moyennes_values)
            stats['max_moyenne'] = max(moyennes_values)
        else:
            stats['moyenne_globale'] = 0
            stats['min_moyenne'] = 0
            stats['max_moyenne'] = 0
        
        # 2. Répartition des moyennes
        repartition = {
            'excellence': 0,
            'tres_bien': 0,
            'bien': 0,
            'assez_bien': 0,
            'passable': 0,
            'insuffisant': 0
        }
        
        for d in donnees_moyennes:
            if d.moyenne_generale is not None:
                if d.moyenne_generale >= 16:
                    repartition['excellence'] += 1
                elif d.moyenne_generale >= 14:
                    repartition['tres_bien'] += 1
                elif d.moyenne_generale >= 12:
                    repartition['bien'] += 1
                elif d.moyenne_generale >= 10:
                    repartition['assez_bien'] += 1
                elif d.moyenne_generale >= 8:
                    repartition['passable'] += 1
                else:
                    repartition['insuffisant'] += 1
        
        stats['repartition'] = repartition
        
        # Calculer les pourcentages pour les barres de progression
        pourcentages = {}
        if total_eleves > 0:
            for categorie, nombre in repartition.items():
                pourcentages[categorie] = (nombre / total_eleves) * 100
        else:
            pourcentages = {k: 0 for k in repartition.keys()}
        
        stats['pourcentages'] = pourcentages
        
        # 3. Taux de réussite
        eleves_reussite = sum(1 for d in donnees_moyennes if d.moyenne_generale is not None and d.moyenne_generale >= 10)
        stats['taux_reussite'] = {
            'nombre': eleves_reussite,
            'pourcentage': (eleves_reussite / total_eleves * 100) if total_eleves > 0 else 0
        }
        
        # 4. Extraire les informations supplémentaires des données
        # (absences, retards, appréciations, etc.)
        stats['absences'] = {
            'total': 0,
            'moyenne': 0
        }
        
        stats['retards'] = {
            'total': 0,
            'moyenne': 0
        }
        
        stats['appreciations'] = {}
        stats['decisions'] = {}
        
        for d in donnees_moyennes:
            if d.donnees_additionnelles:
                # Chercher les absences
                for key in ['Absences', 'absences', 'Abs', 'abs', 'Heures absences', 'Total absences']:
                    if key in d.donnees_additionnelles:
                        try:
                            abs_val = float(d.donnees_additionnelles[key])
                            stats['absences']['total'] += abs_val
                        except (ValueError, TypeError):
                            pass
                
                # Chercher les retards
                for key in ['Retards', 'retards', 'Ret', 'ret', 'Total retards']:
                    if key in d.donnees_additionnelles:
                        try:
                            ret_val = float(d.donnees_additionnelles[key])
                            stats['retards']['total'] += ret_val
                        except (ValueError, TypeError):
                            pass
                
                # Chercher les appréciations
                for key in ['Appréciation', 'Appreciation', 'appreciation', 'Mention', 'mention']:
                    if key in d.donnees_additionnelles:
                        appreciation = str(d.donnees_additionnelles[key])
                        if appreciation:
                            stats['appreciations'][appreciation] = stats['appreciations'].get(appreciation, 0) + 1
                
                # Chercher les décisions du conseil
                for key in ['Décision', 'Decision', 'decision', 'Conseil', 'conseil', 'Avis']:
                    if key in d.donnees_additionnelles:
                        decision = str(d.donnees_additionnelles[key])
                        if decision:
                            stats['decisions'][decision] = stats['decisions'].get(decision, 0) + 1
                
                # Chercher le sexe
                for key in ['Sexe', 'sexe', 'Genre', 'genre']:
                    if key in d.donnees_additionnelles:
                        sexe = str(d.donnees_additionnelles[key]).upper()
                        if sexe == 'M' or sexe == 'MASCULIN' or sexe == 'H':
                            stats['sexe']['M'] += 1
                        elif sexe == 'F' or sexe == 'FEMININ' or sexe == 'FÉMININ':
                            stats['sexe']['F'] += 1
                        else:
                            stats['sexe']['non_precise'] += 1
        
        # Calculer les moyennes d'absences et retards
        if total_eleves > 0:
            stats['absences']['moyenne'] = stats['absences']['total'] / total_eleves
            stats['retards']['moyenne'] = stats['retards']['total'] / total_eleves
        
        # 5. Données pour les graphiques
        # Moyenne par niveau (si applicable)
        if niveau_id is None:
            moyennes_par_niveau = {}
            niveaux_dict = {n.id: n.nom for n in niveaux}
            
            for eleve in moyennes:
                niveau_id = eleve.classe.niveau.id
                niveau_nom = niveaux_dict.get(niveau_id, "Non défini")
                
                if niveau_nom not in moyennes_par_niveau:
                    moyennes_par_niveau[niveau_nom] = {'somme': 0, 'count': 0}
                
                moyennes_par_niveau[niveau_nom]['somme'] += eleve.moyenne_generale
                moyennes_par_niveau[niveau_nom]['count'] += 1
            
            stats['moyennes_par_niveau'] = {
                'labels': [],
                'data': []
            }
            
            for niveau, values in moyennes_par_niveau.items():
                stats['moyennes_par_niveau']['labels'].append(niveau)
                moy = values['somme'] / values['count'] if values['count'] > 0 else 0
                stats['moyennes_par_niveau']['data'].append(round(moy, 2))
        
        # 6. Top 5 des élèves
        stats['top_eleves'] = moyennes[:5]
    
    context = {
        'etablissement': etablissement,
        'classes': classes,
        'niveaux': niveaux,
        'imports': imports,
        'moyennes': moyennes,
        'stats': stats,
        'selected_classe': classe_id,
        'selected_niveau': niveau_id,
        'selected_import': import_id,
    }
    
    return render(request, 'core/semestre1/analyse_moyennes.html', context)

def niveau_delete(request, niveau_id):
    """
    Vue pour supprimer un niveau
    """
    niveau = get_object_or_404(Niveau, id=niveau_id)
    
    # Vérifier si des classes sont associées à ce niveau
    classes_associees = Classe.objects.filter(niveau=niveau)
    
    if request.method == 'POST':
        if classes_associees.exists() and not request.POST.get('confirmer_suppression_classes'):
            messages.warning(request, 
                f"Ce niveau contient {classes_associees.count()} classe(s). Veuillez confirmer la suppression de toutes les classes associées.")
            return render(request, 'core/niveau_delete.html', {
                'niveau': niveau,
                'classes_associees': classes_associees,
                'confirmation_requise': True
            })
        else:
            # Supprimer les classes associées si confirmation
            classes_associees.delete()
            # Supprimer le niveau
            niveau.delete()
            messages.success(request, f"Le niveau '{niveau.nom}' a été supprimé avec succès.")
            request.session['active_tab'] = 'niveaux'
            return redirect('core:configuration')
    
    return render(request, 'core/niveau_delete.html', {
        'niveau': niveau,
        'classes_associees': classes_associees
    })

def classe_delete(request, classe_id):
    """
    Vue pour supprimer une classe
    """
    classe = get_object_or_404(Classe, id=classe_id)
    
    # Vérifier si des élèves (moyennes) sont associés à cette classe
    moyennes_associees = MoyenneEleve.objects.filter(classe=classe)
    
    if request.method == 'POST':
        if moyennes_associees.exists() and not request.POST.get('confirmer_suppression_moyennes'):
            messages.warning(request, 
                f"Cette classe contient des données pour {moyennes_associees.count()} élève(s). Veuillez confirmer la suppression de toutes les données associées.")
            return render(request, 'core/classe_delete.html', {
                'classe': classe,
                'moyennes_count': moyennes_associees.count(),
                'confirmation_requise': True
            })
        else:
            # Supprimer les moyennes et disciplines associées
            for moyenne in moyennes_associees:
                MoyenneDiscipline.objects.filter(eleve=moyenne).delete()
            moyennes_associees.delete()
            
            # Supprimer la classe
            classe.delete()
            messages.success(request, f"La classe '{classe.nom}' a été supprimée avec succès.")
            request.session['active_tab'] = 'classes'
            return redirect('core:configuration')
    
    return render(request, 'core/classe_delete.html', {
        'classe': classe,
        'moyennes_count': moyennes_associees.count()
    })