"""Sign-up, email verification, login and password reset through the API."""

import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from rest_framework.test import APIClient

FRONTEND = "https://frontend.test"
PASSWORD = "a-long-test-password-1"


@pytest.fixture(autouse=True)
def frontend(settings):
    settings.FRONTEND_URL = FRONTEND


@pytest.fixture
def client():
    return APIClient()


def link_in(message, path):
    match = re.search(rf"{re.escape(FRONTEND)}/{path}/(\S+)", message.body)
    assert match, message.body
    return match.group(1)


def verified_address(user):
    from allauth.account.models import EmailAddress

    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )


def register(client, username="newuser", email="New@Example.com"):
    return client.post(
        "/auth/registration/",
        {
            "username": username,
            "email": email,
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
        format="json",
    )


def login(client, username="newuser", password=PASSWORD):
    return client.post(
        "/auth/login/", {"username": username, "password": password}, format="json"
    )


def test_signup_requires_verification_before_login(client):
    response = register(client)
    assert response.status_code == 201, response.data
    assert "key" not in response.data

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["new@example.com"]
    assert message.subject.startswith("WeeklyPulls: ")
    key = link_in(message, "verify-email")

    # Neither login endpoint hands out a token yet.
    assert login(client).status_code == 400
    old = client.post(
        "/api-token-auth/",
        {"username": "newuser", "password": PASSWORD},
        format="json",
    )
    assert old.status_code == 400

    verify = client.post(
        "/auth/registration/verify-email/", {"key": key}, format="json"
    )
    assert verify.status_code == 200, verify.data

    response = login(client)
    assert response.status_code == 200, response.data
    user = User.objects.get(username="newuser")
    assert response.data["key"] == user.auth_token.key
    assert user.last_login is not None


def test_signup_requires_email(client):
    response = register(client, email="")
    assert response.status_code == 400
    assert "email" in response.data


def test_signup_rejects_verified_email(client):
    user = User.objects.create_user("owner", "taken@example.com", PASSWORD)
    verified_address(user)
    response = register(client, username="other", email="Taken@example.com")
    assert response.status_code == 400
    assert "email" in response.data


def test_unverified_email_cannot_be_squatted(client):
    # Someone signing up with an address they don't own doesn't block its
    # real owner; whoever verifies it gets it.
    assert (
        register(client, username="squatter", email="mine@example.com").status_code
        == 201
    )
    assert (
        register(client, username="owner", email="mine@example.com").status_code == 201
    )


def test_resend_verification(client):
    user = User.objects.create_user("waiting", "waiting@example.com", PASSWORD)
    from allauth.account.models import EmailAddress

    EmailAddress.objects.create(user=user, email=user.email, primary=True)
    response = client.post(
        "/auth/registration/resend-email/",
        {"email": "waiting@example.com"},
        format="json",
    )
    assert response.status_code == 200
    assert len(mail.outbox) == 1
    link_in(mail.outbox[0], "verify-email")


def test_password_reset(client):
    user = User.objects.create_user("reader", "reader@example.com", "old-password")

    response = client.post(
        "/auth/password/reset/", {"email": "reader@example.com"}, format="json"
    )
    assert response.status_code == 200, response.data
    assert len(mail.outbox) == 1
    uid, token = link_in(mail.outbox[0], "reset-password").split("/", 1)

    response = client.post(
        "/auth/password/reset/confirm/",
        {
            "uid": uid,
            "token": token,
            "new_password1": PASSWORD,
            "new_password2": PASSWORD,
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    user.refresh_from_db()
    assert user.check_password(PASSWORD)

    # The link only works once.
    again = client.post(
        "/auth/password/reset/confirm/",
        {
            "uid": uid,
            "token": token,
            "new_password1": "another-password-2",
            "new_password2": "another-password-2",
        },
        format="json",
    )
    assert again.status_code == 400


def test_password_reset_unknown_email_looks_the_same(client):
    response = client.post(
        "/auth/password/reset/", {"email": "nobody@example.com"}, format="json"
    )
    assert response.status_code == 200
    assert mail.outbox == []


def test_logout_revokes_token(client):
    user = User.objects.create_user("leaver", "leaver@example.com", PASSWORD)
    verified_address(user)
    key = login(client, "leaver").data["key"]
    client.credentials(HTTP_AUTHORIZATION=f"Token {key}")
    assert client.get("/pull-lists/").status_code == 200

    assert client.post("/auth/logout/").status_code == 200
    assert client.get("/pull-lists/").status_code == 401
