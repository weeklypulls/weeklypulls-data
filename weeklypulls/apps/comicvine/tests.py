"""Checks that ComicVineService still maps Simyan's schemas onto our models."""

from datetime import timedelta

from django.utils import timezone
from simyan.schemas.issue import BasicIssue
from simyan.schemas.volume import Volume

from weeklypulls.apps.comicvine.models import (
    ComicVineIssue,
    ComicVinePublisher,
    ComicVineVolume,
)
from weeklypulls.apps.comicvine.services import ComicVineService

URL = "https://comicvine.gamespot.com/api/x/"
IMAGE = {
    key: f"https://comicvine.gamespot.com/a/{key}.jpg"
    for key in (
        "icon_url",
        "medium_url",
        "screen_url",
        "screen_large_url",
        "small_url",
        "super_url",
        "thumb_url",
        "tiny_url",
        "original_url",
    )
} | {"image_tags": "All Images"}


def _entry(id_, name):
    return {"id": id_, "name": name, "api_detail_url": URL, "site_detail_url": URL}


def test_volume_payload_updates_cache(settings):
    settings.COMICVINE_API_KEY = ""
    cv_volume = Volume.model_validate(
        {
            **_entry(1000, "Test Series"),
            "date_added": "2024-01-01 00:00:00",
            "date_last_updated": "2024-01-02 00:00:00",
            "image": IMAGE,
            "count_of_issues": 12,
            "publisher": _entry(31, "Marvel"),
            "start_year": "2024",
        }
    )

    volume = ComicVineService()._apply_cv_volume_payload(None, cv_volume)

    volume = ComicVineVolume.objects.get(cv_id=1000)
    assert volume.name == "Test Series"
    assert volume.start_year == 2024
    assert volume.count_of_issues == 12
    assert volume.publisher.name == "Marvel"


def test_issue_defaults_from_basic_issue(settings):
    settings.COMICVINE_API_KEY = ""
    volume = ComicVineVolume.objects.create(
        cv_id=1000,
        name="Test Series",
        publisher=ComicVinePublisher.objects.create(cv_id=31, name="Marvel"),
        cache_expires=timezone.now() + timedelta(days=1),
    )
    s_issue = BasicIssue.model_validate(
        {
            **_entry(5001, "Issue One"),
            "issue_number": "1",
            "cover_date": "2026-12-01",
            "store_date": "2026-11-25",
            "date_added": "2026-10-01 12:00:00",
            "date_last_updated": "2026-10-02 12:00:00",
            "image": IMAGE,
            "volume": _entry(1000, "Test Series"),
        }
    )

    defaults, store_date, _ = ComicVineService()._build_issue_defaults(s_issue, volume)
    ComicVineIssue.objects.update_or_create(cv_id=s_issue.id, defaults=defaults)

    issue = ComicVineIssue.objects.get(cv_id=5001)
    assert issue.number == "1"
    assert str(issue.date) == "2026-11-25"
    assert issue.date_added.tzinfo is not None
    assert issue.image_original_url.endswith("original_url.jpg")
    assert issue.image_large_screen_url.endswith("screen_large_url.jpg")
