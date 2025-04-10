# core/pdf_generator.py
import os
from io import BytesIO
from django.conf import settings
from django.template.loader import get_template
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER
from django.utils import timezone
from .models import Etablissement, Classe, Niveau, DonneesMoyennesEleves, DonneesDetailleesEleves, ImportFichier

def format_float(value):
    """
    Formate un nombre flottant pour l'affichage comme dans les exemples
    (avec virgule au lieu de point décimal)
    """
    if value is None or value == 0:
        return "0,00"
    
    # Convertir les virgules en points si nécessaire pour le calcul
    if isinstance(value, str):
        value = value.replace(',', '.')
    
    try:
        # Formatter avec 2 décimales et utiliser une virgule à la place du point
        return "{:.2f}".format(float(value)).replace('.', ',')
    except (ValueError, TypeError):
        return "0,00"

def aggregate_stats(stats_list, type_stats='moyennes'):
    """
    Agrège les statistiques de plusieurs classes ou niveaux
    :param stats_list: Liste des dictionnaires de statistiques
    :param type_stats: 'moyennes' ou 'disciplines'
    """
    if not stats_list:
        # Retourner les valeurs par défaut selon le type
        if type_stats == 'moyennes':
            return {
                'total': 0, 'filles': 0, 'garcons': 0,
                'taux': 0, 'taux_f': 0, 'taux_g': 0,
                'total_reussite': 0, 'filles_reussite': 0, 'garcons_reussite': 0,
                'max': 0, 'min': 0, 'moyenne': 0,
                'indicateurs': {'fel': 0, 'encou': 0, 'th': 0, 'pass': 0, 'insuff': 0}
            }
        else:
            return {
                'total': 0, 'filles': 0, 'garcons': 0,
                'taux': 0, 'taux_f': 0, 'taux_g': 0,
                'total_reussite': 0, 'filles_reussite': 0, 'garcons_reussite': 0,
                'max': 0, 'min': 0, 'moyenne': 0,
                'indicateurs': {'tb': 0, 'bien': 0, 'abien': 0, 'pass': 0, 'insuf': 0, 'faible': 0}
            }
    
    # Agréger les statistiques
    total = sum(s['total'] for s in stats_list)
    filles = sum(s['filles'] for s in stats_list)
    garcons = sum(s['garcons'] for s in stats_list)
    
    reussite_total = sum(s['total_reussite'] for s in stats_list)
    reussite_filles = sum(s['filles_reussite'] for s in stats_list)
    reussite_garcons = sum(s['garcons_reussite'] for s in stats_list)
    
    # Indicateurs selon le type de statistiques
    if type_stats == 'moyennes':
        indicateurs = {
            'fel': sum(s['indicateurs']['fel'] for s in stats_list),
            'encou': sum(s['indicateurs']['encou'] for s in stats_list),
            'th': sum(s['indicateurs']['th'] for s in stats_list),
            'pass': sum(s['indicateurs']['pass'] for s in stats_list),
            'insuff': sum(s['indicateurs']['insuff'] for s in stats_list)
        }
    else:
        indicateurs = {
            'tb': sum(s['indicateurs']['tb'] for s in stats_list),
            'bien': sum(s['indicateurs']['bien'] for s in stats_list),
            'abien': sum(s['indicateurs']['abien'] for s in stats_list),
            'pass': sum(s['indicateurs']['pass'] for s in stats_list),
            'insuf': sum(s['indicateurs']['insuf'] for s in stats_list),
            'faible': sum(s['indicateurs']['faible'] for s in stats_list)
        }
    
    # Calculer les taux de réussite
    taux = round((reussite_total / total) * 100) if total > 0 else 0
    taux_f = round((reussite_filles / filles) * 100) if filles > 0 else 0
    taux_g = round((reussite_garcons / garcons) * 100) if garcons > 0 else 0
    
    # Trouver min et max
    min_moy = min((s['min'] for s in stats_list if s['min'] > 0), default=0)
    max_moy = max((s['max'] for s in stats_list), default=0)
    
    # Calculer la moyenne pondérée
    total_sum = sum(s['total'] * s['moyenne'] for s in stats_list)
    moyenne = total_sum / total if total > 0 else 0
    
    return {
        'total': total,
        'filles': filles,
        'garcons': garcons,
        'taux': taux,
        'taux_f': taux_f,
        'taux_g': taux_g,
        'total_reussite': reussite_total,
        'filles_reussite': reussite_filles,
        'garcons_reussite': reussite_garcons,
        'max': max_moy,
        'min': min_moy,
        'moyenne': moyenne,
        'indicateurs': indicateurs
    }

def get_disciplines_for_import(import_obj):
    """
    Récupère les disciplines disponibles pour une importation
    """
    try:
        # D'abord, essayer de récupérer depuis donnees_supplementaires
        if hasattr(import_obj, 'donnees_supplementaires') and import_obj.donnees_supplementaires:
            if 'disciplines' in import_obj.donnees_supplementaires:
                return import_obj.donnees_supplementaires['disciplines']
        
        # Sinon, utiliser la méthode get_disciplines_disponibles
        return DonneesDetailleesEleves.get_disciplines_disponibles(import_obj)
    except Exception as e:
        print(f"Erreur lors de la récupération des disciplines: {e}")
        return ["MATHS"]  # Valeur par défaut

def calculate_moyennes_stats(donnees_queryset, classe):
    """
    Calcule les statistiques pour les moyennes générales d'une classe
    """
    # Filtrer les données pour la classe spécifiée
    donnees_classe = donnees_queryset.filter(classe_obj=classe)
    
    # Compter les élèves
    total = donnees_classe.count()
    if total == 0:
        return {
            'total': 0, 'filles': 0, 'garcons': 0,
            'taux': 0, 'taux_f': 0, 'taux_g': 0,
            'total_reussite': 0, 'filles_reussite': 0, 'garcons_reussite': 0,
            'max': 0, 'min': 0, 'moyenne': 0,
            'indicateurs': {'fel': 0, 'encou': 0, 'th': 0, 'pass': 0, 'insuff': 0}
        }
    
    # Compter par sexe
    filles = 0
    garcons = 0
    for eleve in donnees_classe:
        sexe = None
        if eleve.donnees_additionnelles:
            for key in ['Sexe', 'sexe', 'Genre', 'genre']:
                if key in eleve.donnees_additionnelles:
                    sexe_val = str(eleve.donnees_additionnelles[key]).upper()
                    if sexe_val.startswith('F'):
                        sexe = 'F'
                        break
                    elif sexe_val.startswith('M') or sexe_val.startswith('H'):
                        sexe = 'M'
                        break
        
        if sexe == 'F':
            filles += 1
        else:
            garcons += 1
    
    # Calculer les moyennes et taux de réussite
    moyennes = []
    min_moy = float('inf')
    max_moy = float('-inf')
    
    # Compteurs pour réussite
    reussite_total = 0
    reussite_filles = 0
    reussite_garcons = 0
    
    # Compteurs pour indicateurs
    fel = 0  # Félicitations (>= 16)
    encou = 0  # Encouragements (>= 14 et < 16)
    th = 0  # Tableau d'honneur (>= 12 et < 14)
    passable = 0  # Passable (>= 10 et < 12)
    insuff = 0  # Insuffisant (< 10)
    
    for eleve in donnees_classe:
        if eleve.moyenne_generale is not None:
            try:
                moyenne = float(str(eleve.moyenne_generale).replace(',', '.'))
                moyennes.append(moyenne)
                
                # Min/Max
                min_moy = min(min_moy, moyenne)
                max_moy = max(max_moy, moyenne)
                
                # Réussite
                if moyenne >= 10:
                    reussite_total += 1
                    
                    # Par sexe
                    sexe = None
                    if eleve.donnees_additionnelles:
                        for key in ['Sexe', 'sexe', 'Genre', 'genre']:
                            if key in eleve.donnees_additionnelles:
                                sexe_val = str(eleve.donnees_additionnelles[key]).upper()
                                if sexe_val.startswith('F'):
                                    sexe = 'F'
                                    break
                                elif sexe_val.startswith('M') or sexe_val.startswith('H'):
                                    sexe = 'M'
                                    break
                    
                    if sexe == 'F':
                        reussite_filles += 1
                    else:
                        reussite_garcons += 1
                
                # Indicateurs
                if moyenne >= 16:
                    fel += 1
                elif moyenne >= 14:
                    encou += 1
                elif moyenne >= 12:
                    th += 1
                elif moyenne >= 10:
                    passable += 1
                else:
                    insuff += 1
            except (ValueError, TypeError):
                pass
    
    # Calculer la moyenne de classe
    moy_generale = sum(moyennes) / len(moyennes) if moyennes else 0
    
    # Calculer les taux de réussite
    taux = round((reussite_total / total) * 100) if total > 0 else 0
    taux_f = round((reussite_filles / filles) * 100) if filles > 0 else 0
    taux_g = round((reussite_garcons / garcons) * 100) if garcons > 0 else 0
    
    # Si aucune moyenne n'a été trouvée
    if not moyennes:
        min_moy = 0
        max_moy = 0
    
    return {
        'total': total,
        'filles': filles,
        'garcons': garcons,
        'taux': taux,
        'taux_f': taux_f,
        'taux_g': taux_g,
        'total_reussite': reussite_total,
        'filles_reussite': reussite_filles,
        'garcons_reussite': reussite_garcons,
        'max': max_moy,
        'min': min_moy,
        'moyenne': moy_generale,
        'indicateurs': {
            'fel': fel,
            'encou': encou,
            'th': th,
            'pass': passable,
            'insuff': insuff
        }
    }

def calculate_disciplines_stats(import_obj, classe, discipline_name):
    """
    Calcule les statistiques pour une discipline spécifique d'une classe
    """
    # Pour les disciplines, nous devons utiliser DonneesDetailleesEleves
    eleves_detailles = DonneesDetailleesEleves.objects.filter(
        import_fichier=import_obj,
        classe__icontains=classe.nom
    )
    
    # Si aucune discipline n'est spécifiée, tenter de récupérer la première disponible
    if not discipline_name:
        disciplines = get_disciplines_for_import(import_obj)
        if disciplines:
            discipline_name = disciplines[0]
        else:
            # Si aucune discipline trouvée, retourner des statistiques vides
            return {
                'total': 0, 'filles': 0, 'garcons': 0,
                'taux': 0, 'taux_f': 0, 'taux_g': 0,
                'total_reussite': 0, 'filles_reussite': 0, 'garcons_reussite': 0,
                'max': 0, 'min': 0, 'moyenne': 0,
                'indicateurs': {'tb': 0, 'bien': 0, 'abien': 0, 'pass': 0, 'insuf': 0, 'faible': 0}
            }
    
    # Clé pour la moyenne de la discipline
    moy_key = f"{discipline_name} Moy D"
    
    # Compter les élèves
    total = eleves_detailles.count()
    if total == 0:
        return {
            'total': 0, 'filles': 0, 'garcons': 0,
            'taux': 0, 'taux_f': 0, 'taux_g': 0,
            'total_reussite': 0, 'filles_reussite': 0, 'garcons_reussite': 0,
            'max': 0, 'min': 0, 'moyenne': 0,
            'indicateurs': {'tb': 0, 'bien': 0, 'abien': 0, 'pass': 0, 'insuf': 0, 'faible': 0}
        }
    
    # Compter par sexe
    filles = 0
    garcons = 0
    
    # Moyennes et réussite
    moyennes = []
    min_moy = float('inf')
    max_moy = float('-inf')
    
    # Compteurs pour réussite
    reussite_total = 0
    reussite_filles = 0
    reussite_garcons = 0
    
    # Compteurs pour indicateurs
    tb = 0  # Très bien (>= 16)
    bien = 0  # Bien (>= 14 et < 16)
    abien = 0  # Assez bien (>= 12 et < 14)
    passable = 0  # Passable (>= 10 et < 12)
    insuf = 0  # Insuffisant (>= 8 et < 10)
    faible = 0  # Faible (< 8)
    
    for eleve in eleves_detailles:
        # Déterminer le sexe
        sexe = None
        if hasattr(eleve, 'get_sexe_normalise'):
            sexe = eleve.get_sexe_normalise()
        else:
            # Tentative manuelle de détermination du sexe
            if 'Sexe' in eleve.disciplines:
                sexe_val = str(eleve.disciplines['Sexe']).upper()
                if sexe_val.startswith('F'):
                    sexe = 'F'
                elif sexe_val.startswith('M') or sexe_val.startswith('H'):
                    sexe = 'M'
        
        if sexe == 'F':
            filles += 1
        else:
            garcons += 1
        
        # Vérifier si la discipline existe
        if moy_key in eleve.disciplines and eleve.disciplines[moy_key]:
            try:
                # Convertir la moyenne en float
                moyenne = float(str(eleve.disciplines[moy_key]).replace(',', '.'))
                moyennes.append(moyenne)
                
                # Min/Max
                min_moy = min(min_moy, moyenne)
                max_moy = max(max_moy, moyenne)
                
                # Réussite
                if moyenne >= 10:
                    reussite_total += 1
                    if sexe == 'F':
                        reussite_filles += 1
                    else:
                        reussite_garcons += 1
                
                # Indicateurs
                if moyenne >= 16:
                    tb += 1
                elif moyenne >= 14:
                    bien += 1
                elif moyenne >= 12:
                    abien += 1
                elif moyenne >= 10:
                    passable += 1
                elif moyenne >= 8:
                    insuf += 1
                else:
                    faible += 1
            except (ValueError, TypeError):
                pass
    
    # Calculer la moyenne de discipline
    moy_generale = sum(moyennes) / len(moyennes) if moyennes else 0
    
    # Calculer les taux de réussite
    taux = round((reussite_total / total) * 100) if total > 0 else 0
    taux_f = round((reussite_filles / filles) * 100) if filles > 0 else 0
    taux_g = round((reussite_garcons / garcons) * 100) if garcons > 0 else 0
    
    # Si aucune moyenne n'a été trouvée
    if not moyennes:
        min_moy = 0
        max_moy = 0
    
    return {
        'total': total,
        'filles': filles,
        'garcons': garcons,
        'taux': taux,
        'taux_f': taux_f,
        'taux_g': taux_g,
        'total_reussite': reussite_total,
        'filles_reussite': reussite_filles,
        'garcons_reussite': reussite_garcons,
        'max': max_moy,
        'min': min_moy,
        'moyenne': moy_generale,
        'indicateurs': {
            'tb': tb,
            'bien': bien,
            'abien': abien,
            'pass': passable,
            'insuf': insuf,
            'faible': faible
        }
    }

def generate_statistics_pdf(request, type_stats='moyennes', import_id=None, niveau_id=None, classe_id=None, discipline_name=None):
    """
    Génère un PDF avec les statistiques des moyennes ou disciplines
    :param type_stats: 'moyennes' ou 'disciplines'
    :param import_id: ID de l'importation à analyser
    :param niveau_id: ID du niveau à filtrer (optionnel)
    :param classe_id: ID de la classe à filtrer (optionnel)
    :param discipline_name: Nom de la discipline pour le type 'disciplines' (optionnel)
    """
    # Récupérer l'établissement actif
    etablissement = Etablissement.objects.first()
    
    # Vérifier les paramètres obligatoires
    if not import_id:
        return HttpResponse("Import ID est requis", status=400)
    
    # Récupérer l'objet ImportFichier
    try:
        import_obj = ImportFichier.objects.get(id=import_id)
    except ImportFichier.DoesNotExist:
        return HttpResponse("Import non trouvé", status=404)
    
    # Préparer les filtres
    filters = {'import_fichier_id': import_id}
    if niveau_id:
        filters['niveau_id'] = niveau_id
    if classe_id:
        filters['classe_obj_id'] = classe_id
    
    # Récupérer les données
    donnees_moyennes = DonneesMoyennesEleves.objects.filter(**filters)
    
    # Si aucune donnée, retourner une erreur
    if not donnees_moyennes.exists():
        return HttpResponse("Aucune donnée trouvée pour les filtres spécifiés", status=404)
    
    # Récupérer les classes et niveaux concernés
    if classe_id:
        classes = Classe.objects.filter(id=classe_id)
    elif niveau_id:
        classes = Classe.objects.filter(niveau_id=niveau_id)
    else:
        # Récupérer les classes concernées par l'importation
        classes_ids = donnees_moyennes.values_list('classe_obj_id', flat=True).distinct()
        classes = Classe.objects.filter(id__in=classes_ids)
    
    if niveau_id:
        niveaux = Niveau.objects.filter(id=niveau_id)
    else:
        # Récupérer les niveaux concernés par l'importation
        niveau_ids = classes.values_list('niveau_id', flat=True).distinct()
        niveaux = Niveau.objects.filter(id__in=niveau_ids)
    
    # Créer un tampon de mémoire pour le PDF
    buffer = BytesIO()
    
    # Créer le document PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    # Styles pour le document
    styles = getSampleStyleSheet()
    center_style = ParagraphStyle(
        name='Center', 
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=10
    )
    
    title_style = ParagraphStyle(
        name='Title', 
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontSize=16,
        textColor=colors.navy
    )
    
    # Éléments à ajouter au PDF
    elements = []
    
    # Titre du document
    if type_stats == 'moyennes':
        title = "STATISTIQUES DES MOYENNES GENERALES DU PREMIER SEMESTRE PAR CLASSE ET NIVEAU"
    else:
        # Pour disciplines, récupérer le nom de la discipline si fourni
        if not discipline_name:
            # Tenter de récupérer la première discipline disponible
            disciplines = get_disciplines_for_import(import_obj)
            if disciplines:
                discipline_name = disciplines[0]
            else:
                discipline_name = "MATHS"  # Par défaut
        
        title = f"STATISTIQUES DES MOYENNES SEMESTRE 1 {discipline_name} PAR CLASSE ET NIVEAU"
    
    # En-tête
    elements.append(Paragraph("Inspection d'Académie de Louga", center_style))
    elements.append(Paragraph("Inspection de l'Education et de la Formation de Louga", center_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Établissement et année scolaire - en ligne avec alignement différent
    data = [[Paragraph(f"<b>{etablissement.nom}</b>", styles['Normal']), 
            Paragraph(f"Année Scolaire : <b>{etablissement.annee_scolaire_active}</b>", styles['Normal'])]]
    
    header_table = Table(data, colWidths=[doc.width/2.0]*2)
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(header_table)
    
    # Titre principal
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Préparer les données pour le tableau
    table_data = []
    
    # En-têtes du tableau
    # Ajustement pour correspondre exactement aux exemples
    if type_stats == 'moyennes':
        headers_row1 = [
            'EFFECTIFS', '', '', 
            'MOYENNES >=10', '', '', 
            'POURCENTAGES >=10', '', '', 
            'INDICATEURS DE PERFORMANCES', '', '', '', ''
        ]
        
        headers_row2 = [
            'CLASSE | NIVEAU', 'TOTAL', 'FILLES', 'GARÇONS',
            'T', 'F', 'G',
            'TOT', 'FIL', 'GAR',
            'MAX', 'MIN', 'MOY G',
            'FEL', 'ENCOU', 'TH', 'PASS', 'Insuff'
        ]
    else:
        headers_row1 = [
            'EFFECTIFS', '', '', 
            'POURCENTAGES >=10', '', '', 
            'MOYENNES >=10', '', '', 
            'INDICATEURS DE PERFORMANCES', '', '', '', '', ''
        ]
        
        headers_row2 = [
            'CLASSE | NIVEAU', 'TOTAL', 'FILLES', 'GARÇONS',
            'T', 'F', 'G',
            'TOT', 'FIL', 'GAR',
            'MAX', 'MIN', 'MOY G',
            'TB', 'BIEN', 'ABIEN', 'PASS', 'INSUF', 'FAIBLE'
        ]
    
    # Ajout du premier en-tête avec span des colonnes
    table_data.append(headers_row1)
    table_data.append(headers_row2)
    
    # Analyser les données par classe
    class_stats = []
    for classe in classes:
        if type_stats == 'moyennes':
            stats = calculate_moyennes_stats(donnees_moyennes, classe)
            
            # Données pour le tableau, format selon l'exemple
            table_data.append([
                classe.nom,
                stats['total'],
                stats['filles'],
                stats['garcons'],
                stats['total_reussite'],
                stats['filles_reussite'],
                stats['garcons_reussite'],
                f"{stats['taux']}%",
                f"{stats['taux_f']}%",
                f"{stats['taux_g']}%",
                format_float(stats['max']),
                format_float(stats['min']),
                format_float(stats['moyenne']),
                stats['indicateurs']['fel'],
                stats['indicateurs']['encou'],
                stats['indicateurs']['th'],
                stats['indicateurs']['pass'],
                stats['indicateurs']['insuff']
            ])
        else:
            stats = calculate_disciplines_stats(import_obj, classe, discipline_name)
            
            # Données pour le tableau, format selon l'exemple
            table_data.append([
                classe.nom,
                stats['total'],
                stats['filles'],
                stats['garcons'],
                f"{stats['taux']}%",
                f"{stats['taux_f']}%",
                f"{stats['taux_g']}%",
                stats['total_reussite'],
                stats['filles_reussite'],
                stats['garcons_reussite'],
                format_float(stats['max']),
                format_float(stats['min']),
                format_float(stats['moyenne']),
                stats['indicateurs']['tb'],
                stats['indicateurs']['bien'],
                stats['indicateurs']['abien'],
                stats['indicateurs']['pass'],
                stats['indicateurs']['insuf'],
                stats['indicateurs']['faible']
            ])
        
        # Stocker les statistiques pour l'agrégation par niveau
        stats['classe'] = classe
        class_stats.append(stats)
    
    # Analyser les données par niveau
    niveau_stats = []
    for niveau in niveaux:
        # Filtrer les statistiques des classes de ce niveau
        niveau_classes_stats = [s for s in class_stats if s['classe'].niveau_id == niveau.id]
        
        if niveau_classes_stats:
            stats = aggregate_stats(niveau_classes_stats, type_stats)
            
            if type_stats == 'moyennes':
                # Données pour le tableau, format selon l'exemple
                table_data.append([
                    niveau.nom,
                    stats['total'],
                    stats['filles'],
                    stats['garcons'],
                    stats['total_reussite'],
                    stats['filles_reussite'],
                    stats['garcons_reussite'],
                    f"{stats['taux']}%",
                    f"{stats['taux_f']}%",
                    f"{stats['taux_g']}%",
                    format_float(stats['max']),
                    format_float(stats['min']),
                    format_float(stats['moyenne']),
                    stats['indicateurs']['fel'],
                    stats['indicateurs']['encou'],
                    stats['indicateurs']['th'],
                    stats['indicateurs']['pass'],
                    stats['indicateurs']['insuff']
                ])
            else:
                # Données pour le tableau, format selon l'exemple
                table_data.append([
                    niveau.nom,
                    stats['total'],
                    stats['filles'],
                    stats['garcons'],
                    f"{stats['taux']}%",
                    f"{stats['taux_f']}%",
                    f"{stats['taux_g']}%",
                    stats['total_reussite'],
                    stats['filles_reussite'],
                    stats['garcons_reussite'],
                    format_float(stats['max']),
                    format_float(stats['min']),
                    format_float(stats['moyenne']),
                    stats['indicateurs']['tb'],
                    stats['indicateurs']['bien'],
                    stats['indicateurs']['abien'],
                    stats['indicateurs']['pass'],
                    stats['indicateurs']['insuf'],
                    stats['indicateurs']['faible']
                ])
            
            # Stocker les statistiques pour le total général
            niveau_stats.append(stats)
    
    # Total général
    if niveau_stats:
        total_stats = aggregate_stats(niveau_stats, type_stats)
        
        if type_stats == 'moyennes':
            table_data.append([
                'TOTAL',
                total_stats['total'],
                total_stats['filles'],
                total_stats['garcons'],
                total_stats['total_reussite'],
                total_stats['filles_reussite'],
                total_stats['garcons_reussite'],
                f"{total_stats['taux']}%",
                f"{total_stats['taux_f']}%",
                f"{total_stats['taux_g']}%",
                format_float(total_stats['max']),
                format_float(total_stats['min']),
                format_float(total_stats['moyenne']),
                total_stats['indicateurs']['fel'],
                total_stats['indicateurs']['encou'],
                total_stats['indicateurs']['th'],
                total_stats['indicateurs']['pass'],
                total_stats['indicateurs']['insuff']
            ])
        else:
            table_data.append([
                'TOTAL',
                total_stats['total'],
                total_stats['filles'],
                total_stats['garcons'],
                f"{total_stats['taux']}%",
                f"{total_stats['taux_f']}%",
                f"{total_stats['taux_g']}%",
                total_stats['total_reussite'],
                total_stats['filles_reussite'],
                total_stats['garcons_reussite'],
                format_float(total_stats['max']),
                format_float(total_stats['min']),
                format_float(total_stats['moyenne']),
                total_stats['indicateurs']['tb'],
                total_stats['indicateurs']['bien'],
                total_stats['indicateurs']['abien'],
                total_stats['indicateurs']['pass'],
                total_stats['indicateurs']['insuf'],
                total_stats['indicateurs']['faible']
            ])
    
    # Ajustement des largeurs de colonnes pour améliorer la présentation
    col_widths = [1.3*cm]  # Première colonne (CLASSE | NIVEAU)
    
    # Les 3 colonnes EFFECTIFS
    col_widths.extend([0.9*cm] * 3)
    
    # Les 3 colonnes MOYENNES/POURCENTAGES >=10
    col_widths.extend([0.9*cm] * 3)
    
    # Les 3 colonnes POURCENTAGES/MOYENNES >=10
    col_widths.extend([0.9*cm] * 3)
    
    # Les 3 colonnes MAX, MIN, MOY G
    col_widths.extend([0.9*cm] * 3)
    
    # Les colonnes d'indicateurs (5 ou 6 selon le type)
    if type_stats == 'moyennes':
        col_widths.extend([0.9*cm] * 5)
    else:
        col_widths.extend([0.9*cm] * 6)
    
    # Créer le tableau
    table = Table(table_data, colWidths=col_widths)
    
    # Style du tableau
    table_style = TableStyle([
        # Fond bleu clair pour les en-têtes
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('BACKGROUND', (0, 1), (-1, 1), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 1), colors.black),
        
        # Alignement centré pour toutes les cellules
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Police en gras pour les en-têtes
        ('FONTNAME', (0, 0), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 1), 9),
        
        # Espacement des cellules
        ('BOTTOMPADDING', (0, 0), (-1, 1), 5),
        ('TOPPADDING', (0, 0), (-1, 1), 5),
        
        # Bordures pour toutes les cellules
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        
        # Fond bleu clair pour la ligne TOTAL
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightblue),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        
        # Style pour les niveaux
        # Les lignes des niveaux sont après les classes mais avant le total
        # Leur position dépend du nombre de classes
    ])
    
    # Fusion des cellules pour les groupes dans l'en-tête
    # Effectifs (3 colonnes)
    table_style.add('SPAN', (0, 0), (3, 0))
    
    # MOYENNES/POURCENTAGES >=10 (3 colonnes)
    table_style.add('SPAN', (4, 0), (6, 0))
    
    # POURCENTAGES/MOYENNES >=10 (3 colonnes)
    table_style.add('SPAN', (7, 0), (9, 0))
    
    # INDICATEURS DE PERFORMANCES (5 ou 6 colonnes selon le type)
    if type_stats == 'moyennes':
        table_style.add('SPAN', (10, 0), (17, 0))
    else:
        table_style.add('SPAN', (10, 0), (18, 0))
    
    # Appliquer des styles pour les lignes de niveau
    num_classes = len(classes)
    for i in range(len(niveaux)):
        niveau_row = num_classes + 2 + i  # +2 pour les deux lignes d'en-tête
        table_style.add('BACKGROUND', (0, niveau_row), (-1, niveau_row), colors.lightgrey)
        table_style.add('FONTNAME', (0, niveau_row), (-1, niveau_row), 'Helvetica-Bold')
    
    # Appliquer le style au tableau
    table.setStyle(table_style)
    
    # Ajouter le tableau au document
    elements.append(table)
    
    # Ajouter le pied de page
    elements.append(Spacer(1, 0.5*inch))
    
    # Pied de page avec informations de génération
    footer_data = [[
        Paragraph("© Créé par SAAL", styles['Normal']),
        Paragraph(f"Généré le {timezone.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal'])
    ]]
    
    footer_table = Table(footer_data, colWidths=[doc.width/2.0]*2)
    footer_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(footer_table)
    
    # Construire le document
    doc.build(elements)
    
    # Récupérer le contenu du buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Créer la réponse HTTP avec le PDF
    response = HttpResponse(pdf, content_type='application/pdf')
    
    # Déterminer le nom du fichier de téléchargement
    if type_stats == 'moyennes':
        filename = f"Statistiques_Moyennes_S1_{timezone.now().strftime('%Y%m%d')}.pdf"
    else:
        discipline_short = discipline_name if discipline_name else "Discipline"
        filename = f"Statistiques_{discipline_short}_S1_{timezone.now().strftime('%Y%m%d')}.pdf"
    
    # Définir les en-têtes de réponse
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response
