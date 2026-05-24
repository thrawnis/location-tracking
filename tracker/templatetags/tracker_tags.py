from django import template

register = template.Library()


@register.inclusion_tag("tracker/partials/stars_display.html")
def stars_display(rating, size="md"):
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
def category_icon(category):
    icons = {
        "restaurant": "🍽️",
        "store": "🛍️",
        "attraction": "🎯",
        "other": "📍",
    }
    return icons.get(category, "📍")


@register.filter
def get_item(dictionary, key):
    """Allow dict lookups by variable key in templates: my_dict|get_item:key"""
    return dictionary.get(key)


@register.filter
def category_color(category):
    colors = {
        "restaurant": "indigo",
        "store": "emerald",
        "attraction": "violet",
        "other": "slate",
    }
    return colors.get(category, "slate")
