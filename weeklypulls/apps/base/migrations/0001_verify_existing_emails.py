"""Prepare for mandatory email verification.

- Names the site, which account emails use for their greeting and sign-off.
- Treats the email address of every account that existed before verification
  was required as verified, so existing users aren't locked out.
"""

from django.conf import settings
from django.db import migrations


def forwards(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        id=settings.SITE_ID,
        defaults={"domain": "weeklypulls.com", "name": "WeeklyPulls"},
    )

    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    EmailAddress = apps.get_model("account", "EmailAddress")
    for user in User.objects.exclude(email=""):
        # allauth stores addresses lowercased, and dj-rest-auth's login check
        # compares user.email to EmailAddress.email exactly.
        if user.email != user.email.lower():
            user.email = user.email.lower()
            user.save(update_fields=["email"])
        address = EmailAddress.objects.filter(
            user=user, email__iexact=user.email
        ).first()
        if address:
            address.email = user.email
            address.verified = True
            address.save(update_fields=["email", "verified"])
        else:
            EmailAddress.objects.create(
                user=user,
                email=user.email.lower(),
                verified=True,
                primary=not EmailAddress.objects.filter(
                    user=user, primary=True
                ).exists(),
            )


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0002_alter_domain_unique"),
        ("account", "0009_emailaddress_unique_primary_email"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
