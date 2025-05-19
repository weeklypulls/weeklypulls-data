"""weeklypulls URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.contrib import admin
from weeklypulls.apps.pulls import views as pull_views
from weeklypulls.apps.pull_lists import views as pull_list_views
from rest_framework.authtoken import views as authtoken_views

urlpatterns = [
    path('', include(pull_list_views.router.urls)),
    path('', include(pull_views.router.urls)),
    path('admin/', admin.site.urls),
    path('api-token-auth/', authtoken_views.obtain_auth_token),
    path('auth/', include('dj_rest_auth.urls')),
    path('auth/registration/', include('dj_rest_auth.registration.urls'))
]
