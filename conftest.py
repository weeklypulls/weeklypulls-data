import pytest
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture(autouse=True)
def clear_cache():
    # Rate-limit counters live in the cache; don't carry them between tests.
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def api_client(django_user_model):
    username = "user1"
    password = "password1"
    user = django_user_model.objects.create_user(username=username, password=password)
    client = APIClient()
    client.login(username=username, password=password)
    client.credentials(HTTP_AUTHORIZATION="TOKEN " + user.auth_token.key)
    return client
