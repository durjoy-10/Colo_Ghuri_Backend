from django.urls import path
from .views import (
    GuideGroupRegistrationView, GuideGroupListView, GuideGroupDetailView,
    PendingGuideGroupsView, VerifyGuideGroupView, RejectGuideGroupView,
    GuideDashboardView, GuideGroupBookingsView, GuideSetupPasswordView
)

urlpatterns = [
    path('register-group/', GuideGroupRegistrationView.as_view(), name='register-group'),
    path('setup-password/<str:token>/', GuideSetupPasswordView.as_view(), name='guide-setup-password'),
    path('groups/', GuideGroupListView.as_view(), name='guide-group-list'),
    path('groups/<int:guide_group_id>/', GuideGroupDetailView.as_view(), name='guide-group-detail'),
    path('pending-groups/', PendingGuideGroupsView.as_view(), name='pending-groups'),
    path('verify-group/<int:group_id>/', VerifyGuideGroupView.as_view(), name='verify-group'),
    path('reject-group/<int:group_id>/', RejectGuideGroupView.as_view(), name='reject-group'),
    path('dashboard/', GuideDashboardView.as_view(), name='guide-dashboard'),
    path('bookings/', GuideGroupBookingsView.as_view(), name='guide-bookings'),
]