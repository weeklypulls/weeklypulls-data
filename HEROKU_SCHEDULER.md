# ComicVine Data Fetching - Heroku Setup Guide

## Heroku Scheduler Setup

### 1. Add the Scheduler Add-on

```bash
heroku addons:create scheduler:standard
```

### 2. Configure the Scheduled Job

```bash
heroku addons:open scheduler
```

In the Heroku Scheduler dashboard, add a new job:

- **Command**: `python manage.py primecache --limit 180`
- **Frequency**: Daily at 02:00 UTC (low traffic time)
- **Dyno Size**: Standard-1X (or whatever your app uses)

### 3. Alternative: Use Heroku CLI

```bash
heroku addons:create scheduler:standard
heroku run python manage.py primecache --limit 180
```

## Command Options

### Basic Usage

```bash
# Fetch up to 180 API requests worth of data (smart refresh)
python manage.py primecache --limit 180

# Dry run to see what would be fetched
python manage.py primecache --limit 180 --dry-run

# Force refresh of volumes that have failed recently
python manage.py primecache --limit 180 --force-volumes
```

### Production Schedule Recommendations

**Daily Maintenance** (2 AM UTC):

```bash
python manage.py primecache --limit 180
```

**Weekly Deep Refresh** (Sunday 3 AM UTC):

```bash
python manage.py primecache --limit 180 --force-volumes
```

## Smart Refresh Strategy

The `primecache` command uses intelligent refresh logic:

### Volume Refresh Intervals

- **Recent series** (last 3 years): Refresh weekly
- **Older series** (4-10 years old): Refresh every 2 weeks
- **Very old series** (10+ years old): Refresh monthly

### Issue Data Priority

- **Recent series** (last 5 years): Prioritized for issue data fetching
- **Older series**: Filled in as API capacity allows

## API Rate Limiting Strategy

The command is designed to respect ComicVine's rate limits:

1. **Built-in Simyan rate limiting** (1 request per second)
2. **Additional 0.5s delay** between requests for safety
3. **Request counting** to stay under daily limits
4. **Prioritized fetching**:
   - Missing volumes first (rarely needed after conversion)
   - Expired volumes second (smart refresh intervals)
   - Issue data third (prioritizing recent series)

## Monitoring

### Heroku Logs

```bash
# View recent scheduler runs
heroku logs --app your-app-name --ps scheduler

# Real-time log monitoring
heroku logs --app your-app-name --tail
```

### Custom Metrics (Optional)

Consider adding metrics tracking:

- Number of API requests made
- Success/failure rates
- Cache hit ratios

## Error Handling

The command includes:

- **Graceful API failure handling**
- **Detailed logging** of successes and failures
- **Automatic retry logic** (built into Simyan)
- **Rate limit respect** even on failures

## Alternative: APScheduler Background Worker

If you need more control, you can run a background worker:

```python
# In a separate worker dyno
from apscheduler.schedulers.blocking import BlockingScheduler
import os

scheduler = BlockingScheduler()

@scheduler.scheduled_job('cron', hour=2, minute=0)  # 2 AM daily
def fetch_data():
    os.system('python manage.py fetch_missing_data --limit 180')

scheduler.start()
```

Add to Procfile:

```
web: gunicorn weeklypulls.wsgi
worker: python scheduler_worker.py
```

## Cost Considerations

- **Heroku Scheduler**: Free tier covers most needs
- **Dyno hours**: ~30 seconds per run = minimal usage
- **Database**: Ensure your plan supports the data volume

## Testing

Always test with dry-run first:

```bash
heroku run python manage.py primecache --limit 10 --dry-run
```

### Testing Smart Refresh Logic

```bash
# Test recent series prioritization
heroku run python manage.py primecache --dry-run --limit 20

# Test with smaller limits to verify behavior
heroku run python manage.py primecache --limit 5
```
