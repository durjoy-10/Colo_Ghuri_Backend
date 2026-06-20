from django.contrib import admin
from .models import Guide, GuideGroup, GuideGroupMember

@admin.register(GuideGroup)
class GuideGroupAdmin(admin.ModelAdmin):
    list_display = ('guide_group_id', 'guide_groupname', 'guide_group_number', 'is_verified', 'created_at')
    list_filter = ('is_verified',)
    search_fields = ('guide_groupname',)

@admin.register(Guide)
class GuideAdmin(admin.ModelAdmin):
    list_display = ('guide_id', 'name', 'email', 'guide_group', 'experience_years', 'rating', 'is_active')
    list_filter = ('gender', 'is_active', 'guide_group')
    search_fields = ('name', 'email', 'national_id')

@admin.register(GuideGroupMember)
class GuideGroupMemberAdmin(admin.ModelAdmin):
    list_display = ('guide_group', 'guide', 'index')
    list_filter = ('guide_group',)