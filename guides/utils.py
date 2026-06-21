import os
import secrets
import traceback

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

from users.utils import send_project_email


def generate_setup_token():
    return secrets.token_urlsafe(32)


def get_frontend_url():
    return getattr(
        settings,
        "FRONTEND_URL",
        os.environ.get("FRONTEND_URL", "http://localhost:5173"),
    ).rstrip("/")


def send_guide_acceptance_email(guide, guide_group, request=None):
    token = generate_setup_token()
    guide.invitation_token = token
    guide.invitation_sent_at = timezone.now()
    guide.save()

    setup_url = f"{get_frontend_url()}/guide/setup-password/{token}/"

    print("\n=== GUIDE ACCEPTANCE EMAIL DEBUG ===")
    print(f"To: {guide.email}")
    print(f"Guide: {guide.name}")
    print(f"Group: {guide_group.guide_groupname}")
    print(f"Setup URL: {setup_url}")
    print("====================================\n")

    context = {
        "guide": guide,
        "guide_group": guide_group,
        "setup_url": setup_url,
        "site_name": "Colo Ghuri",
        "expiry_hours": 48,
    }

    try:
        try:
            html_message = render_to_string("emails/guide_acceptance.html", context)
            plain_message = strip_tags(html_message)
        except Exception:
            plain_message = f"""
Hello {guide.name or guide.username},

Your guide group application has been accepted.

Guide Group: {guide_group.guide_groupname}

Please set your password using the link below:

{setup_url}

This setup link will expire in 48 hours.

Best regards,
Colo Ghuri Team
"""
            html_message = f"""
<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #222;">
    <h2>Guide Group Verified</h2>
    <p>Hello {guide.name or guide.username},</p>
    <p>Your guide group application has been accepted.</p>
    <p><strong>Guide Group:</strong> {guide_group.guide_groupname}</p>
    <p>Please set your password using the button below:</p>
    <p>
        <a href="{setup_url}"
           style="display:inline-block;padding:12px 18px;background:#0ea5b7;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:bold;">
            Set Password
        </a>
    </p>
    <p>If the button does not work, copy and paste this link:</p>
    <p><a href="{setup_url}">{setup_url}</a></p>
    <p>This setup link will expire in 48 hours.</p>
    <p>Best regards,<br>Colo Ghuri Team</p>
</div>
"""

        send_project_email(
            to_email=guide.email,
            subject=f"Your Guide Application has been Accepted - {guide_group.guide_groupname}",
            plain_message=plain_message,
            html_message=html_message,
        )

        print(f"✅ Guide acceptance email sent successfully to {guide.email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send guide acceptance email to {guide.email}")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return False