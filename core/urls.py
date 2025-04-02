from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('configuration/', views.configuration, name='configuration'),
    
    # Semestre 1
    path('semestre1/', views.semestre1_accueil, name='semestre1_accueil'),
    path('semestre1/importation/', views.semestre1_importation, name='semestre1_importation'),
    path('semestre1/importation/<int:import_id>/', views.semestre1_importation_detail, name='semestre1_importation_detail'),
    path('semestre1/importation/<int:import_id>/delete/', views.semestre1_importation_delete, name='semestre1_importation_delete'),
    path('semestre1/analyse-moyennes/', views.semestre1_analyse_moyennes, name='semestre1_analyse_moyennes'),
]