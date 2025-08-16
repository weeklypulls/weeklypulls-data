import arrow
from django.db import models
from django.utils import timezone
from datetime import timedelta


class ComicVineCacheModel(models.Model):
    """Abstract base model for ComicVine API cached data"""

    # Cache metadata
    last_updated = models.DateTimeField(auto_now=True)
    cache_expires = models.DateTimeField()

    # API status tracking
    api_fetch_failed = models.BooleanField(default=False)
    api_fetch_failure_count = models.IntegerField(default=0)
    api_last_failure = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def is_cache_expired(self):
        """Check if cached data is expired"""
        return timezone.now() > self.cache_expires

    def mark_api_failure(self):
        """Mark that API fetch failed"""
        self.api_fetch_failed = True
        self.api_fetch_failure_count += 1
        self.api_last_failure = timezone.now()
        self.save()

    def reset_api_failure(self):
        """Reset API failure status"""
        self.api_fetch_failed = False
        self.api_fetch_failure_count = 0
        self.api_last_failure = None
        self.save()


class ComicVineVolume(ComicVineCacheModel):
    """Cache for ComicVine volume (series) data"""

    cv_id = models.IntegerField(unique=True, primary_key=True)
    name = models.CharField(max_length=500)
    start_year = models.IntegerField(null=True, blank=True)
    count_of_issues = models.IntegerField(default=0)

    class Meta:
        db_table = "comicvine_volumes"
        verbose_name_plural = "ComicVine Volumes"

    def __str__(self):
        return f"{self.name} ({self.start_year})" if self.start_year else self.name


class ComicVineIssue(ComicVineCacheModel):
    """Cache for ComicVine issue data"""

    cv_id = models.IntegerField(unique=True, primary_key=True)
    name = models.CharField(max_length=500, null=True, blank=True)  # Issue title
    number = models.CharField(
        max_length=50, null=True, blank=True
    )  # Issue number (can be alphanumeric)

    # Dates
    cover_date = models.DateField(null=True, blank=True)  # Date on the cover
    store_date = models.DateField(null=True, blank=True)  # Date went on sale

    # Volume relationship
    volume = models.ForeignKey(
        ComicVineVolume, on_delete=models.CASCADE, related_name="issues"
    )

    # Content fields
    description = models.TextField(null=True, blank=True)  # Long description
    summary = models.TextField(null=True, blank=True)  # Short description
    aliases = models.TextField(null=True, blank=True)  # Alternative names

    # API metadata
    api_url = models.URLField(null=True, blank=True)
    site_url = models.URLField(null=True, blank=True)
    date_added = models.DateTimeField(null=True, blank=True)  # When added to CV
    date_last_updated = models.DateTimeField(null=True, blank=True)  # Last CV update

    # Cover image URLs (different sizes from ComicVine)
    image_icon_url = models.URLField(null=True, blank=True)  # Square avatar
    image_thumbnail_url = models.URLField(null=True, blank=True)  # Scale avatar
    image_tiny_url = models.URLField(null=True, blank=True)  # Square mini
    image_small_url = models.URLField(null=True, blank=True)  # Scale small
    image_medium_url = models.URLField(null=True, blank=True)  # Scale medium
    image_screen_url = models.URLField(null=True, blank=True)  # Screen medium
    image_super_url = models.URLField(null=True, blank=True)  # Scale large
    image_large_screen_url = models.URLField(null=True, blank=True)  # Screen kubrick
    image_original_url = models.URLField(null=True, blank=True)  # Original size

    class Meta:
        db_table = "comicvine_issues"
        verbose_name_plural = "ComicVine Issues"
        ordering = ["volume", "store_date", "cover_date", "number"]
        indexes = [
            models.Index(fields=["volume", "store_date"]),
            models.Index(fields=["volume", "number"]),
            models.Index(fields=["store_date"]),
        ]

    def __str__(self):
        volume_name = self.volume.name if self.volume else "Unknown Volume"
        number_str = f" #{self.number}" if self.number else ""
        name_str = f": {self.name}" if self.name else ""
        return f"{volume_name}{number_str}{name_str}"


class ComicVineCacheWeek(ComicVineCacheModel):
    """Tracks priming of ComicVine issues for a given week (Monday start).

    Use week_start as the canonical key (Monday of that ISO week). When
    cache_expires is in the future, the week is considered fresh and the
    Weeks endpoint can skip re-priming from the API.
    """

    week_start = models.DateField(unique=True)

    class Meta:
        db_table = "comicvine_weeks"
        verbose_name = "ComicVine Weekly Cache"
        verbose_name_plural = "ComicVine Weekly Caches"

    def __str__(self):
        return f"Week starting {self.week_start} (expires {self.cache_expires:%Y-%m-%d %H:%M})"
