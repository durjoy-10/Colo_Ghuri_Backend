import os
import requests

from django.conf import settings
from django.core.mail import send_mail


def parse_sender(default_from_email):
    default_from_email = (default_from_email or "").strip()

    if "<" in default_from_email and ">" in default_from_email:
        name = default_from_email.split("<")[0].strip()
        email = default_from_email.split("<")[1].replace(">", "").strip()
        return name or "Colo Ghuri", email

    return "Colo Ghuri", default_from_email


def send_mailtrap_email(to_email, subject, html_content, text_content=""):
    api_token = os.environ.get("MAILTRAP_API_TOKEN", "").strip()

    if not api_token:
        raise Exception("MAILTRAP_API_TOKEN is not configured.")

    sender_name, sender_email = parse_sender(
        os.environ.get("DEFAULT_FROM_EMAIL", "Colo Ghuri <hello@demomailtrap.co>")
    )

    payload = {
        "from": {
            "email": sender_email,
            "name": sender_name,
        },
        "to": [
            {
                "email": to_email,
            }
        ],
        "subject": subject,
        "text": text_content or subject,
        "html": html_content,
        "category": "Email Verification",
    }

    response = requests.post(
        "https://send.api.mailtrap.io/api/send",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Api-Token": api_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=int(os.environ.get("EMAIL_TIMEOUT", 10)),
    )

    if response.status_code >= 400:
        raise Exception(
            f"Mailtrap email failed: {response.status_code} {response.text}"
        )

    return response.json()


def send_verification_email(user):
    token = user.email_verification_token
    verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}"

    subject = "Verify your Colo Ghuri account"

    html_message = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #222;">
        <h2>Welcome to Colo Ghuri</h2>
        <p>Hello {user.first_name or user.username},</p>
        <p>Thank you for registering. Please verify your email address by clicking the button below:</p>

        <p>
            <a href="{verification_url}"
               style="display:inline-block;padding:12px 18px;background:#0ea5b7;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:bold;">
                Verify Email
            </a>
        </p>

        <p>If the button does not work, copy and paste this link into your browser:</p>
        <p>
            <a href="{verification_url}">{verification_url}</a>
        </p>

        <p>Regards,<br>Colo Ghuri Team</p>
    </div>
    """

    plain_message = f"""
Hello {user.first_name or user.username},

Thank you for registering with Colo Ghuri.

Please verify your email using this link:
{verification_url}

Regards,
Colo Ghuri Team
"""

    print("=== VERIFICATION EMAIL DEBUG ===")
    print("To:", user.email)
    print("Verification link:", verification_url)
    print("================================")

    email_backend = os.environ.get("EMAIL_BACKEND", "").lower().strip()

    if email_backend == "mailtrap":
        return send_mailtrap_email(
            to_email=user.email,
            subject=subject,
            html_content=html_message,
            text_content=plain_message,
        )

    return send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )