from django.contrib import admin
from django.urls import include, path

urlpatterns = [path("admin/", admin.site.urls), path("", include("recipes.urls"))]
handler400 = "recipes.views.bad_request"
handler404 = "recipes.views.not_found"
handler500 = "recipes.views.server_error"
