from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User

class GuideGroup(models.Model):
    guide_group_id = models.AutoField(primary_key=True)
    guide_groupname = models.CharField(max_length=100, unique=True)
    guide_group_picture = models.ImageField(upload_to='guide_groups/', blank=True, null=True)
    guide_group_number = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(8)], default=1)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    email = models.EmailField(max_length=254, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.guide_groupname} (Members: {self.guide_group_number}) - {'Verified' if self.is_verified else 'Pending'}"
    
    class Meta:
        db_table = 'guide_groups'
        verbose_name_plural = 'Guide Groups'


class Guide(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
    )
    
    guide_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='guide_profile', null=True, blank=True)
    guide_group = models.ForeignKey(GuideGroup, on_delete=models.CASCADE, related_name='guides')
    name = models.CharField(max_length=200)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=254, unique=True)
    national_id = models.CharField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=20)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    experience_years = models.IntegerField(default=0)
    languages_spoken = models.CharField(max_length=500, default='Bengali, English')
    bio = models.TextField(blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_tours = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    joined_date = models.DateTimeField(auto_now_add=True)
    
    # Invitation fields
    invitation_token = models.CharField(max_length=255, blank=True, null=True)
    invitation_sent_at = models.DateTimeField(blank=True, null=True)
    has_set_password = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Guide: {self.name} - Group: {self.guide_group.guide_groupname}"
    
    class Meta:
        db_table = 'guides'
        verbose_name_plural = 'Guides'


class GuideGroupMember(models.Model):
    guide_group = models.ForeignKey(GuideGroup, on_delete=models.CASCADE, related_name='members')
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name='group_memberships')
    index = models.IntegerField(help_text="Position in group (1-8)")
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('guide_group', 'guide')
        ordering = ['index']
        db_table = 'guide_group_members'
    
    def __str__(self):
        return f"{self.guide.name} - {self.guide_group.guide_groupname} (Position: {self.index})"