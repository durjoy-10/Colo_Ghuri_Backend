from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
import secrets

def generate_setup_token():
    """Generate a secure random token for guide password setup"""
    return secrets.token_urlsafe(32)

def send_guide_acceptance_email(guide, guide_group, request):
    """Send email to guide when their group is verified by admin - with password setup link"""
    token = generate_setup_token()
    guide.invitation_token = token
    guide.invitation_sent_at = timezone.now()
    guide.save()
    
    setup_url = f"{settings.FRONTEND_URL}/guide/setup-password/{token}/"
    
    print(f"Setup token for {guide.email}: {token}")
    print(f"Setup URL: {setup_url}")
    
    context = {
        'guide': guide,
        'guide_group': guide_group,
        'setup_url': setup_url,
        'site_name': 'Colo Ghuri',
        'expiry_hours': 48
    }
    
    try:
        html_message = render_to_string('emails/guide_acceptance.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Your Guide Application has been Accepted - {guide_group.guide_groupname}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[guide.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"✅ Password setup email sent to guide {guide.email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email to guide {guide.email}: {str(e)}")
        return False