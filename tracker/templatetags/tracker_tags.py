from django import template

from tracker.permissions import is_superuser_role

register = template.Library()
register.filter("is_superuser_role", is_superuser_role)


@register.inclusion_tag("tracker/partials/stars_display.html")
def stars_display(rating, size="md"):
    if rating is not None:
        try:
            rating = round(float(rating), 1)
        except (TypeError, ValueError):
            rating = None
    stars = []
    for i in range(1, 6):
        if rating and rating >= i:
            stars.append("full")
        elif rating and rating >= i - 0.5:
            stars.append("half")
        else:
            stars.append("empty")
    return {"stars": stars, "rating": rating, "size": size}


@register.filter
def get_item(dictionary, key):
    """Allow dict lookups by variable key in templates: my_dict|get_item:key.
    Tolerates a non-dict (e.g. an undefined var resolving to '') so a missing
    context variable renders as empty rather than raising."""
    if hasattr(dictionary, "get"):
        return dictionary.get(key)
    return None
