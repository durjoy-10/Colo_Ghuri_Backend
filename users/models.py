from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('guide', 'Guide'),
        ('traveller', 'Traveller'),
    )
    
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='traveller')
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be in format: '+999999999'. Up to 15 digits allowed.")
    phone_number = models.CharField(validators=[phone_regex], max_length=20, blank=True)
    national_id = models.CharField(max_length=100, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    email = models.EmailField(unique=True, max_length=254)
    is_verified = models.BooleanField(default=False)
    verification_documents = models.FileField(upload_to='verification_docs/', blank=True, null=True)
    guide_group_id = models.IntegerField(null=True, blank=True)
    
    # Email verification fields
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=255, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(blank=True, null=True)
    
    # Password reset fields
    password_reset_token = models.CharField(max_length=255, blank=True, null=True)
    password_reset_sent_at = models.DateTimeField(blank=True, null=True)
    
    # Additional fields
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    preferred_language = models.CharField(max_length=200, blank=True, default='Bengali, English')
    
    def __str__(self):
        return f"{self.username} - {self.role}"
    
    class Meta:
        db_table = 'users'
        verbose_name_plural = 'Users'