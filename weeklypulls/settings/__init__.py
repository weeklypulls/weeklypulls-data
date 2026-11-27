import os

from dotenv import load_dotenv

# Local development reads .env; on Railway there is no .env and real
# environment variables win anyway (override=False).
load_dotenv()

if os.getenv("WP_PROD", False):
    from .production import *
else:
    from .development import *
