from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.http import JsonResponse
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from destinations.models import Destination
from tours.models import Tour, TourBooking
from guides.models import GuideGroup
from .models import User
from .serializers import UserSerializer, RegisterSerializer, UserProfileSerializer
from .utils import send_verification_email, send_welcome_email, send_password_reset_email


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.email_verified = False
            user.save()

            email_sent = send_verification_email(user, request)
            message = (
                'Registration successful! Please check your email to verify your account.'
                if email_sent
                else 'Registration successful! However, we could not send verification email.'
            )

            return Response({
                'success': True,
                'message': message,
                'user': UserSerializer(user, context={'request': request}).data,
            }, status=status.HTTP_201_CREATED)

        return Response({
            'success': False,
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, token):
        try:
            user = User.objects.get(email_verification_token=token)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid verification link',
            }, status=400)

        if user.email_verification_sent_at:
            time_diff = timezone.now() - user.email_verification_sent_at
            if time_diff.total_seconds() > 86400:
                return JsonResponse({
                    'success': False,
                    'error': 'Verification link has expired',
                }, status=400)

        if user.email_verified:
            return JsonResponse({
                'success': True,
                'message': 'Email already verified',
            }, status=200)

        user.email_verified = True
        user.email_verification_token = None
        user.is_active = True
        user.save()

        try:
            send_welcome_email(user, request)
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'message': 'Email verified successfully! You can now login.',
        }, status=200)


class ResendVerificationEmailView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        email = request.data.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'No user found with this email address.',
            }, status=404)

        if user.email_verified:
            return JsonResponse({
                'success': False,
                'error': 'Email already verified.',
            }, status=400)

        email_sent = send_verification_email(user, request)

        if email_sent:
            return JsonResponse({
                'success': True,
                'message': 'Verification email sent successfully!',
            }, status=200)

        return JsonResponse({
            'success': False,
            'error': 'Failed to send verification email.',
        }, status=500)


class ForgotPasswordView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({
                'success': False,
                'error': 'Email is required',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'success': True,
                'message': 'If an account exists with this email, you will receive a password reset link.',
            }, status=status.HTTP_200_OK)

        if not user.email_verified:
            return Response({
                'success': False,
                'error': 'Please verify your email address first.',
            }, status=status.HTTP_400_BAD_REQUEST)

        email_sent = send_password_reset_email(user, request)

        if email_sent:
            return Response({
                'success': True,
                'message': 'Password reset link has been sent to your email.',
            }, status=status.HTTP_200_OK)

        return Response({
            'success': False,
            'error': 'Failed to send password reset email.',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ValidateResetTokenView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, token):
        try:
            user = User.objects.get(password_reset_token=token)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or expired reset link.',
            }, status=404)

        if user.password_reset_sent_at:
            time_diff = timezone.now() - user.password_reset_sent_at
            if time_diff.total_seconds() > 86400:
                return JsonResponse({
                    'success': False,
                    'error': 'Reset link has expired.',
                }, status=400)

        return JsonResponse({
            'success': True,
            'message': 'Valid reset token',
            'email': user.email,
        }, status=200)


class ResetPasswordView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, token):
        try:
            user = User.objects.get(password_reset_token=token)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or expired reset link.',
            }, status=404)

        if user.password_reset_sent_at:
            time_diff = timezone.now() - user.password_reset_sent_at
            if time_diff.total_seconds() > 86400:
                return JsonResponse({
                    'success': False,
                    'error': 'Reset link has expired.',
                }, status=400)

        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not new_password or not confirm_password:
            return JsonResponse({
                'success': False,
                'error': 'Both password fields are required.',
            }, status=400)

        if new_password != confirm_password:
            return JsonResponse({
                'success': False,
                'error': 'Passwords do not match.',
            }, status=400)

        try:
            validate_password(new_password, user=user)
        except ValidationError as exc:
            return JsonResponse({
                'success': False,
                'error': ' '.join(exc.messages),
            }, status=400)

        user.set_password(new_password)
        user.password_reset_token = None
        user.password_reset_sent_at = None
        user.save()

        return JsonResponse({
            'success': True,
            'message': 'Password reset successfully!',
        }, status=200)


class LoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)

        if not user:
            return Response(
                {'error': 'Invalid Credentials'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.email_verified:
            return Response(
                {'error': 'Please verify your email address before logging in. Check your inbox for verification link.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.role == 'guide' and not user.is_verified:
            return Response(
                {'error': 'Your guide account is pending verification by admin.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user, context={'request': request}).data,
        })


class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not old_password or not new_password:
            return Response({
                'success': False,
                'error': 'Current password and new password are required.',
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        if not user.check_password(old_password):
            return Response({
                'success': False,
                'error': 'Current password is incorrect.',
            }, status=status.HTTP_400_BAD_REQUEST)

        if old_password == new_password:
            return Response({
                'success': False,
                'error': 'New password must be different from current password.',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=user)
        except ValidationError as exc:
            return Response({
                'success': False,
                'error': ' '.join(exc.messages),
            }, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({
            'success': True,
            'message': 'Password changed successfully. Please login again if required.',
        }, status=status.HTTP_200_OK)


class IsAdminOrRoleAdmin(permissions.BasePermission):
    """
    Allows Django staff/superuser or custom users with role='admin'.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_staff
                or request.user.is_superuser
                or getattr(request.user, 'role', None) == 'admin'
            )
        )


class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAdminOrRoleAdmin,)
    pagination_class = None

    def get_queryset(self):
        return User.objects.all().order_by('-date_joined')

class UserDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAdminOrRoleAdmin,)
    lookup_field = 'id'
    lookup_url_kwarg = 'user_id'

    def get_queryset(self):
        return User.objects.all()

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()

        if user.id == request.user.id:
            return Response(
                {'error': 'You cannot delete your own account.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.is_superuser:
            return Response(
                {'error': 'Superuser account cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.role == 'admin' or user.is_staff:
            return Response(
                {'error': 'Admin/staff account cannot be deleted from this panel.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            deleted_username = user.username
            user.delete()

            return Response(
                {'message': f'User "{deleted_username}" deleted successfully.'},
                status=status.HTTP_200_OK
            )

        except ProtectedError:
            return Response(
                {
                    'error': 'This user cannot be deleted because related protected records exist.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        except IntegrityError:
            return Response(
                {
                    'error': 'This user cannot be deleted because related database records exist.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
            


class AdminDashboardStatsView(APIView):
    permission_classes = (IsAdminOrRoleAdmin,)

    def get(self, request):
        verified_users = User.objects.filter(email_verified=True)

        total_users = verified_users.count()
        total_travellers = verified_users.filter(role='traveller').count()
        total_guides = verified_users.filter(role='guide').count()
        total_admins = verified_users.filter(role='admin').count()

        unverified_users = User.objects.filter(email_verified=False).count()

        total_destinations = Destination.objects.count()
        total_tours = Tour.objects.count()
        active_tours = Tour.objects.filter(status__in=['upcoming', 'ongoing']).count()
        completed_tours = Tour.objects.filter(status='completed').count()
        cancelled_tours = Tour.objects.filter(status='cancelled').count()

        total_bookings = TourBooking.objects.count()
        pending_bookings = TourBooking.objects.filter(status='pending').count()
        confirmed_bookings = TourBooking.objects.filter(status='confirmed').count()
        completed_bookings = TourBooking.objects.filter(status='completed').count()
        cancelled_bookings = TourBooking.objects.filter(status='cancelled').count()

        total_guide_groups = GuideGroup.objects.count()
        pending_guide_groups = GuideGroup.objects.filter(is_verified=False).count()
        verified_guide_groups = GuideGroup.objects.filter(is_verified=True).count()

        return Response({
            'users': {
                'total': total_users,
                'travellers': total_travellers,
                'guides': total_guides,
                'admins': total_admins,
                'unverified': unverified_users,
            },
            'destinations': {
                'total': total_destinations,
            },
            'tours': {
                'total': total_tours,
                'active': active_tours,
                'completed': completed_tours,
                'cancelled': cancelled_tours,
            },
            'bookings': {
                'total': total_bookings,
                'pending': pending_bookings,
                'confirmed': confirmed_bookings,
                'completed': completed_bookings,
                'cancelled': cancelled_bookings,
            },
            'guide_groups': {
                'total': total_guide_groups,
                'pending': pending_guide_groups,
                'verified': verified_guide_groups,
            }
        }, status=status.HTTP_200_OK)



class LogoutView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        refresh_token = request.data.get('refresh_token')

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass

        return Response({'message': 'Successfully logged out.'})


class PendingGuidesView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAdminUser,)

    def get_queryset(self):
        return User.objects.filter(role='guide', is_verified=False).order_by('-date_joined')


class VerifyGuideView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role='guide')
            user.is_verified = True
            user.save()
            return Response({'message': 'Guide verified successfully'})
        except User.DoesNotExist:
            return Response({'error': 'Guide not found'}, status=status.HTTP_404_NOT_FOUND)