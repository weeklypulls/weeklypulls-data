import os

from dotenv import load_dotenv

# Local development reads .env; on Railway there is no .env and real
# environment variables win anyway (override=False).
load_dotenv()

# Production is the default. Development settings (DEBUG, any host, any CORS
# origin) load only when DJANGO_DEBUG is explicitly truthy, so a missing
# variable can never make production run in debug mode.
if os.getenv("DJANGO_DEBUG", "").lower() in ("1", "true", "yes"):
    from .development import *
else:
    from .production import *
