from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import User
from .models import Guide

@receiver(post_save, sender=User)
def sync_guide_profile(sender, instance, **kwargs):
    """
    Automatically sync Guide profile when User is updated
    This runs every time a User is saved (created or updated)
    """
    # Only sync for guide role
    if instance.role == 'guide':
        try:
            # Try to get existing guide profile
            guide = Guide.objects.get(user=instance)
            
            # Update guide fields from user fields
            guide.name = f"{instance.first_name} {instance.last_name}".strip()
            guide.username = instance.username
            guide.email = instance.email
            guide.phone_number = instance.phone_number
            guide.national_id = instance.national_id
            guide.save()
            
            print(f"✅ Guide profile synced: {guide.name}")
            
        except Guide.DoesNotExist:
            print(f"⚠️ Guide profile not found for user: {instance.username}")