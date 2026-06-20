from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    UserProfileView,
    UserListView,
    UserDetailView,
    LogoutView,
    PendingGuidesView,
    VerifyGuideView,
    VerifyEmailView,
    ResendVerificationEmailView,
    ForgotPasswordView,
    ValidateResetTokenView,
    ResetPasswordView,
    ChangePasswordView,
    AdminDashboardStatsView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),

    path('verify-email/<str:token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),

    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('validate-reset-token/<str:token>/', ValidateResetTokenView.as_view(), name='validate-reset-token'),
    path('reset-password/<str:token>/', ResetPasswordView.as_view(), name='reset-password'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),

    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('profile/', UserProfileView.as_view(), name='profile'),

    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:user_id>/', UserDetailView.as_view(), name='user-detail'),

    path('admin-dashboard-stats/', AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),

    path('pending-guides/', PendingGuidesView.as_view(), name='pending-guides'),
    path('verify-guide/<int:user_id>/', VerifyGuideView.as_view(), name='verify-guide'),
]