from django.urls import path, include
from django.contrib import admin
from weeklypulls.apps.pulls import views as pull_views
from weeklypulls.apps.pull_lists import views as pull_list_views
from rest_framework.authtoken import views as authtoken_views

from weeklypulls.apps.base.health import health

urlpatterns = [
    path("health/", health),
    path("", include(pull_list_views.router.urls)),
    path("", include(pull_views.router.urls)),
    path("admin/", admin.site.urls),
    path("api-token-auth/", authtoken_views.obtain_auth_token),
    path("auth/", include("dj_rest_auth.urls")),
    path("auth/registration/", include("dj_rest_auth.registration.urls")),
]
