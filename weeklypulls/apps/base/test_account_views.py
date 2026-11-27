"""The account page's endpoints: details, password change, export, delete."""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from weeklypulls.apps.comicvine.models import ComicVinePublisher, ComicVineVolume
from weeklypulls.apps.pull_lists.models import PullList
from weeklypulls.apps.pulls.models import Pull


@pytest.fixture
def user(api_client):
    user = User.objects.get(username="user1")
    user.email = "user1@example.com"
    user.save()
    return user


@pytest.fixture
def pull(user):
    publisher = ComicVinePublisher.objects.create(cv_id=31, name="Marvel")
    ComicVineVolume.objects.create(
        cv_id=1000,
        name="Test Series",
        publisher=publisher,
        cache_expires="2100-01-01T00:00Z",
    )
    pull_list = PullList.objects.create(title="Mine", owner=user)
    return Pull.objects.create(
        owner=user, pull_list=pull_list, series_id=1000, read=[9002, 9001]
    )


def test_user_details_read_only(api_client, user):
    response = api_client.get("/auth/user/")
    assert response.status_code == 200
    assert response.data["username"] == "user1"
    assert response.data["email"] == "user1@example.com"

    api_client.patch(
        "/auth/user/", {"username": "renamed", "email": "x@example.com"}, format="json"
    )
    user.refresh_from_db()
    assert (user.username, user.email) == ("user1", "user1@example.com")


def test_password_change_needs_old_password(api_client, user):
    new = {"new_password1": "fresh-password-123", "new_password2": "fresh-password-123"}
    response = api_client.post("/auth/password/change/", new, format="json")
    assert response.status_code == 400
    assert "old_password" in response.data

    response = api_client.post(
        "/auth/password/change/", {**new, "old_password": "password1"}, format="json"
    )
    assert response.status_code == 200, response.data
    user.refresh_from_db()
    assert user.check_password("fresh-password-123")


def test_export(api_client, user, pull):
    response = api_client.get("/account/export/")
    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    data = response.data
    assert data["account"]["email"] == "user1@example.com"
    [pull_list] = data["pull_lists"]
    assert pull_list["title"] == "Mine"
    [exported] = pull_list["pulls"]
    assert exported["series_name"] == "Test Series"
    assert exported["read_comicvine_issue_ids"] == [9001, 9002]


def test_export_only_includes_own_data(api_client, user, pull):
    other = User.objects.create_user("other", "other@example.com", "pw-123456789")
    PullList.objects.create(title="Theirs", owner=other)
    titles = [
        pl["title"] for pl in api_client.get("/account/export/").data["pull_lists"]
    ]
    assert titles == ["Mine"]


def test_delete_requires_password(api_client, user, pull):
    response = api_client.post("/account/delete/", {"password": "wrong"}, format="json")
    assert response.status_code == 400
    assert User.objects.filter(pk=user.pk).exists()


def test_delete_removes_everything(api_client, user, pull):
    response = api_client.post(
        "/account/delete/", {"password": "password1"}, format="json"
    )
    assert response.status_code == 204
    assert not User.objects.filter(pk=user.pk).exists()
    assert not PullList.objects.filter(owner_id=user.pk).exists()
    assert not Pull.objects.filter(owner_id=user.pk).exists()
    assert not Token.objects.filter(user_id=user.pk).exists()
    # The old token no longer works.
    assert api_client.get("/pull-lists/").status_code == 401


def test_account_endpoints_need_login():
    from rest_framework.test import APIClient

    client = APIClient()
    assert client.get("/account/export/").status_code == 401
    assert (
        client.post("/account/delete/", {"password": "x"}, format="json").status_code
        == 401
    )
