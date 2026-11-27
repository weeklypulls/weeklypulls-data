"""Smoke tests for the endpoints the client uses. ComicVine is never called."""

import datetime
from datetime import timedelta

import pytest
from django.utils import timezone

from weeklypulls.apps.comicvine.models import (
    ComicVineIssue,
    ComicVinePublisher,
    ComicVineVolume,
)
from weeklypulls.apps.pull_lists.models import PullList
from weeklypulls.apps.pulls.models import Pull


@pytest.fixture(autouse=True)
def no_comicvine(settings):
    settings.COMICVINE_API_KEY = ""


@pytest.fixture
def user(api_client):
    from django.contrib.auth.models import User

    return User.objects.get(username="user1")


@pytest.fixture
def volume():
    publisher = ComicVinePublisher.objects.create(cv_id=31, name="Marvel")
    return ComicVineVolume.objects.create(
        cv_id=1000,
        name="Test Series",
        start_year=2024,
        count_of_issues=2,
        publisher=publisher,
        cache_expires=timezone.now() + timedelta(days=1),
    )


@pytest.fixture
def issues(volume):
    week = datetime.date(2026, 11, 25)  # a Wednesday
    return [
        ComicVineIssue.objects.create(
            cv_id=5000 + n,
            number=str(n),
            name=f"Issue {n}",
            date=week + timedelta(days=7 * (n - 1)),
            volume=volume,
            cache_expires=timezone.now() + timedelta(days=1),
        )
        for n in (1, 2)
    ]


@pytest.fixture
def pull(user, volume):
    pull_list = PullList.objects.create(title="Main", owner=user)
    return Pull.objects.create(owner=user, pull_list=pull_list, series_id=volume.cv_id)


def test_requires_auth(client):
    assert client.get("/pulls/").status_code == 401


def test_pulls_list_annotates_series(api_client, pull):
    response = api_client.get("/pulls/")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["series_title"] == "Test Series"


def test_mark_read_and_unread_issues(api_client, pull, issues):
    response = api_client.get("/pulls/unread_issues/")
    assert response.status_code == 200
    assert {int(i["id"]) for i in response.json()["results"]} == {5001, 5002}

    response = api_client.post(f"/pulls/{pull.id}/mark_read/", {"issue_id": 5001})
    assert response.status_code == 200
    assert response.json()["read"] == [5001]

    response = api_client.get("/pulls/unread_issues/")
    assert [int(i["id"]) for i in response.json()["results"]] == [5002]


def test_mark_read_requires_issue_id(api_client, pull):
    response = api_client.post(f"/pulls/{pull.id}/mark_read/", {})
    assert response.status_code == 400


def test_week_returns_issues_in_range(api_client, pull, issues):
    response = api_client.get("/weeks/2026-11-25/?prime=false")
    assert response.status_code == 200
    body = response.json()
    assert body["week_of"] == "2026-11-23"
    assert [int(c["id"]) for c in body["comics"]] == [5001]


def test_week_rejects_bad_date(api_client):
    assert api_client.get("/weeks/not-a-date/").status_code == 400


def test_series_search_and_detail(api_client, volume, issues):
    response = api_client.get("/series/?q=test")
    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == volume.cv_id

    response = api_client.get(f"/series/{volume.cv_id}/")
    assert response.status_code == 200
    assert len(response.json()["comics"]) == 2


def test_other_users_cannot_see_pull(api_client, pull, django_user_model):
    from rest_framework.test import APIClient

    other = django_user_model.objects.create_user(username="other", password="pw")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="TOKEN " + other.auth_token.key)
    assert client.get("/pulls/").json()["count"] == 0
    assert client.get(f"/pulls/{pull.id}/").status_code == 404


def test_cannot_add_pull_to_someone_elses_list(api_client, django_user_model):
    other = django_user_model.objects.create_user(username="other", password="pw")
    their_list = PullList.objects.create(title="Theirs", owner=other)
    response = api_client.post(
        "/pulls/", {"pull_list_id": str(their_list.id), "series_id": 1}, format="json"
    )
    assert response.status_code == 400
    assert not Pull.objects.filter(pull_list=their_list).exists()


def test_create_pull(api_client, user, volume):
    my_list = PullList.objects.create(title="Mine", owner=user)
    response = api_client.post(
        "/pulls/",
        {"pull_list_id": str(my_list.id), "series_id": volume.cv_id},
        format="json",
    )
    assert response.status_code == 201
    assert response.json()["series_title"] == "Test Series"
