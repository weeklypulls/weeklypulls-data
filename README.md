# weeklypulls-data

Django REST API behind [weeklypulls.com](https://weeklypulls.com). Comic data comes from
ComicVine via [Simyan](https://github.com/Metron-Project/Simyan) and is cached in Postgres.

## Local setup

Requires Python 3.13 and Postgres.

```sh
python3.13 -m venv .venv && source .venv/bin/activate
make install
cp dotenv_sample .env   # then edit; settings load it automatically
python manage.py migrate
make run
```

Dependencies: edit `requirements.in` / `requirements-testing.in`, then `make lock` (needs
[uv](https://docs.astral.sh/uv/)) to re-pin the `.txt` files. `make upgrade` bumps every pin.

`make test` runs the test suite (it creates a `wptest` database, so the
Postgres user needs `CREATEDB`).

## Hosting (Railway)

Project `weeklypulls`, deployed on push to `master`. Commands are configured on the
services, not in this repo:

| Service      | Command                                                                 |
| ------------ | ----------------------------------------------------------------------- |
| `data`       | build `python manage.py collectstatic --noinput`, pre-deploy `python manage.py migrate`, start `gunicorn weeklypulls.wsgi --log-file -` |
| `primecache` | cron `0 2 * * *`: `python manage.py primecache --limit 180`              |

Production settings are the default; `DJANGO_DEBUG=true` (in your local `.env`) switches to
development settings. `/health/` is Railway's health check. Add any new client origin to
`CORS_ALLOWED_ORIGINS` in `weeklypulls/settings/production.py`.

## Email

Sent through Amazon SES's SMTP interface when `EMAIL_HOST` is set on Railway
(`email-smtp.us-east-1.amazonaws.com`, with `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD`
as SES SMTP credentials); otherwise emails print to the console. `DEFAULT_FROM_EMAIL`
defaults to `WeeklyPulls <noreply@weeklypulls.com>`. To send a test message from
production: `railway ssh -s data -- python manage.py sendtestemail you@example.com`.

## primecache

Refreshes cached ComicVine volumes and issues within the API's rate limits
(Simyan enforces 1 request/second and 200/hour).

```sh
python manage.py primecache --limit 180            # normal run
python manage.py primecache --limit 20 --dry-run   # show what would be fetched
python manage.py primecache --limit 180 --force-volumes
```

Volumes refresh weekly if they started in the last 3 years, every 2 weeks if 4-10 years
old, and monthly after that. Recent series get priority for issue data.
