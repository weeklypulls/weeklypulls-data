"""The logged-in user's own account: details, data export, and deletion."""

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from weeklypulls.apps.comicvine.models import ComicVineVolume


class UserDetailsSerializer(serializers.ModelSerializer):
    """What /auth/user/ returns. Read-only: changing the email address would
    need its own verification flow."""

    class Meta:
        model = get_user_model()
        fields = ("pk", "username", "email", "date_joined")
        read_only_fields = fields


def export_account(user):
    series_ids = set(user.pulls.values_list("series_id", flat=True))
    names = dict(
        ComicVineVolume.objects.filter(cv_id__in=series_ids).values_list(
            "cv_id", "name"
        )
    )
    return {
        "exported_at": timezone.now().isoformat(),
        "account": {
            "username": user.username,
            "email": user.email,
            "date_joined": user.date_joined.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "pull_lists": [
            {
                "id": str(pull_list.id),
                "title": pull_list.title,
                "created_at": pull_list.created_at.isoformat(),
                "pulls": [
                    {
                        "id": str(pull.id),
                        "comicvine_series_id": pull.series_id,
                        "series_name": names.get(pull.series_id),
                        "read_comicvine_issue_ids": sorted(pull.read),
                        "created_at": pull.created_at.isoformat(),
                    }
                    for pull in pull_list.pull_set.order_by("created_at")
                ],
            }
            for pull_list in user.pull_lists.order_by("created_at")
        ],
    }


class AccountExportView(APIView):
    """GET: everything WeeklyPulls stores about you, as a JSON download."""

    def get(self, request):
        stamp = timezone.now().strftime("%Y-%m-%d")
        return Response(
            export_account(request.user),
            headers={
                "Content-Disposition": (
                    f'attachment; filename="weeklypulls-export-{stamp}.json"'
                )
            },
        )


class AccountDeleteSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Incorrect password.")
        return value


class AccountDeleteView(APIView):
    """POST {"password": ...}: permanently delete your account, pull lists,
    pulls and login tokens."""

    def post(self, request):
        serializer = AccountDeleteSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
