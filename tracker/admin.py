from django.contrib import admin

from .models import Item, Location, Visit


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0


class VisitInline(admin.TabularInline):
    model = Visit
    extra = 0


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "overall_rating", "created_by", "created_at")
    list_filter = ("category",)
    search_fields = ("name", "address")
    inlines = [ItemInline, VisitInline]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "rating")
    search_fields = ("name", "location__name")


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("location", "date", "user")
    list_filter = ("date",)
