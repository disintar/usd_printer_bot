from django.urls import path

from .views import healthcheck, home


urlpatterns = [
    path("", home, name="home"),
    path("healthz/", healthcheck, name="healthcheck"),
]
