import arrow
from django.db import models
from django.utils import timezone
from datetime import timedelta


class ComicVineVolume(models.Model):
    """Cache for ComicVine volume (series) data"""
    cv_id = models.IntegerField(unique=True, primary_key=True)
    name = models.CharField(max_length=500)
    start_year = models.IntegerField(null=True, blank=True)
    
    # Cache metadata
    last_updated = models.DateTimeField(auto_now=True)
    cache_expires = models.DateTimeField()
    
    # API status tracking
    api_fetch_failed = models.BooleanField(default=False)
    api_fetch_failure_count = models.IntegerField(default=0)
    api_last_failure = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'comicvine_volumes'
        verbose_name_plural = "ComicVine Volumes"
    
    def __str__(self):
        return f"{self.name} ({self.start_year})" if self.start_year else self.name
    
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
