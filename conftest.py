import pytest
from rest_framework.test import APIClient, RequestsClient


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture
def api_client(django_user_model):
    username = "user1"
    password = "password1"
    user = django_user_model.objects.create_user(username=username, password=password)
    client = APIClient()
    client.login(username=username, password=password)
    client.credentials(HTTP_AUTHORIZATION="TOKEN " + user.auth_token.key)
    return client


@pytest.fixture
def requests_client(django_user_model):
    username = "user1"
    password = "password1"
    user = django_user_model.objects.create_user(username=username, password=password)
    client = RequestsClient()
    client.headers.update({"Authorization": f"TOKEN {user.auth_token.key}"})
    return client
