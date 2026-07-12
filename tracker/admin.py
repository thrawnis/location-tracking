from django.contrib import admin

from .models import (
    Collection, EmailVerification, GlutenFreeVote, Item, ItemReview, Location,
    LocationReview, OsmSearchCache, TermsAcceptance,
)


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "overall_rating", "created_by", "created_at")
    list_filter = ("gluten_free",)
    search_fields = ("name", "address")
    inlines = [ItemInline]


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


@admin.register(GlutenFreeVote)
class GlutenFreeVoteAdmin(admin.ModelAdmin):
    list_display = ("location", "user", "agrees", "updated_at")
    list_filter = ("agrees",)
    search_fields = ("location__name", "user__username")


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "verified", "verified_at", "last_sent_at")
    list_filter = ("verified",)
    search_fields = ("user__username", "user__email")


@admin.register(TermsAcceptance)
class TermsAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user", "version", "accepted_at", "ip_address")
    list_filter = ("version",)
    search_fields = ("user__username",)
