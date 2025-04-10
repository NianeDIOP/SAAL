from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('configuration/', views.configuration, name='configuration'),
    path('configuration/niveau/<int:niveau_id>/delete/', views.niveau_delete, name='niveau_delete'),
    path('configuration/classe/<int:classe_id>/delete/', views.classe_delete, name='classe_delete'),
    
    # Semestre 1
    path('semestre1/', views.semestre1_accueil, name='semestre1_accueil'),
    path('semestre1/importation/', views.semestre1_importation, name='semestre1_importation'),
    path('semestre1/importation/<int:import_id>/', views.semestre1_importation_detail, name='semestre1_importation_detail'),
    path('semestre1/importation/<int:import_id>/delete/', views.semestre1_importation_delete, name='semestre1_importation_delete'),
    path('semestre1/analyse-moyennes/', views.semestre1_analyse_moyennes, name='semestre1_analyse_moyennes'),
    path('semestre1/analyse-disciplines/', views.semestre1_analyse_disciplines, name='semestre1_analyse_disciplines'),
    path('semestre1/generer-pdf/', views.semestre1_generer_pdf, name='semestre1_generer_pdf'),
   
]