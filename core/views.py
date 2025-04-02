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
            
            # Récupérer la classe sélectionnée si une est choisie
            classe_selectionnee = None
            niveau_selectionne = None
            if classe_id:
                classe_selectionnee = Classe.objects.get(id=classe_id)
                niveau_selectionne = classe_selectionnee.niveau
            
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
            
            # --- 7) Stocker les données du tableau "Moyennes eleves"
            for _, row in df_moyennes.iterrows():
                # Sélectionner les colonnes connues
                nom = str(row.get('Nom', ''))
                prenom = str(row.get('Prénom', '')) if pd.notna(row.get('Prénom')) else None
                classe_nom = str(row.get('Classe', '')) if pd.notna(row.get('Classe')) else None
                
                # Chercher la moyenne générale dans différentes colonnes possibles
                moyenne_generale = None
                for col in ['Moyenne Générale', 'Moyenne générale', 'Moyenne Generale', 'Moyenne', 'Moy Gen', 'Moy']:
                    if col in df_moyennes.columns and pd.notna(row.get(col)):
                        try:
                            # Conserver la valeur exacte
                            moyenne_generale = float(row.get(col))
                            break
                        except (ValueError, TypeError) as e:
                            pass
                
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
                                rang = int(chiffres[0])
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
                                effectif = int(chiffres[0])
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

                # IMPORTANT: Trouver la classe correspondante dans la base de données
                classe_obj = None
                niveau_obj = None
                
                # Si classe_selectionnee existe, l'utiliser directement
                if classe_selectionnee:
                    classe_obj = classe_selectionnee
                    niveau_obj = niveau_selectionne
                # Sinon, chercher parmi les classes existantes
                elif classe_nom:
                    for c in classes:
                        if c.nom.lower() in classe_nom.lower() or classe_nom.lower() in c.nom.lower():
                            classe_obj = c
                            niveau_obj = c.niveau
                            break
                
                # Sauvegarder dans la base de données
                if nom:  # S'assurer qu'il y a un nom
                    DonneesMoyennesEleves.objects.create(
                        import_fichier=import_fichier,
                        nom=nom,
                        prenom=prenom,
                        classe_texte=classe_nom,
                        classe_obj=classe_obj,
                        niveau=niveau_obj,
                        moyenne_generale=moyenne_generale,
                        rang_classe=rang,
                        effectif_classe=effectif,
                        donnees_additionnelles=donnees_additionnelles
                    )
            
            # --- 8) Stocker les données du tableau "Données détaillées"
            # Extraire les noms des disciplines
            discipline_colonnes = []
            for col in df_detail.columns:
                # Vérifier si la colonne de deuxième niveau est "Moy D"
                if col[1] == "Moy D":
                    discipline_colonnes.append(col[0])
            
            for _, row in df_final.iterrows():
                nom = str(row.get('Nom', ''))
                prenom = str(row.get('Prénom', '')) if pd.notna(row.get('Prénom')) else None
                classe_nom = str(row.get('Classe', '')) if pd.notna(row.get('Classe')) else None
                
                # Créer un dictionnaire pour les disciplines
                disciplines_dict = {}
                
                # Ajouter les moyennes des disciplines
                for discipline in discipline_colonnes:
                    # Clé avec le nom de la discipline et suffixe "Moy D"
                    moy_key = f"{discipline} Moy D"
                    
                    # Trouver la valeur de la moyenne
                    moy_value = row.get((discipline, "Moy D"))
                    
                    # Ajouter au dictionnaire si la valeur existe
                    if pd.notna(moy_value):
                        disciplines_dict[moy_key] = moy_value
                    
                    # Ajouter d'autres colonnes pour cette discipline
                    for sous_col in df_detail.columns.get_level_values(1).unique():
                        if sous_col != "Moy D":
                            detail_key = f"{discipline} {sous_col}"
                            detail_value = row.get((discipline, sous_col))
                            
                            if pd.notna(detail_value):
                                disciplines_dict[detail_key] = detail_value
                
                # Ajouter des informations supplémentaires de la première section
                for col in info_colonnes.columns:
                    if pd.notna(row.get(col)):
                        disciplines_dict[col] = row.get(col)
                
                # Sauvegarder dans la base de données
                if nom:  # S'assurer qu'il y a un nom
                    DonneesDetailleesEleves.objects.create(
                        import_fichier=import_fichier,
                        nom=nom,
                        prenom=prenom,
                        classe=classe_nom,
                        disciplines=disciplines_dict
                    )
            
            # Terminer l'importation
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
    sexe = request.GET.get('sexe')
    intervalle = request.GET.get('intervalle')
    
    # Base de requête pour les données de moyenne
    donnees_moyennes_query = DonneesMoyennesEleves.objects.filter(
        import_fichier__semestre=1,
        import_fichier__annee_scolaire=annee_scolaire,
        import_fichier__statut='termine'
    )
    
    # Appliquer les filtres
    if import_id:
        donnees_moyennes_query = donnees_moyennes_query.filter(import_fichier_id=import_id)
    
    if classe_id:
        donnees_moyennes_query = donnees_moyennes_query.filter(classe_obj_id=classe_id)
    
    if niveau_id:
        donnees_moyennes_query = donnees_moyennes_query.filter(niveau_id=niveau_id)
    
    # Filtrer par sexe
    if sexe:
        from django.db.models import Q
        sexe_filter = Q()
        
        if sexe == 'M':
            # Chercher les valeurs qui commencent par M ou H
            sexe_filter |= Q(donnees_additionnelles__Sexe__istartswith='M')
            sexe_filter |= Q(donnees_additionnelles__Sexe__istartswith='H')
            sexe_filter |= Q(donnees_additionnelles__sexe__istartswith='M')
            sexe_filter |= Q(donnees_additionnelles__sexe__istartswith='H')
            sexe_filter |= Q(donnees_additionnelles__Genre__istartswith='M')
            sexe_filter |= Q(donnees_additionnelles__Genre__istartswith='H')
        else:  # sexe == 'F'
            # Pour féminin, chercher les valeurs qui commencent par F
            sexe_filter |= Q(donnees_additionnelles__Sexe__istartswith='F')
            sexe_filter |= Q(donnees_additionnelles__sexe__istartswith='F')
            sexe_filter |= Q(donnees_additionnelles__Genre__istartswith='F')
        
        donnees_moyennes_query = donnees_moyennes_query.filter(sexe_filter)
    
    # Initialiser donnees_moyennes comme une liste vide par défaut
    donnees_moyennes = []
    
    # Convertir en liste uniquement si des résultats existent
    if donnees_moyennes_query.exists():
        donnees_moyennes = list(donnees_moyennes_query)
    
    # Filtre par intervalle de moyenne
    if intervalle and donnees_moyennes:
        filtered_by_interval = []
        for d in donnees_moyennes:
            if d.moyenne_generale is not None:
                try:
                    moyenne = float(d.moyenne_generale)
                    if intervalle == 'excellence' and moyenne >= 16:
                        filtered_by_interval.append(d)
                    elif intervalle == 'tres_bien' and 14 <= moyenne < 16:
                        filtered_by_interval.append(d)
                    elif intervalle == 'bien' and 12 <= moyenne < 14:
                        filtered_by_interval.append(d)
                    elif intervalle == 'assez_bien' and 10 <= moyenne < 12:
                        filtered_by_interval.append(d)
                    elif intervalle == 'passable' and 8 <= moyenne < 10:
                        filtered_by_interval.append(d)
                    elif intervalle == 'insuffisant' and moyenne < 8:
                        filtered_by_interval.append(d)
                except (ValueError, TypeError):
                    pass
        
        donnees_moyennes = filtered_by_interval
    
    # Trier par moyenne générale décroissante
    donnees_moyennes.sort(
        key=lambda x: float(x.moyenne_generale) if x.moyenne_generale is not None else 0,
        reverse=True
    )
    
    # Statistiques générales
    stats = {}
    
    if donnees_moyennes:
        # 1. Statistiques de base
        total_eleves = len(donnees_moyennes)
        stats['nb_eleves'] = total_eleves
        
        # Compter par sexe
        stats['sexe'] = {'M': 0, 'F': 0, 'non_precise': 0}
        
        for d in donnees_moyennes:
            sexe_trouve = False
            if d.donnees_additionnelles:
                for key in ['Sexe', 'sexe', 'Genre', 'genre']:
                    if key in d.donnees_additionnelles:
                        valeur = str(d.donnees_additionnelles[key]).upper()
                        if valeur.startswith('M') or valeur.startswith('H'):
                            stats['sexe']['M'] += 1
                            sexe_trouve = True
                            break
                        elif valeur.startswith('F'):
                            stats['sexe']['F'] += 1
                            sexe_trouve = True
                            break
            
            if not sexe_trouve:
                stats['sexe']['non_precise'] += 1
        
        # 2. Moyennes
        moyennes_values = []
        for d in donnees_moyennes:
            if d.moyenne_generale is not None:
                try:
                    moyennes_values.append(float(d.moyenne_generale))
                except (ValueError, TypeError):
                    pass
        
        if moyennes_values:
            stats['moyenne_globale'] = sum(moyennes_values) / len(moyennes_values)
            stats['min_moyenne'] = min(moyennes_values)
            stats['max_moyenne'] = max(moyennes_values)
        else:
            stats['moyenne_globale'] = 0
            stats['min_moyenne'] = 0
            stats['max_moyenne'] = 0
        
        # 3. Répartition des moyennes
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
                try:
                    moyenne = float(d.moyenne_generale)
                    if moyenne >= 16:
                        repartition['excellence'] += 1
                    elif moyenne >= 14:
                        repartition['tres_bien'] += 1
                    elif moyenne >= 12:
                        repartition['bien'] += 1
                    elif moyenne >= 10:
                        repartition['assez_bien'] += 1
                    elif moyenne >= 8:
                        repartition['passable'] += 1
                    else:
                        repartition['insuffisant'] += 1
                except (ValueError, TypeError):
                    pass
        
        stats['repartition'] = repartition
        
        # Calcul des pourcentages
        pourcentages = {}
        if total_eleves > 0:
            for categorie, nombre in repartition.items():
                pourcentages[categorie] = (nombre / total_eleves) * 100
        else:
            pourcentages = {k: 0 for k in repartition.keys()}
        
        stats['pourcentages'] = pourcentages
        
        # 4. Taux de réussite
        eleves_reussite = {'total': 0, 'par_sexe': {'M': 0, 'F': 0}}
        
        for d in donnees_moyennes:
            if d.moyenne_generale is not None:
                try:
                    if float(d.moyenne_generale) >= 10:
                        eleves_reussite['total'] += 1
                        
                        # Répartition par sexe
                        if d.donnees_additionnelles:
                            for key in ['Sexe', 'sexe', 'Genre', 'genre']:
                                if key in d.donnees_additionnelles:
                                    valeur = str(d.donnees_additionnelles[key]).upper()
                                    if valeur.startswith('M') or valeur.startswith('H'):
                                        eleves_reussite['par_sexe']['M'] += 1
                                        break
                                    elif valeur.startswith('F'):
                                        eleves_reussite['par_sexe']['F'] += 1
                                        break
                except (ValueError, TypeError):
                    pass
        
        stats['taux_reussite'] = {
            'nombre': eleves_reussite['total'],
            'pourcentage': (eleves_reussite['total'] / total_eleves * 100) if total_eleves > 0 else 0,
            'par_sexe': eleves_reussite['par_sexe']
        }
        
        # 5. Extraire informations supplémentaires
        stats['absences'] = {'total': 0, 'moyenne': 0, 'max': 0}
        stats['retards'] = {'total': 0, 'moyenne': 0, 'max': 0}
        stats['appreciations'] = {}
        stats['decisions'] = {}
        
        for d in donnees_moyennes:
            if d.donnees_additionnelles:
                # Chercher absences
                for key in ['Absences', 'absences', 'Absence', 'absence']:
                    if key in d.donnees_additionnelles and d.donnees_additionnelles[key]:
                        try:
                            val = str(d.donnees_additionnelles[key])
                            # Pour le format "Abs: 4 Jstf: 0"
                            if 'Abs:' in val:
                                parts = val.split('Abs:')
                                if len(parts) > 1:
                                    abs_part = parts[1].strip().split()[0]
                                    abs_val = float(abs_part)
                                    stats['absences']['total'] += abs_val
                                    stats['absences']['max'] = max(stats['absences']['max'], abs_val)
                            else:
                                abs_val = float(val)
                                stats['absences']['total'] += abs_val
                                stats['absences']['max'] = max(stats['absences']['max'], abs_val)
                        except (ValueError, TypeError):
                            pass
                
                # Chercher retards
                for key in ['Retards', 'retards', 'Retard', 'retard']:
                    if key in d.donnees_additionnelles and d.donnees_additionnelles[key]:
                        try:
                            val = d.donnees_additionnelles[key]
                            # Pour le format "0h 0mn"
                            if isinstance(val, str) and 'h' in val:
                                parts = val.split('h')
                                hours = int(parts[0])
                                minutes = 0
                                if len(parts) > 1 and 'mn' in parts[1]:
                                    try:
                                        minutes = int(parts[1].split('mn')[0])
                                    except ValueError:
                                        pass
                                # Convertir en minutes
                                ret_val = hours * 60 + minutes
                                if ret_val > 0:  # Ne compter que si > 0
                                    stats['retards']['total'] += 1
                                    stats['retards']['max'] = max(stats['retards']['max'], 1)
                            else:
                                ret_val = float(val) if not isinstance(val, str) else 1
                                stats['retards']['total'] += ret_val
                                stats['retards']['max'] = max(stats['retards']['max'], ret_val)
                        except (ValueError, TypeError):
                            pass
                
                # Chercher appréciations
                for key in ['Appréciation', 'Appreciation', 'appreciation']:
                    if key in d.donnees_additionnelles and d.donnees_additionnelles[key]:
                        appreciation = str(d.donnees_additionnelles[key])
                        stats['appreciations'][appreciation] = stats['appreciations'].get(appreciation, 0) + 1
                
                # Chercher décisions du conseil
                for key in ['Décision conseil', 'Décision du conseil', 'Décision', 'Decision']:
                    if key in d.donnees_additionnelles and d.donnees_additionnelles[key]:
                        decision = str(d.donnees_additionnelles[key])
                        stats['decisions'][decision] = stats['decisions'].get(decision, 0) + 1
        
        # Calculer moyennes d'absences et retards
        if total_eleves > 0:
            stats['absences']['moyenne'] = stats['absences']['total'] / total_eleves
            stats['retards']['moyenne'] = stats['retards']['total'] / total_eleves
        
        # 6. Moyennes par niveau (utiliser les relations directes maintenant)
        moyennes_par_niveau = {}
        
        # Regrouper par niveau
        for d in donnees_moyennes:
            if d.niveau and d.moyenne_generale is not None:
                niveau_nom = d.niveau.nom
                
                if niveau_nom not in moyennes_par_niveau:
                    moyennes_par_niveau[niveau_nom] = {'somme': 0, 'count': 0}
                
                try:
                    moyenne = float(d.moyenne_generale)
                    moyennes_par_niveau[niveau_nom]['somme'] += moyenne
                    moyennes_par_niveau[niveau_nom]['count'] += 1
                except (ValueError, TypeError):
                    pass
        
        stats['moyennes_par_niveau'] = {
            'labels': [],
            'data': []
        }
        
        for niveau, values in moyennes_par_niveau.items():
            if values['count'] > 0:
                stats['moyennes_par_niveau']['labels'].append(niveau)
                moy = values['somme'] / values['count']
                stats['moyennes_par_niveau']['data'].append(round(moy, 2))
        
        # 7. Top 5 des élèves
        top_eleves = donnees_moyennes[:5] if len(donnees_moyennes) >= 5 else donnees_moyennes

        # Ajouter rang pour affichage
        for i, d in enumerate(top_eleves):
            d.rang = i + 1
            
            # Debug pour voir ce qu'on a comme données
            if hasattr(d, 'donnees_additionnelles'):
                print(f"TOP ELEVE: {d.nom}, prénom={d.prenom}, "
                    f"clés disponibles: {d.donnees_additionnelles.keys() if d.donnees_additionnelles else 'aucune'}")
                
            # Compléter les données manquantes
            if not d.prenom and hasattr(d, 'donnees_additionnelles') and d.donnees_additionnelles:
                for key in ['Prénom', 'prenom', 'Prenom', 'PRENOM']:
                    if key in d.donnees_additionnelles and d.donnees_additionnelles[key]:
                        d.prenom = str(d.donnees_additionnelles[key])
                        print(f"Prénom ajouté: {d.prenom}")
                        break

        stats['top_eleves'] = top_eleves
    
    context = {
        'etablissement': etablissement,
        'classes': classes,
        'niveaux': niveaux,
        'imports': imports,
        'moyennes': donnees_moyennes,
        'stats': stats,
        'selected_classe': classe_id,
        'selected_niveau': niveau_id,
        'selected_import': import_id,
        'selected_sexe': sexe,
        'selected_intervalle': intervalle,
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

def semestre1_analyse_disciplines(request):
    """
    Vue pour l'analyse des disciplines du Semestre 1
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
    discipline_selectionnee = request.GET.get('discipline')
    sexe = request.GET.get('sexe')
    
    # Base de requête pour les données détaillées
    donnees_query = DonneesDetailleesEleves.objects.filter(
        import_fichier__semestre=1,
        import_fichier__annee_scolaire=annee_scolaire,
        import_fichier__statut='termine'
    )
    
    # Appliquer les filtres
    if import_id:
        donnees_query = donnees_query.filter(import_fichier_id=import_id)
    
    if classe_id:
        classe = Classe.objects.get(id=classe_id)
        donnees_query = donnees_query.filter(classe=classe.nom)
    
    if niveau_id:
        niveau = Niveau.objects.get(id=niveau_id)
        # Trouver les classes du niveau
        classes_niveau = Classe.objects.filter(niveau=niveau)
        donnees_query = donnees_query.filter(classe__in=[c.nom for c in classes_niveau])
    
    # Identifier les disciplines disponibles de manière robuste
    def get_disciplines_disponibles():
        disciplines = set()
        
        # Parcourir tous les enregistrements pour extraire les disciplines
        for donnees in donnees_query:
            # Trouver les clés qui se terminent par "Moy D"
            for key in donnees.disciplines.keys():
                if key.endswith(" Moy D"):
                    # Enlever le suffixe " Moy D"
                    discipline = key[:-6].strip()
                    disciplines.add(discipline)
        
        return sorted(list(disciplines))
    
    # Initialiser la liste des disciplines disponibles
    disciplines_disponibles = get_disciplines_disponibles()
    
    # Préparer les statistiques pour la discipline sélectionnée
    stats_discipline = {}
    donnees_discipline = []
    distribution_notes = {
        'labels': ['0-4', '4-8', '8-10', '10-12', '12-14', '14-16', '16-20'],
        'data': [0, 0, 0, 0, 0, 0, 0]
    }
    
    if discipline_selectionnee:
        # Construire la clé de moyenne pour la discipline
        moy_key = f"{discipline_selectionnee} Moy D"
        
        # Filtrer les données
        donnees_discipline = [
            eleve for eleve in donnees_query 
            if moy_key in eleve.disciplines and eleve.disciplines
        ]
        
        # Filtrer par sexe si spécifié
        if sexe:
            donnees_discipline = [
                eleve for eleve in donnees_discipline
                if eleve.disciplines.get('Sexe', '').upper().startswith(sexe.upper())
            ]
        
        # Calculer les statistiques
        if donnees_discipline:
            import statistics
            
            # Extraire les moyennes
            moyennes = []
            for eleve in donnees_discipline:
                try:
                    moyenne = float(eleve.disciplines.get(moy_key, 0))
                    moyennes.append(moyenne)
                except (ValueError, TypeError):
                    pass
            
            if moyennes:
                stats_discipline = {
                    'nombre_eleves': len(moyennes),
                    'moyenne_globale': round(sum(moyennes) / len(moyennes), 2),
                    'min_moyenne': round(min(moyennes), 2),
                    'max_moyenne': round(max(moyennes), 2),
                    'ecart_type': round(statistics.pstdev(moyennes) if len(moyennes) > 1 else 0, 2),
                }
                
                # Calculer la distribution des notes
                for moyenne in moyennes:
                    if moyenne < 4:
                        distribution_notes['data'][0] += 1
                    elif moyenne < 8:
                        distribution_notes['data'][1] += 1
                    elif moyenne < 10:
                        distribution_notes['data'][2] += 1
                    elif moyenne < 12:
                        distribution_notes['data'][3] += 1
                    elif moyenne < 14:
                        distribution_notes['data'][4] += 1
                    elif moyenne < 16:
                        distribution_notes['data'][5] += 1
                    else:
                        distribution_notes['data'][6] += 1
            else:
                stats_discipline = {
                    'nombre_eleves': 0,
                    'moyenne_globale': 0,
                    'min_moyenne': 0,
                    'max_moyenne': 0,
                    'ecart_type': 0,
                }
    
    context = {
        'etablissement': etablissement,
        'classes': classes,
        'niveaux': niveaux,
        'imports': imports,
        'disciplines_disponibles': disciplines_disponibles,
        'selected_classe': classe_id,
        'selected_niveau': niveau_id,
        'selected_import': import_id,
        'selected_discipline': discipline_selectionnee,
        'selected_sexe': sexe,
        'stats_discipline': stats_discipline,
        'donnees_discipline': donnees_discipline,
        'distribution_notes': distribution_notes,
    }
    
    return render(request, 'core/semestre1/analyse_disciplines.html', context)