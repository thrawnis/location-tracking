from django.contrib import admin

from .models import (
    Collection, Item, ItemReview, Location, LocationReview, OsmSearchCache, Visit,
)


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0


class VisitInline(admin.TabularInline):
    model = Visit
    extra = 0


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "status", "overall_rating", "created_by", "created_at")
    list_filter = ("category", "status", "gluten_free")
    search_fields = ("name", "address")
    inlines = [ItemInline, VisitInline]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    search_fields = ("name",)
    filter_horizontal = ("locations",)


@admin.register(LocationReview)
class LocationReviewAdmin(admin.ModelAdmin):
    list_display = ("location", "user", "rating", "updated_at")
    list_filter = ("rating",)
    search_fields = ("location__name", "user__username")


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
