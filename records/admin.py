from django.contrib import admin

from .models import DigitalRecord, RecentSearch, RecordDocument, SavedItem


class SavedItemInline(admin.TabularInline):
    model = SavedItem
    extra = 0
    autocomplete_fields = ("program", "event", "promotion")


class RecentSearchInline(admin.TabularInline):
    model = RecentSearch
    extra = 0
    readonly_fields = ("query", "created_at")
    can_delete = False


class RecordDocumentInline(admin.TabularInline):
    model = RecordDocument
    extra = 0


@admin.register(DigitalRecord)
class DigitalRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")
    search_fields = ("user__email",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (SavedItemInline, RecentSearchInline, RecordDocumentInline)
