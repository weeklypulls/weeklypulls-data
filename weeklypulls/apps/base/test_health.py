from unittest import mock

from django.db.utils import OperationalError


def test_health_ok_without_auth(client):
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "no-cache" in response["Cache-Control"]


def test_health_503_when_database_unreachable(client):
    with mock.patch(
        "weeklypulls.apps.base.health.connection.cursor",
        side_effect=OperationalError("down"),
    ):
        response = client.get("/health/")
    assert response.status_code == 503


def test_health_skips_ssl_redirect_in_production(client, settings):
    # Mirrors production.py: Railway's checker uses plain HTTP and its own Host.
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_REDIRECT_EXEMPT = [r"^health/?$"]
    settings.ALLOWED_HOSTS = ["healthcheck.railway.app"]
    response = client.get("/health/", HTTP_HOST="healthcheck.railway.app")
    assert response.status_code == 200
    # Everything else still redirects to HTTPS.
    assert client.get("/pulls/", HTTP_HOST="healthcheck.railway.app").status_code == 301
