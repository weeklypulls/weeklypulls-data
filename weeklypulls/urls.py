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
from django.conf.urls import url, include
from django.contrib import admin
from weeklypulls.apps.series import views as series_views
from weeklypulls.apps.comics import views as comic_views

urlpatterns = [
    url(r'^', include(series_views.router.urls)),
    url(r'^admin/', admin.site.urls),
    url(
        r'^comics/week/([0-9]{4}\-[0-9]{2}\-[0-9]{2})/$',
        comic_views.comic_week),
]
