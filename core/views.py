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
            import re  # Pour le nettoyage des valeurs non numériques
            
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

            # Ajouter ce code de débogage juste après:
            print("DEBUG - CONTENU DU DATAFRAME MOYENNES ELEVES:")
            print(f"Colonnes détectées: {df_moyennes.columns.tolist()}")
            print(f"Nombre de lignes: {len(df_moyennes)}")
            # Afficher les 2 premières lignes pour vérification
            if not df_moyennes.empty:
                print("Premières lignes:")
                print(df_moyennes.head(2))
                # Vérifier spécifiquement la colonne 'Moy. Gén.'
                if 'Moy. Gén.' in df_moyennes.columns:
                    print("Valeurs de la colonne 'Moy. Gén.':")
                    print(df_moyennes['Moy. Gén.'].head(5))
                else:
                    print("ATTENTION: Colonne 'Moy. Gén.' non trouvée!")
                    print("Noms des colonnes disponibles:")
                    for col in df_moyennes.columns:
                        print(f"  - {col}")
            else:
                print("ATTENTION: DataFrame vide!")
            
            # Extraire le sexe depuis l'onglet "Moyennes eleves" pour chaque élève
            eleves_avec_sexe = {}
            for idx, row in df_moyennes.iterrows():
                nom = str(row.get('Nom', '')).strip()
                prenom = str(row.get('Prénom', '')).strip() if pd.notna(row.get('Prénom')) else ''
                ine = str(row.get('INE', '')).strip() if pd.notna(row.get('INE')) else None
                
                # Récupérer le sexe
                sexe = None
                for col in ['Sexe', 'sexe', 'Genre', 'genre']:
                    if col in df_moyennes.columns and pd.notna(row.get(col)):
                        sexe_valeur = str(row.get(col)).upper()
                        if sexe_valeur.startswith('M') or sexe_valeur.startswith('H'):
                            sexe = 'M'
                            break
                        elif sexe_valeur.startswith('F'):
                            sexe = 'F'
                            break
                
                # Stocker par INE si disponible
                if ine:
                    eleves_avec_sexe[ine] = sexe
                
                # Stocker aussi par nom/prénom pour les cas sans INE
                eleve_key = (nom.lower(), prenom.lower())
                eleves_avec_sexe[eleve_key] = sexe
                
                print(f"Élève extrait: {nom} {prenom}, INE: {ine}, Sexe: {sexe}")
            
            # --- 2) Lecture préliminaire pour extraire les vrais noms des disciplines
            # Lire les premières lignes pour identifier les noms des disciplines
            df_entetes = pd.read_excel(
                xls,
                sheet_name="Données détaillées",
                nrows=8,  # Lire seulement les 8 premières lignes
                header=None
            )
            
            # Chercher les disciplines dans les premières lignes
            # Améliorer l'extraction des disciplines en analysant plusieurs lignes potentielles
            discipline_names = []
            
            # Parcourir les lignes 5, 6 et 4 pour trouver celle qui contient les disciplines
            for discipline_line in [5, 6, 4]:
                potential_disciplines = []
                # Parcourir toutes les colonnes à partir de la 3e (après Nom, Prénom, Classe)
                for col in range(3, df_entetes.shape[1]):
                    cell_value = df_entetes.iloc[discipline_line, col]
                    if pd.notna(cell_value) and str(cell_value).strip():
                        potential_disciplines.append(str(cell_value).strip())
                
                # Si nous avons trouvé des disciplines potentielles, c'est probablement la bonne ligne
                if len(potential_disciplines) > 3:  # Au moins 3 disciplines
                    discipline_names = potential_disciplines
                    print(f"Disciplines trouvées à la ligne {discipline_line+1}: {discipline_names}")
                    break
            
            # --- 3) Lecture de l'onglet "Données détaillées" avec les noms corrects
            # Lire l'onglet en considérant les 2 lignes d'en-tête fusionnées
            df_detail = pd.read_excel(
                xls,
                sheet_name="Données détaillées",
                skiprows=range(8),  # Ignore les 8 premières lignes
                header=[0, 1]  # Considère les 2 premières lignes comme en-têtes 
            )
            
            # Extraire les colonnes principales et sous-colonnes
            disciplines = list(df_detail.columns.get_level_values(0))
            sous_colonnes = list(df_detail.columns.get_level_values(1))
            
            # Remplacer les "Unnamed" dans les disciplines par la valeur précédente
            # (effet des cellules fusionnées)
            for i in range(len(disciplines)):
                if "Unnamed" in str(disciplines[i]):
                    disciplines[i] = disciplines[i-1]
            
            # --- 4) Sélectionner les 3 premières colonnes (Infos élèves)
            info_colonnes = df_detail.iloc[:, :3].copy()
            info_colonnes.columns = [col[0] for col in info_colonnes.columns]
            
            # Vérifier si les colonnes nécessaires sont présentes 
            required_columns = ['Nom']
            missing_columns = [col for col in required_columns if col not in info_colonnes.columns]
            
            if missing_columns:
                raise ValueError(f"Colonnes manquantes dans le fichier: {', '.join(missing_columns)}")
            
            # Vérifier si la colonne 'Prénom' existe, sinon créer une colonne vide
            if 'Prénom' not in info_colonnes.columns:
                info_colonnes['Prénom'] = None
            
            # --- 5) Sélectionner uniquement les colonnes "Moy D" et récupérer leurs positions
            colonnes_moy_d = []
            for i, col in enumerate(sous_colonnes):
                if str(col).strip() == "Moy D":
                    colonnes_moy_d.append(i)
            
            df_detail_moy_d = df_detail.iloc[:, colonnes_moy_d].copy()
            
            # Récupérer les noms des disciplines pour les colonnes "Moy D"
            disciplines_for_moy_d = [disciplines[i] for i in colonnes_moy_d]
            
            # Utiliser les noms extraits des en-têtes si disponibles
            if discipline_names and len(discipline_names) >= len(colonnes_moy_d):
                # S'assurer que nous avons le bon nombre de disciplines
                noms_moy_d = discipline_names[:len(colonnes_moy_d)]
                print(f"Utilisation des disciplines extraites des en-têtes: {noms_moy_d}")
            else:
                # Sinon utiliser ceux extraits des colonnes
                noms_moy_d = disciplines_for_moy_d
                print(f"Utilisation des disciplines extraites des colonnes: {noms_moy_d}")
            
            # Renommer les colonnes de moyennes avec les noms extraits
            df_detail_moy_d.columns = noms_moy_d
            
            # --- 6) Fusionner les infos élèves avec les moyennes "Moy D"
            df_final = pd.concat([info_colonnes, df_detail_moy_d], axis=1)
            
            # --- 7) Ajouter la colonne de sexe à df_final ---
            # --- 7) Ajouter la colonne de sexe à df_final ---
            # Vérifier si la colonne Sexe existe dans df_moyennes
            if 'Sexe' in df_moyennes.columns:
                # Créer un dictionnaire pour associer nom+prénom à la valeur de sexe
                sexe_map = {}
                for idx, row in df_moyennes.iterrows():
                    nom = str(row.get('Nom', '')).strip()
                    prenom = str(row.get('Prénom', '')).strip() if pd.notna(row.get('Prénom')) else ''
                    if pd.notna(row.get('Sexe')):
                        sexe_map[(nom.lower(), prenom.lower())] = row.get('Sexe')
                
                # Appliquer à df_final
                df_final['Sexe'] = None
                for idx, row in df_final.iterrows():
                    nom = str(row.get('Nom', '')).strip()
                    prenom = str(row.get('Prénom', '')).strip() if pd.notna(row.get('Prénom')) else ''
                    key = (nom.lower(), prenom.lower())
                    if key in sexe_map:
                        df_final.loc[idx, 'Sexe'] = sexe_map[key]
                        print(f"Sexe ajouté pour {nom} {prenom}: {sexe_map[key]}")
            
            # --- 8) Stocker les données du tableau "Moyennes eleves"
            print("DEBUG - TRAITEMENT DES MOYENNES PAR ÉLÈVE:")

            # Déterminer quelle colonne contient la moyenne générale
            moyenne_col = None
            if 'Moy. Gén.' in df_moyennes.columns:
                moyenne_col = 'Moy. Gén.'
            elif 'Moy' in df_moyennes.columns:
                moyenne_col = 'Moy'
            else:
                # Recherche par mot-clé
                for col in df_moyennes.columns:
                    if 'moy' in col.lower():
                        moyenne_col = col
                        print(f"Colonne moyenne trouvée: {col}")
                        break

            if not moyenne_col:
                print("ERREUR: Aucune colonne de moyenne trouvée!")
                raise ValueError("Aucune colonne de moyenne trouvée dans le fichier Excel")

            print(f"Utilisation de la colonne '{moyenne_col}' pour les moyennes générales")

            for idx, row in df_moyennes.iterrows():
                # Extraction du nom, prénom et classe
                nom = str(row.get('Nom', ''))
                prenom = str(row.get('Prénom', '')) if pd.notna(row.get('Prénom')) else None
                classe_texte = str(row.get('Classe', '')) if pd.notna(row.get('Classe')) else None
                
                # Extraction de la moyenne générale
                moyenne_generale = row.get(moyenne_col) if pd.notna(row.get(moyenne_col)) else None
                print(f"Élève {idx+1}: {nom} {prenom or ''}, Moyenne: {moyenne_generale}, Type: {type(moyenne_generale)}")
                
                # Si la classe et le niveau ont été sélectionnés ou identifiés
                classe_obj = None
                niveau_obj = None
                if classe_selectionnee:
                    classe_obj = classe_selectionnee
                    niveau_obj = niveau_selectionne
                else:
                    # Tenter de trouver la classe correspondante
                    for c in classes:
                        if classe_texte and c.nom in classe_texte:
                            classe_obj = c
                            niveau_obj = c.niveau
                            break
                
                # Création des données additionnelles (autres colonnes)
                donnees_add = {}
                for col in df_moyennes.columns:
                    if col not in ['Nom', 'Prénom', 'Classe', moyenne_col, 'Rang']:
                        if pd.notna(row.get(col)):
                            donnees_add[col] = row.get(col)
                
                # Extraction et nettoyage du rang
                rang_brut = row.get('Rang')
                rang = None
                if pd.notna(rang_brut):
                    # Vérifier si c'est un nombre valide
                    try:
                        # Nettoyer les valeurs potentiellement non numériques
                        rang_str = str(rang_brut).strip()
                        # Extraire les chiffres si la valeur contient du texte (comme "32ex")
                        matches = re.match(r'(\d+)', rang_str)
                        if matches:
                            rang = int(matches.group(1))
                        else:
                            rang = None
                    except (ValueError, TypeError):
                        rang = None
                
                # Création de l'entrée dans DonneesMoyennesEleves si le nom existe
                if nom:
                    # Convertir la moyenne en float si possible
                    moyenne_value = None
                    if moyenne_generale is not None:
                        try:
                            if isinstance(moyenne_generale, str):
                                moyenne_value = float(moyenne_generale.replace(',', '.'))
                            else:
                                moyenne_value = float(moyenne_generale)
                            print(f"Moyenne convertie pour {nom}: {moyenne_value}")
                        except (ValueError, TypeError) as e:
                            print(f"Erreur conversion moyenne pour {nom}: {e}, valeur: {moyenne_generale}")
                            moyenne_value = None
                    
                    # Créer l'objet DonneesMoyennesEleves
                    obj = DonneesMoyennesEleves.objects.create(
                        import_fichier=import_fichier,
                        nom=nom,
                        prenom=prenom,
                        classe_texte=classe_texte,
                        classe_obj=classe_obj,
                        niveau=niveau_obj,
                        moyenne_generale=moyenne_value,
                        rang_classe=rang,
                        effectif_classe=classe_obj.effectif if classe_obj else None,
                        donnees_additionnelles=donnees_add
                    )
                    print(f"DonneesMoyennesEleves créé: ID={obj.id}, Nom={nom}, Moyenne={obj.moyenne_generale}")
                    
                    # Créer également une entrée dans MoyenneEleve pour maintenir la compatibilité
                    if classe_obj:
                        moyenne_eleve = MoyenneEleve.objects.create(
                            import_fichier=import_fichier,
                            nom_eleve=nom,
                            prenom_eleve=prenom,
                            classe=classe_obj,
                            moyenne_generale=moyenne_value,
                            rang=rang
                        )
                        print(f"MoyenneEleve créé: ID={moyenne_eleve.id}, Moyenne={moyenne_eleve.moyenne_generale}")
            
            # --- 9) Stocker les données du tableau "Données détaillées"
            # Créer un dictionnaire pour stocker les données détaillées

            # Extraire les noms des disciplines correctement
            discipline_colonnes = noms_moy_d

            # Créer un dictionnaire pour associer élèves et données détaillées
            donnees_detail_par_eleve = {}

            # Créer un dictionnaire pour stocker le sexe des élèves à partir des données déjà traitées
            sexe_par_eleve = {}
            for idx, row in df_moyennes.iterrows():
                nom = str(row.get('Nom', '')).strip()
                prenom = str(row.get('Prénom', '')).strip() if pd.notna(row.get('Prénom')) else ''
                
                # Récupérer le sexe
                sexe = None
                for col in ['Sexe', 'sexe', 'Genre', 'genre']:
                    if col in df_moyennes.columns and pd.notna(row.get(col)):
                        sexe_valeur = str(row.get(col)).upper()
                        if sexe_valeur.startswith('M') or sexe_valeur.startswith('H'):
                            sexe = 'M'
                            break
                        elif sexe_valeur.startswith('F'):
                            sexe = 'F'
                            break
                
                # Stocker le sexe pour cet élève
                if sexe:
                    sexe_par_eleve[(nom.lower(), prenom.lower())] = sexe
                    print(f"Sexe stocké pour {nom} {prenom}: {sexe}")

            # Maintenant, traitons les données détaillées
            for idx, row in df_final.iterrows():
                nom = str(row.get('Nom', ''))
                prenom = str(row.get('Prénom', '')) if pd.notna(row.get('Prénom')) else None
                classe_nom = str(row.get('Classe', '')) if pd.notna(row.get('Classe')) else None
                
                # Créer un dictionnaire pour les disciplines
                disciplines_dict = {}
                
                # Ajouter les moyennes des disciplines
                for discipline in discipline_colonnes:
                    # Clé avec le nom de la discipline et suffixe "Moy D"
                    moy_key = f"{discipline} Moy D"
                    
                    # Trouver la valeur de la moyenne directement depuis df_final
                    moy_value = row.get(discipline)
                    
                    # Ajouter au dictionnaire si la valeur existe
                    if pd.notna(moy_value):
                        disciplines_dict[moy_key] = moy_value
                
                # Ajouter des informations supplémentaires de la première section
                for col in info_colonnes.columns:
                    if pd.notna(row.get(col)):
                        disciplines_dict[col] = row.get(col)
                
                # Récupérer le sexe directement depuis df_final
                sexe_value = row.get('Sexe')
                
                # Si pas trouvé, essayer depuis sexe_par_eleve
                if not sexe_value:
                    eleve_key = (nom.lower(), (prenom or '').lower())
                    sexe_value = sexe_par_eleve.get(eleve_key)
                
                # Ajouter le sexe au dictionnaire disciplines
                if sexe_value:
                    disciplines_dict['Sexe'] = sexe_value
                
                # Sauvegarder dans la base de données
                if nom:  # S'assurer qu'il y a un nom
                    donnees_detail = DonneesDetailleesEleves.objects.create(
                        import_fichier=import_fichier,
                        nom=nom,
                        prenom=prenom,
                        classe=classe_nom,
                        sexe=sexe_value,  # Ajouter le sexe ici
                        disciplines=disciplines_dict
                    )
                    
                    # Stocker dans le dictionnaire pour l'utiliser plus tard
                    donnees_detail_par_eleve[(nom, prenom if prenom else '')] = disciplines_dict
            
            # --- 10) Associer les moyennes de disciplines aux élèves dans MoyenneEleve
            # Pour chaque MoyenneEleve, trouver les données détaillées correspondantes
            # et créer les MoyenneDiscipline appropriées
            for moyenne_eleve in MoyenneEleve.objects.filter(import_fichier=import_fichier):
                nom = moyenne_eleve.nom_eleve
                prenom = moyenne_eleve.prenom_eleve if moyenne_eleve.prenom_eleve else ''
                
                # Rechercher les données détaillées correspondantes
                disciplines_dict = donnees_detail_par_eleve.get((nom, prenom), None)
                
                if disciplines_dict:
                    # Pour chaque discipline, créer une MoyenneDiscipline
                    for discipline in discipline_colonnes:
                        moy_key = f"{discipline} Moy D"
                        if moy_key in disciplines_dict:
                            moy_value = disciplines_dict[moy_key]
                            
                            if pd.notna(moy_value):
                                try:
                                    # Convertir en float si possible
                                    moyenne_float = float(str(moy_value).replace(',', '.'))
                                    MoyenneDiscipline.objects.create(
                                        eleve=moyenne_eleve,
                                        nom_discipline=discipline,
                                        moyenne=moyenne_float
                                    )
                                except (ValueError, TypeError):
                                    # Ignorer les valeurs qui ne peuvent pas être converties
                                    pass
            
            # --- 11) Extraire et stocker les disciplines uniques
            # Stocker les disciplines dans les données supplémentaires de l'importation
            import_fichier.donnees_supplementaires = {
                'disciplines': discipline_colonnes
            }
            
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

from django.shortcuts import render
from django.db.models import Q, FloatField
from django.db.models.functions import Cast

from .models import (
    Etablissement, 
    Classe, 
    Niveau, 
    ImportFichier, 
    DonneesMoyennesEleves
)

def semestre1_analyse_moyennes(request):
    """
    Vue pour l'analyse des moyennes du Semestre 1, basée uniquement sur l'onglet 'Moyennes eleves'
    """
    # Code de débogage pour vérifier les données
    print("DEBUG - Vérification des données DonneesMoyennesEleves:")
    dmoyennes = DonneesMoyennesEleves.objects.all()
    print(f"Nombre total d'objets: {dmoyennes.count()}")
    for donnee in dmoyennes[:5]:
        print(f"ID: {donnee.id}, Élève: {donnee.nom}, Moyenne: {donnee.moyenne_generale}, "
              f"Import: {donnee.import_fichier.titre}")
    
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
    
    # Si aucun filtre n'est appliqué, utiliser le dernier import par défaut
    if not any([classe_id, niveau_id, import_id, sexe, intervalle]):
        dernier_import = imports.order_by('-date_import').first()
        if dernier_import:
            import_id = str(dernier_import.id)
            donnees_moyennes_query = donnees_moyennes_query.filter(import_fichier_id=import_id)
    else:
        # Appliquer les filtres
        if import_id:
            donnees_moyennes_query = donnees_moyennes_query.filter(import_fichier_id=import_id)
        
        if classe_id:
            donnees_moyennes_query = donnees_moyennes_query.filter(classe_obj_id=classe_id)
        
        if niveau_id:
            donnees_moyennes_query = donnees_moyennes_query.filter(niveau_id=niveau_id)
    
    # Filtrer par sexe
    if sexe:
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
        top_eleves = donnees_moyennes[:5] if len(donnees_moyennes) >=5 else donnees_moyennes

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
    
    # Si aucun filtre n'est appliqué, utiliser le dernier import par défaut
    if not any([classe_id, niveau_id, import_id, discipline_selectionnee, sexe]):
        dernier_import = imports.order_by('-date_import').first()
        if dernier_import:
            import_id = str(dernier_import.id)
            donnees_query = donnees_query.filter(import_fichier_id=import_id)
    else:
        # Appliquer les filtres
        if import_id:
            donnees_query = donnees_query.filter(import_fichier_id=import_id)
        
        if classe_id:
            classe = Classe.objects.get(id=classe_id)
            donnees_query = donnees_query.filter(classe__icontains=classe.nom)
        
        if niveau_id:
            niveau = Niveau.objects.get(id=niveau_id)
            # Trouver les classes du niveau
            classes_niveau = Classe.objects.filter(niveau=niveau)
            classe_patterns = [c.nom for c in classes_niveau]
            
            # Utiliser Q objects pour faire un OR entre les différentes classes
            from django.db.models import Q
            q_objects = Q()
            for classe_pattern in classe_patterns:
                q_objects |= Q(classe__icontains=classe_pattern)
            
            donnees_query = donnees_query.filter(q_objects)
    
    # Fonction pour récupérer les disciplines disponibles
    def get_disciplines_disponibles():
        disciplines = set()
        
        # Si un import spécifique est sélectionné, récupérer ses disciplines
        if import_id:
            try:
                import_obj = ImportFichier.objects.get(id=import_id)
                if import_obj.donnees_supplementaires and 'disciplines' in import_obj.donnees_supplementaires:
                    return sorted(import_obj.donnees_supplementaires['disciplines'])
            except ImportFichier.DoesNotExist:
                pass
        
        # Sinon, analyser les données pour extraire les disciplines
        for donnee in donnees_query:
            for key in donnee.disciplines.keys():
                if key.endswith(" Moy D"):
                    discipline = key.replace(" Moy D", "").strip()
                    disciplines.add(discipline)
        
        if not disciplines:
            # Si aucune discipline trouvée, essayer une autre approche
            for import_obj in imports:
                if hasattr(import_obj, 'donnees_supplementaires') and import_obj.donnees_supplementaires:
                    if 'disciplines' in import_obj.donnees_supplementaires:
                        disciplines.update(import_obj.donnees_supplementaires['disciplines'])
        
        return sorted(list(disciplines))
    
    # Initialiser la liste des disciplines disponibles
    disciplines_disponibles = get_disciplines_disponibles()
    
    # Sélectionner automatiquement la première discipline si aucune n'est sélectionnée
    if not discipline_selectionnee and disciplines_disponibles:
        discipline_selectionnee = disciplines_disponibles[0]
    
    # Préparer les statistiques pour la discipline sélectionnée
    stats_discipline = {}
    donnees_discipline = []
    distribution_notes = {
        'labels': ['0-4', '4-8', '8-10', '10-12', '12-14', '14-16', '16-20'],
        'data': [0, 0, 0, 0, 0, 0, 0]
    }
    
    if discipline_selectionnee and disciplines_disponibles:
        # Construire la clé de moyenne pour la discipline
        moy_key = f"{discipline_selectionnee} Moy D"
        
        # Récupérer TOUTES les données de moyennes pour le(s) import(s) sélectionné(s)
        moyennes_query = DonneesMoyennesEleves.objects.filter(
            import_fichier__semestre=1,
            import_fichier__annee_scolaire=annee_scolaire,
            import_fichier__statut='termine'
        )
        
        if import_id:
            moyennes_query = moyennes_query.filter(import_fichier_id=import_id)
        
        # Créer un dictionnaire pour accéder rapidement aux données de moyennes par élève
        moyennes_dict = {}
        ine_dict = {}  # Nouveau dictionnaire pour faire correspondre les INE
        
        # Créer un dictionnaire pour stocker le sexe correct des élèves
        sexe_correct = {}
        
        for m in moyennes_query:
            # Clé standardisée pour identifier un élève par nom/prénom
            eleve_key = (m.nom.strip().lower(), (m.prenom or '').strip().lower())
            moyennes_dict[eleve_key] = m
            
            # Récupérer et stocker le sexe à partir de donnees_additionnelles
            if m.donnees_additionnelles:
                for key in ['Sexe', 'sexe', 'Genre', 'genre']:
                    if key in m.donnees_additionnelles and m.donnees_additionnelles[key]:
                        sexe_val = str(m.donnees_additionnelles[key]).upper()
                        if sexe_val.startswith('M') or sexe_val.startswith('H'):
                            sexe_correct[eleve_key] = 'M'
                            break
                        elif sexe_val.startswith('F'):
                            sexe_correct[eleve_key] = 'F'
                            break
            
            # Récupérer l'INE si disponible dans donnees_additionnelles
            if m.donnees_additionnelles:
                for key in ['INE', 'ine', 'Ine', 'N°INE', 'Numéro INE']:
                    if key in m.donnees_additionnelles and m.donnees_additionnelles[key]:
                        ine_val = str(m.donnees_additionnelles[key]).strip()
                        ine_dict[ine_val] = m
                        break
        
        # Filtrer les données pour la discipline sélectionnée
        for eleve in donnees_query:
            if moy_key in eleve.disciplines and eleve.disciplines[moy_key] is not None:
                try:
                    # Extraire la moyenne pour cette discipline
                    moyenne = float(str(eleve.disciplines[moy_key]).replace(',', '.'))
                    eleve.moyenne_discipline = moyenne

                    # Déterminer le sexe de l'élève - méthode prioritaire
                    eleve.sexe_value = 'Non précisé'
                    
                    # 1. D'abord vérifier le champ sexe du modèle
                    if eleve.sexe:
                        if eleve.sexe.upper() in ['M', 'H']:
                            eleve.sexe_value = 'M'
                        elif eleve.sexe.upper() == 'F':
                            eleve.sexe_value = 'F'
                    
                    # 2. Ensuite vérifier dans disciplines
                    elif 'Sexe' in eleve.disciplines and eleve.disciplines['Sexe']:
                        sexe_val = str(eleve.disciplines['Sexe']).upper()
                        if sexe_val.startswith('M') or sexe_val.startswith('H'):
                            eleve.sexe_value = 'M'
                        elif sexe_val.startswith('F'):
                            eleve.sexe_value = 'F'
                    
                    # 3. Enfin chercher par clé nom/prénom
                    else:
                        eleve_key = (eleve.nom.strip().lower(), (eleve.prenom or '').strip().lower())
                        if eleve_key in sexe_correct:
                            eleve.sexe_value = sexe_correct[eleve_key]
                    
                    # Récupérer l'INE de l'élève depuis disciplines
                    ine_eleve = None
                    for key in ['INE', 'ine', 'Ine', 'N°INE', 'Numéro INE']:
                        if key in eleve.disciplines and eleve.disciplines[key]:
                            ine_eleve = str(eleve.disciplines[key]).strip()
                            break
                    
                    # Construire la clé par nom/prénom pour retrouver cet élève dans les données de moyennes
                    eleve_key = (eleve.nom.strip().lower(), (eleve.prenom or '').strip().lower())
                    
                    # Assigner des valeurs par défaut
                    eleve.classe_obj = None
                    eleve.niveau_obj = None
                    
                    # Priorité 1: Essayer de retrouver l'élève par INE
                    moyennes_eleve = None
                    if ine_eleve and ine_eleve in ine_dict:
                        moyennes_eleve = ine_dict[ine_eleve]
                        # Debug
                        print(f"INE match found for {eleve.nom}: {ine_eleve}")
                    
                    # Priorité 2: Si pas trouvé par INE, essayer par nom/prénom
                    if not moyennes_eleve and eleve_key in moyennes_dict:
                        moyennes_eleve = moyennes_dict[eleve_key]
                        # Debug
                        print(f"Name match found for {eleve.nom} {eleve.prenom}")
                    
                    # Si on a trouvé l'élève dans les moyennes, récupérer ses informations
                    if moyennes_eleve:
                        # Récupérer les informations de classe et niveau
                        eleve.classe_obj = moyennes_eleve.classe_obj
                        eleve.niveau_obj = moyennes_eleve.niveau
                        
                        # Récupérer le prénom si manquant
                        if not eleve.prenom and moyennes_eleve.prenom:
                            eleve.prenom = moyennes_eleve.prenom
                    
                    # Assigner d'autres informations manquantes si nécessaire
                    if not eleve.classe_obj and eleve.classe:
                        for c in classes:
                            if c.nom in eleve.classe:
                                eleve.classe_obj = c
                                eleve.niveau_obj = c.niveau
                                break
                    
                    # Appliquer le filtre par sexe
                    if not sexe or eleve.sexe_value == sexe:
                        donnees_discipline.append(eleve)
                
                except (ValueError, TypeError) as e:
                    print(f"Erreur pour {eleve.nom}: {e} - Valeur: {eleve.disciplines.get(moy_key, 'Non trouvée')}")
        
        # Calculer toutes les statistiques
        if donnees_discipline:
            import statistics
            
            # Récupérer les moyennes de tous les élèves
            moyennes = [eleve.moyenne_discipline for eleve in donnees_discipline]
            
            if moyennes:
                # Statistiques de base
                stats_discipline = {
                    'nombre_eleves': len(moyennes),
                    'moyenne_globale': round(sum(moyennes) / len(moyennes), 2),
                    'min_moyenne': round(min(moyennes), 2),
                    'max_moyenne': round(max(moyennes), 2),
                    'ecart_type': round(statistics.pstdev(moyennes) if len(moyennes) > 1 else 0, 2),
                    'mediane': round(statistics.median(moyennes), 2) if len(moyennes) > 0 else 0,
                }
                
                # Distribution des notes
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
                
                # Répartition par sexe
                repartition_sexe = {'M': 0, 'F': 0, 'Non précisé': 0}
                reussite_par_sexe = {'M': 0, 'F': 0}

                for eleve in donnees_discipline:
                    # Utiliser sexe_value qui a été correctement défini
                    sexe_standardise = eleve.sexe_value
                    if sexe_standardise not in ['M', 'F']:
                        sexe_standardise = 'Non précisé'
                    
                    # Compter l'élève dans la répartition par sexe
                    repartition_sexe[sexe_standardise] += 1
                    
                    # Si l'élève a une moyenne ≥ 10, le compter dans les réussites
                    if eleve.moyenne_discipline >= 10:
                        if sexe_standardise in ['M', 'F']:
                            reussite_par_sexe[sexe_standardise] += 1
                
                # Calculer les taux de réussite
                total_eleves = len(donnees_discipline)
                reussite_totale = sum(1 for m in moyennes if m >= 10)
                
                stats_discipline['repartition_sexe'] = repartition_sexe
                stats_discipline['taux_reussite'] = {
                    'total': round(reussite_totale / total_eleves * 100, 1) if total_eleves > 0 else 0,
                    'nombre': reussite_totale,
                    'par_sexe': reussite_par_sexe
                }
                
                # Calculer les pourcentages de réussite par sexe
                for sexe_key in ['M', 'F']:
                    total_sexe = repartition_sexe.get(sexe_key, 0)
                    if total_sexe > 0:
                        stats_discipline['taux_reussite']['par_sexe'][f'{sexe_key}_taux'] = round(
                            reussite_par_sexe[sexe_key] / total_sexe * 100, 1
                        )
                    else:
                        stats_discipline['taux_reussite']['par_sexe'][f'{sexe_key}_taux'] = 0
            else:
                # Valeurs par défaut si pas de données
                stats_discipline = {
                    'nombre_eleves': 0,
                    'moyenne_globale': 0,
                    'min_moyenne': 0,
                    'max_moyenne': 0,
                    'ecart_type': 0,
                    'mediane': 0,
                    'taux_reussite': {
                        'total': 0,
                        'nombre': 0,
                        'par_sexe': {
                            'M': 0,
                            'F': 0,
                            'M_taux': 0,
                            'F_taux': 0
                        }
                    },
                    'repartition_sexe': {'M': 0, 'F': 0, 'Non précisé': 0}
                }
    
    # Trier les données par moyenne décroissante
    if donnees_discipline:
        donnees_discipline.sort(key=lambda x: x.moyenne_discipline, reverse=True)
        
        # Ajouter le rang à chaque élève
        for i, eleve in enumerate(donnees_discipline):
            eleve.rang = i + 1
    
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
        'debug_mode': False,
    }
    
    return render(request, 'core/semestre1/analyse_disciplines.html', context)