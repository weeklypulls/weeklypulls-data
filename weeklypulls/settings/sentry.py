"""Sentry error and performance monitoring, configured from the environment.

Enabled only when SENTRY_DSN is set (on Railway), so local runs and CI send
nothing. sentry-sdk 3.x collects more by default than 2.x did, so
data_collection below opts out of personal data explicitly.
"""

import os

import sentry_sdk


def init_sentry():
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("RAILWAY_ENVIRONMENT_NAME", "production"),
        release=os.getenv("RAILWAY_GIT_COMMIT_SHA") or None,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        data_collection={
            "user_info": False,
            "cookies": {"mode": "off"},
            "http_bodies": [],
            "http_headers": {
                "request": {
                    "mode": "denylist",
                    "terms": ["forwarded", "-ip", "remote-", "via", "-user"],
                }
            },
            "database_query_data": False,
            # Locals help debugging; keys matching Sentry's built-in denylist
            # (password, token, auth, session, ...) plus "email" are filtered.
            "stack_frame_variables": {"mode": "denylist", "terms": ["email"]},
        },
        # Setup reviewed against sentry_sdk/SETUP_CHECKLIST.md (logs: off by choice).
        _experiments={"agent_setup_complete": True},
    )
