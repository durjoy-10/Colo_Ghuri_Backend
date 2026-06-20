from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_verified', 'email_verified', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_verified', 'email_verified', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('role', 'email_verified', 'phone_number', 'national_id', 'profile_picture', 'address', 
                      'is_verified', 'gender', 'date_of_birth', 'preferred_language')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('role', 'email_verified', 'phone_number', 'national_id', 'address', 'gender', 'date_of_birth')
        }),
    )

admin.site.register(User, CustomUserAdmin)