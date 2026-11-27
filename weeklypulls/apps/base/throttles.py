"""Rate limits for the account endpoints: the logged-out ones, plus the two
logged-in ones that check your current password.

Each endpoint gets two limits: one per client IP, and one per account
identity (the username for logins, the email address for reset and
verification emails), so a single address can't be flooded with email or
have its password guessed from many IPs. Rates live in
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] as "<action>_ip" / "<action>_id".

The throttles apply to every DRF view but do nothing outside the views
listed in AUTH_ACTIONS. Matching on the view class (rather than the URL)
covers every route dj-rest-auth registers, including the ones without a
trailing slash.

Counts live in the default cache. That's per-process local memory, which is
fine with production's single gunicorn worker; with more workers or
instances, move it to a shared cache.
"""

from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle

# View class name -> (action, request field identifying the account)
AUTH_ACTIONS = {
    "LoginView": ("login", "username"),
    "VerifiedObtainAuthToken": ("login", "username"),
    "RegisterView": ("register", "email"),
    "PasswordResetView": ("password_reset", "email"),
    "PasswordResetConfirmView": ("password_reset_confirm", "uid"),
    "ResendEmailVerificationView": ("resend_email", "email"),
    "VerifyEmailView": ("verify_email", None),
    "PasswordChangeView": ("password_change", None),
    "AccountDeleteView": ("account_delete", None),
}


def client_ip(request):
    # Railway's edge proxy sets X-Real-IP to the connecting client's address.
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR")


class _AuthThrottle(SimpleRateThrottle):
    kind = ""

    def __init__(self):
        # Rates are looked up per request (see allow_request), not here.
        pass

    def _action(self, view):
        for cls in type(view).__mro__:
            if cls.__name__ in AUTH_ACTIONS:
                return AUTH_ACTIONS[cls.__name__]
        return None

    def allow_request(self, request, view):
        action = self._action(view)
        if request.method != "POST" or action is None:
            return True
        self.action, self.field = action
        self.scope = f"{self.action}_{self.kind}"
        self.rate = api_settings.DEFAULT_THROTTLE_RATES.get(self.scope)
        if not self.rate:
            return True
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def identity(self, request):
        raise NotImplementedError

    def get_cache_key(self, request, view):
        ident = self.identity(request)
        if not ident:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}


class AuthIPThrottle(_AuthThrottle):
    kind = "ip"

    def identity(self, request):
        return client_ip(request)


class AuthIdentityThrottle(_AuthThrottle):
    kind = "id"

    def identity(self, request):
        if not self.field:
            return None
        try:
            value = request.data.get(self.field)
        except AttributeError:
            return None
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip().lower()[:254]
