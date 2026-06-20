import os
import secrets
import traceback
import requests

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone


def generate_verification_token():
    return secrets.token_urlsafe(32)


def generate_password_reset_token():
    return secrets.token_urlsafe(32)


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
        "category": "Colo Ghuri Email",
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


def send_project_email(to_email, subject, plain_message, html_message):
    email_backend = os.environ.get("EMAIL_BACKEND", "").lower().strip()

    if email_backend == "mailtrap":
        send_mailtrap_email(
            to_email=to_email,
            subject=subject,
            html_content=html_message,
            text_content=plain_message,
        )
        return True

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        html_message=html_message,
        fail_silently=False,
    )
    return True


def send_verification_email(user, request=None):
    token = generate_verification_token()
    user.email_verification_token = token
    user.email_verification_sent_at = timezone.now()
    user.save()

    verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}"

    print("\n=== VERIFICATION EMAIL DEBUG ===")
    print(f"To: {user.email}")
    print(f"From: {settings.DEFAULT_FROM_EMAIL}")
    print(f"Verification link: {verification_url}")
    print("================================\n")

    context = {
        "user": user,
        "verification_url": verification_url,
        "site_name": "Colo Ghuri",
        "expiry_hours": 24,
    }

    try:
        try:
            html_message = render_to_string("emails/verify_email.html", context)
            plain_message = strip_tags(html_message)
        except Exception:
            plain_message = f"""
Hello {user.first_name or user.username},

Thank you for registering with Colo Ghuri.

Please verify your email by clicking the link below:

{verification_url}

This verification link will expire in 24 hours.

Best regards,
Colo Ghuri Team
"""
            html_message = f"""
<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #222;">
    <h2>Welcome to Colo Ghuri</h2>
    <p>Hello {user.first_name or user.username},</p>
    <p>Thank you for registering with Colo Ghuri.</p>
    <p>Please verify your email by clicking the button below:</p>
    <p>
        <a href="{verification_url}"
           style="display:inline-block;padding:12px 18px;background:#0ea5b7;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:bold;">
            Verify Email
        </a>
    </p>
    <p>If the button does not work, copy and paste this link:</p>
    <p><a href="{verification_url}">{verification_url}</a></p>
    <p>This verification link will expire in 24 hours.</p>
    <p>Best regards,<br>Colo Ghuri Team</p>
</div>
"""

        send_project_email(
            to_email=user.email,
            subject="Verify Your Email Address - Colo Ghuri",
            plain_message=plain_message,
            html_message=html_message,
        )

        print(f"✅ Verification email sent successfully to {user.email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send verification email to {user.email}")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return False


def send_password_reset_email(user, request=None):
    token = generate_password_reset_token()
    user.password_reset_token = token
    user.password_reset_sent_at = timezone.now()
    user.save()

    reset_url = f"{settings.FRONTEND_URL}/reset-password/{token}"

    context = {
        "user": user,
        "reset_url": reset_url,
        "site_name": "Colo Ghuri",
        "expiry_hours": 24,
    }

    try:
        try:
            html_message = render_to_string("emails/password_reset.html", context)
            plain_message = strip_tags(html_message)
        except Exception:
            plain_message = f"""
Hello {user.first_name or user.username},

You requested to reset your password for your Colo Ghuri account.

Click the link below to reset your password:

{reset_url}

This password reset link will expire in 24 hours.

If you did not request this, please ignore this email.

Best regards,
Colo Ghuri Team
"""
            html_message = f"""
<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #222;">
    <h2>Password Reset Request</h2>
    <p>Hello {user.first_name or user.username},</p>
    <p>You requested to reset your password for your Colo Ghuri account.</p>
    <p>
        <a href="{reset_url}"
           style="display:inline-block;padding:12px 18px;background:#0ea5b7;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:bold;">
            Reset Password
        </a>
    </p>
    <p>If the button does not work, copy and paste this link:</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>This password reset link will expire in 24 hours.</p>
    <p>If you did not request this, please ignore this email.</p>
    <p>Best regards,<br>Colo Ghuri Team</p>
</div>
"""

        send_project_email(
            to_email=user.email,
            subject="Reset Your Password - Colo Ghuri",
            plain_message=plain_message,
            html_message=html_message,
        )

        print(f"✅ Password reset email sent successfully to {user.email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send password reset email to {user.email}")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return False


def send_welcome_email(user, request=None):
    login_url = f"{settings.FRONTEND_URL}/login"

    context = {
        "user": user,
        "site_name": "Colo Ghuri",
        "login_url": login_url,
    }

    try:
        try:
            html_message = render_to_string("emails/welcome_email.html", context)
            plain_message = strip_tags(html_message)
        except Exception:
            plain_message = f"""
Welcome to Colo Ghuri, {user.first_name or user.username}!

Your email has been successfully verified.

You can now login here:

{login_url}

Best regards,
Colo Ghuri Team
"""
            html_message = f"""
<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #222;">
    <h2>Welcome to Colo Ghuri!</h2>
    <p>Hello {user.first_name or user.username},</p>
    <p>Your email has been successfully verified.</p>
    <p>You can now login and start exploring Bangladesh.</p>
    <p>
        <a href="{login_url}"
           style="display:inline-block;padding:12px 18px;background:#0ea5b7;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:bold;">
            Login Now
        </a>
    </p>
    <p>Best regards,<br>Colo Ghuri Team</p>
</div>
"""

        send_project_email(
            to_email=user.email,
            subject="Welcome to Colo Ghuri!",
            plain_message=plain_message,
            html_message=html_message,
        )

        print(f"✅ Welcome email sent successfully to {user.email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send welcome email to {user.email}")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return False