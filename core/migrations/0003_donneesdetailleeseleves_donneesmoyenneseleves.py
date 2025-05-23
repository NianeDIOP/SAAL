# Generated by Django 5.1.7 on 2025-04-02 10:14

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_importfichier_moyenneeleve_moyennediscipline'),
    ]

    operations = [
        migrations.CreateModel(
            name='DonneesDetailleesEleves',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100)),
                ('prenom', models.CharField(blank=True, max_length=100, null=True)),
                ('classe', models.CharField(blank=True, max_length=50, null=True)),
                ('disciplines', models.JSONField(blank=True, default=dict)),
                ('import_fichier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='donnees_detaillees', to='core.importfichier')),
            ],
            options={
                'verbose_name': 'Données détaillées élèves',
                'verbose_name_plural': 'Données détaillées élèves',
            },
        ),
        migrations.CreateModel(
            name='DonneesMoyennesEleves',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100)),
                ('prenom', models.CharField(blank=True, max_length=100, null=True)),
                ('classe', models.CharField(blank=True, max_length=50, null=True)),
                ('moyenne_generale', models.FloatField(null=True)),
                ('rang_classe', models.IntegerField(blank=True, null=True)),
                ('effectif_classe', models.IntegerField(blank=True, null=True)),
                ('donnees_additionnelles', models.JSONField(blank=True, default=dict)),
                ('import_fichier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='donnees_moyennes', to='core.importfichier')),
            ],
            options={
                'verbose_name': 'Données moyennes élèves',
                'verbose_name_plural': 'Données moyennes élèves',
                'ordering': ['-moyenne_generale'],
            },
        ),
    ]
