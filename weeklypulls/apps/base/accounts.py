"""Point the links in account emails at the React client, not the API.

The API serves no HTML pages, so the email-confirmation and password-reset
links go to client routes, which post the key or token back to dj-rest-auth:

- {FRONTEND_URL}/verify-email/<key>       -> POST auth/registration/verify-email/
- {FRONTEND_URL}/reset-password/<uid>/<token> -> POST auth/password/reset/confirm/
"""

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.contrib.auth.models import update_last_login
from dj_rest_auth.serializers import LoginSerializer, PasswordResetSerializer
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.settings import api_settings


def frontend_url(path: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/{path.lstrip('/')}"


class AccountAdapter(DefaultAccountAdapter):
    def get_email_confirmation_url(self, request, emailconfirmation):
        return frontend_url(f"verify-email/{emailconfirmation.key}")


def _reset_url(request, user, temp_key):
    from allauth.account.utils import user_pk_to_url_str

    return frontend_url(f"reset-password/{user_pk_to_url_str(user)}/{temp_key}")


class FrontendPasswordResetSerializer(PasswordResetSerializer):
    def get_email_options(self):
        return {"url_generator": _reset_url}


class TrackingLoginSerializer(LoginSerializer):
    """Records last_login, which Django's session login would normally do
    (dj-rest-auth skips it with SESSION_LOGIN off)."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        update_last_login(None, attrs["user"])
        return attrs


class VerifiedObtainAuthToken(ObtainAuthToken):
    """The old token endpoint, kept for clients loaded before the switch to
    auth/login/, but with the same verified-email check and rate limits
    (ObtainAuthToken turns throttling off by default)."""

    throttle_classes = api_settings.DEFAULT_THROTTLE_CLASSES

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        LoginSerializer.validate_email_verification_status(
            serializer.validated_data["user"]
        )
        update_last_login(None, serializer.validated_data["user"])
        return super().post(request, *args, **kwargs)
