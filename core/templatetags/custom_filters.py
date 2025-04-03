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
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """Multiplie la valeur par l'argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
@stringfilter
def split(value, arg):
    """Divise une chaîne par un séparateur et renvoie une liste"""
    return value.split(arg)