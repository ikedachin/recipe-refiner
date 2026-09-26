from django.core.exceptions import ValidationError
from django.db import models


class Recipe(models.Model):
    title = models.CharField(max_length=200)
    original_text = models.TextField()
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]

    def __str__(self) -> str:
        return self.title


class RecipeRevision(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="revisions")
    parent_revision = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    request_text = models.TextField()
    provider = models.CharField(max_length=20)
    model_name = models.CharField(max_length=200)
    api_style = models.CharField(max_length=30)
    result_json = models.JSONField()
    result_text = models.TextField()
    confirmation_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def clean(self) -> None:
        if self.parent_revision_id:
            if self.parent_revision_id == self.pk:
                raise ValidationError("Revision自身を親にはできません。")
            if self.parent_revision.recipe_id != self.recipe_id:
                raise ValidationError("親Revisionは同じレシピに属する必要があります。")

    def __str__(self) -> str:
        return f"{self.recipe.title} / Revision #{self.pk}"
