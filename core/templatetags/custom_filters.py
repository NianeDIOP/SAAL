from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Récupère un élément d'un dictionnaire par sa clé"""
    if not dictionary:
        return None
    return dictionary.get(key)

@register.filter
def div(value, arg):
    """Divise la valeur par l'argument"""
    try:
        return float(value) * 100 / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0
    
