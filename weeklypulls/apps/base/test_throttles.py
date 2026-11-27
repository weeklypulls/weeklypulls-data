"""Rate limits on the logged-out account endpoints."""

import pytest
from django.contrib.auth.models import User
from django.core import mail
from rest_framework.test import APIClient


@pytest.fixture
def rates(settings):
    def set_rates(**rates):
        settings.REST_FRAMEWORK = {
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": rates,
        }

    return set_rates


def post(client, path, data, ip="203.0.113.1"):
    return client.post(path, data, format="json", HTTP_X_REAL_IP=ip)


def test_login_limited_per_ip(rates):
    rates(login_ip="3/min")
    client = APIClient()
    for _ in range(3):
        r = post(client, "/auth/login/", {"username": "x", "password": "y"})
        assert r.status_code == 400
    r = post(client, "/auth/login/", {"username": "x", "password": "y"})
    assert r.status_code == 429
    # Another client isn't affected.
    r = post(client, "/auth/login/", {"username": "x", "password": "y"}, ip="1.2.3.4")
    assert r.status_code == 400


def test_login_limited_per_username_across_ips(rates):
    rates(login_id="2/hour")
    client = APIClient()
    for i in range(2):
        r = post(
            client,
            "/auth/login/",
            {"username": "Victim", "password": "y"},
            ip=f"10.0.0.{i}",
        )
        assert r.status_code == 400
    r = post(
        client, "/auth/login/", {"username": "victim", "password": "y"}, ip="10.0.0.9"
    )
    assert r.status_code == 429
    r = post(
        client, "/auth/login/", {"username": "other", "password": "y"}, ip="10.0.0.9"
    )
    assert r.status_code == 400


def test_old_token_endpoint_and_unslashed_routes_are_limited(rates):
    rates(login_ip="1/min")
    client = APIClient()
    assert (
        post(client, "/api-token-auth/", {"username": "x", "password": "y"}).status_code
        == 400
    )
    assert (
        post(client, "/auth/login", {"username": "x", "password": "y"}).status_code
        == 429
    )


def test_reset_emails_limited_per_address(rates):
    rates(password_reset_id="2/hour")
    User.objects.create_user("reader", "reader@example.com", "pw-123456789")
    client = APIClient()
    for i in range(2):
        r = post(
            client,
            "/auth/password/reset/",
            {"email": "reader@example.com"},
            ip=f"10.0.1.{i}",
        )
        assert r.status_code == 200
    r = post(
        client, "/auth/password/reset/", {"email": "READER@example.com"}, ip="10.0.1.9"
    )
    assert r.status_code == 429
    assert len(mail.outbox) == 2


def test_resend_limited(rates):
    rates(resend_email_id="1/hour")
    client = APIClient()
    assert (
        post(
            client, "/auth/registration/resend-email/", {"email": "a@example.com"}
        ).status_code
        == 200
    )
    assert (
        post(
            client, "/auth/registration/resend-email/", {"email": "a@example.com"}
        ).status_code
        == 429
    )


def test_regular_api_not_limited(rates, api_client):
    rates(login_ip="1/min")
    for _ in range(5):
        assert api_client.get("/pull-lists/").status_code == 200
