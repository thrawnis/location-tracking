from django.contrib import admin

from .models import Item, ItemReview, Location, OsmSearchCache, Visit


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
    list_display = ("name", "location")
    search_fields = ("name", "location__name")


@admin.register(ItemReview)
class ItemReviewAdmin(admin.ModelAdmin):
    list_display = ("item", "user", "rating", "updated_at")
    list_filter = ("rating",)
    search_fields = ("item__name", "user__username")


@admin.register(OsmSearchCache)
class OsmSearchCacheAdmin(admin.ModelAdmin):
    list_display = ("query", "center_lat", "center_lng", "radius_m", "fetched_at")
    list_filter = ("radius_m",)
    search_fields = ("query",)
    readonly_fields = ("fetched_at",)


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("location", "date", "user")
    list_filter = ("date",)
