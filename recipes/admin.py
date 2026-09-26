from django.contrib import admin

from .models import Recipe, RecipeRevision


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("title", "is_favorite", "updated_at")
    search_fields = ("title", "original_text")
    list_filter = ("is_favorite",)


@admin.register(RecipeRevision)
class RecipeRevisionAdmin(admin.ModelAdmin):
    list_display = ("id", "recipe", "parent_revision", "provider", "model_name", "created_at")
    readonly_fields = ("created_at",)
