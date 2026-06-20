from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
import secrets
import traceback


def generate_verification_token():
    return secrets.token_urlsafe(32)


def generate_password_reset_token():
    return secrets.token_urlsafe(32)


def send_verification_email(user, request):
    token = generate_verification_token()
    user.email_verification_token = token
    user.email_verification_sent_at = timezone.now()
    user.save()

    verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}"

    print("\n=== VERIFICATION EMAIL DEBUG ===")
    print(f"To: {user.email}")
    print(f"From: {settings.DEFAULT_FROM_EMAIL}")
    print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"EMAIL_HOST_PASSWORD exists: {bool(settings.EMAIL_HOST_PASSWORD)}")
    print(f"Verification link: {verification_url}")
    print("================================\n")

    context = {
        'user': user,
        'verification_url': verification_url,
        'site_name': 'Colo Ghuri',
        'expiry_hours': 24,
    }

    try:
        try:
            html_message = render_to_string('emails/verify_email.html', context)
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
            html_message = f"<pre>{plain_message}</pre>"

        send_mail(
            subject='Verify Your Email Address - Colo Ghuri',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
            auth_user=settings.EMAIL_HOST_USER,
            auth_password=settings.EMAIL_HOST_PASSWORD,
        )

        print(f"✅ Verification email sent successfully to {user.email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send verification email to {user.email}")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return False


def send_password_reset_email(user, request):
    token = generate_password_reset_token()
    user.password_reset_token = token
    user.password_reset_sent_at = timezone.now()
    user.save()

    reset_url = f"{settings.FRONTEND_URL}/reset-password/{token}"

    context = {
        'user': user,
        'reset_url': reset_url,
        'site_name': 'Colo Ghuri',
        'expiry_hours': 24,
    }

    try:
        try:
            html_message = render_to_string('emails/password_reset.html', context)
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
            html_message = f"<pre>{plain_message}</pre>"

        send_mail(
            subject='Reset Your Password - Colo Ghuri',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
            auth_user=settings.EMAIL_HOST_USER,
            auth_password=settings.EMAIL_HOST_PASSWORD,
        )

        print(f"✅ Password reset email sent successfully to {user.email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send password reset email to {user.email}")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return False


def send_welcome_email(user, request):
    login_url = f"{settings.FRONTEND_URL}/login"

    context = {
        'user': user,
        'site_name': 'Colo Ghuri',
        'login_url': login_url,
    }

    try:
        try:
            html_message = render_to_string('emails/welcome_email.html', context)
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
            html_message = f"<pre>{plain_message}</pre>"

        send_mail(
            subject='Welcome to Colo Ghuri!',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
            auth_user=settings.EMAIL_HOST_USER,
            auth_password=settings.EMAIL_HOST_PASSWORD,
        )

        print(f"✅ Welcome email sent successfully to {user.email}")
        return True

    except Exception as e:
        print(f"❌ Failed to send welcome email to {user.email}")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return False