from django.urls import path

from . import views

app_name = "recipes"
urlpatterns = [
    path("", views.index, name="index"),
    path("history/", views.recipe_list, name="history"),
    path("favorites/", views.recipe_list, {"favorites": True}, name="favorites"),
    path("recipes/<int:recipe_id>/", views.recipe_detail, name="detail"),
    path("api/refine/", views.refine_api, name="refine"),
    path("api/refine/confirm/", views.confirm_api, name="confirm"),
    path("api/refine/<int:revision_id>/", views.refine_api, name="refine_revision"),
    path("api/recipes/<int:recipe_id>/refine/", views.refine_api, name="refine_original"),
    path("api/recipes/<int:recipe_id>/favorite/", views.favorite_api, name="favorite"),
    path("api/recipes/<int:recipe_id>/history/", views.history_api, name="history_api"),
]
