from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import BasePermission
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Guide, GuideGroup, GuideGroupMember
from .serializers import GuideGroupSerializer, GuideSerializer, GuideGroupMemberSerializer, GuideGroupRegistrationSerializer
from .utils import send_guide_acceptance_email
from users.models import User
from tours.models import Tour, TourBooking
from django.db.models import Sum, Count, Q
from decimal import Decimal


class IsGuideOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['guide', 'admin']


class IsGuideVerified(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == 'admin' or 
            (request.user.role == 'guide' and request.user.is_verified)
        )


class GuideGroupRegistrationView(APIView):
    permission_classes = (permissions.AllowAny,)
    
    def post(self, request):
        print("=" * 50)
        print("GUIDE GROUP REGISTRATION REQUEST")
        
        serializer = GuideGroupRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                result = serializer.save()
                guide_group = result['guide_group']
                guides = result['guides']
                
                # NO emails sent here - only after admin verification
                
                return Response({
                    'success': True,
                    'message': f'Guide group registration successful! Admin will review and verify the group. {len(guides)} guides have been registered.',
                    'guide_group': GuideGroupSerializer(guide_group).data,
                    'guides': GuideSerializer(guides, many=True).data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                print(f"Error during save: {str(e)}")
                return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            print(f"Serializer errors: {serializer.errors}")
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class GuideSetupPasswordView(APIView):
    permission_classes = (permissions.AllowAny,)
    
    def get(self, request, token):
        """Check if token is valid"""
        print(f"GET request for token: {token}")
        
        try:
            guide = Guide.objects.get(invitation_token=token)
        except Guide.DoesNotExist:
            return Response({
                'success': False, 
                'error': 'Invalid setup link. The link may have been used already or is incorrect.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if token is expired (48 hours)
        if guide.invitation_sent_at:
            time_diff = timezone.now() - guide.invitation_sent_at
            if time_diff.total_seconds() > 172800:  # 48 hours
                return Response({
                    'success': False, 
                    'error': 'Setup link has expired. Please contact the group admin.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if password already set
        if guide.has_set_password:
            return Response({
                'success': False, 
                'error': 'Password already set for this account. Please login.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if guide group is verified
        if not guide.guide_group.is_verified:
            return Response({
                'success': False, 
                'error': 'Your guide group is pending verification. Please wait for admin approval.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True, 
            'message': 'Valid setup link',
            'guide': {
                'name': guide.name,
                'email': guide.email,
                'username': guide.username,
                'group_name': guide.guide_group.guide_groupname
            }
        }, status=status.HTTP_200_OK)
    
    def post(self, request, token):
        """Set password for guide"""
        print(f"POST request for token: {token}")
        
        try:
            guide = Guide.objects.get(invitation_token=token)
        except Guide.DoesNotExist:
            return Response({
                'success': False, 
                'error': 'Invalid setup link. The link may have been used already or is incorrect.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if token is expired (48 hours)
        if guide.invitation_sent_at:
            time_diff = timezone.now() - guide.invitation_sent_at
            if time_diff.total_seconds() > 172800:  # 48 hours
                return Response({
                    'success': False, 
                    'error': 'Setup link has expired. Please contact the group admin.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if password already set
        if guide.has_set_password:
            return Response({
                'success': False, 
                'error': 'Password already set for this account. Please login.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if guide group is verified
        if not guide.guide_group.is_verified:
            return Response({
                'success': False, 
                'error': 'Your guide group is pending verification. Please wait for admin approval.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        password = request.data.get('password')
        if not password or len(password) < 6:
            return Response({
                'success': False, 
                'error': 'Password must be at least 6 characters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user already exists
        if User.objects.filter(username=guide.username).exists():
            return Response({
                'success': False, 
                'error': f'Username "{guide.username}" already exists.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create User account for the guide
        user = User.objects.create_user(
            username=guide.username,
            email=guide.email,
            password=password,
            first_name=guide.name.split()[0] if ' ' in guide.name else guide.name,
            last_name=guide.name.split()[-1] if ' ' in guide.name else '',
            role='guide',
            phone_number=guide.phone_number,
            national_id=guide.national_id,
            is_verified=True,  # Already verified by admin (group is verified)
            email_verified=True
        )
        
        # Link user to guide
        guide.user = user
        guide.has_set_password = True
        guide.invitation_token = None
        guide.is_active = True
        guide.save()
        
        print(f"Password set successfully for guide: {guide.email}")
        
        return Response({
            'success': True,
            'message': 'Password set successfully! You can now login to your guide account.',
            'redirect_url': '/login'
        }, status=status.HTTP_200_OK)


class GuideDashboardView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request):
        try:
            guide = Guide.objects.get(user=request.user)
            guide_group = guide.guide_group
            
            tours = Tour.objects.filter(guide_group=guide_group)
            bookings = TourBooking.objects.filter(tour__in=tours)
            
            # Revenue from confirmed OR completed bookings
            revenue_bookings = bookings.filter(Q(status='confirmed') | Q(status='completed'))
            total_revenue = revenue_bookings.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            
            total_expenses = tours.aggregate(total=Sum('total_expenses'))['total'] or Decimal('0.00')
            total_profit = total_revenue - total_expenses
            
            total_tours = tours.count()
            total_bookings = bookings.count()
            total_travellers = bookings.aggregate(total=Sum('number_of_travellers'))['total'] or 0
            
            upcoming_tours = tours.filter(status='upcoming').count()
            ongoing_tours = tours.filter(status='ongoing').count()
            completed_tours = tours.filter(status='completed').count()
            
            # Per-tour profit breakdown
            tour_profits = []
            for tour in tours:
                tour_revenue_bookings = bookings.filter(tour=tour).filter(Q(status='confirmed') | Q(status='completed'))
                tour_revenue = tour_revenue_bookings.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
                tour_profit = tour_revenue - tour.total_expenses
                
                tour_profits.append({
                    'tour_id': tour.tour_id,
                    'tour_name': tour.tour_name,
                    'revenue': float(tour_revenue),
                    'expenses': float(tour.total_expenses),
                    'profit': float(tour_profit),
                    'booking_count': tour_revenue_bookings.count(),
                    'traveller_count': tour_revenue_bookings.aggregate(total=Sum('number_of_travellers'))['total'] or 0,
                    'status': tour.status,
                    'is_locked': tour.is_locked,
                })
            
            recent_bookings = bookings.select_related('tour', 'traveller').order_by('-booking_date')[:15]
            group_members = GuideGroupMember.objects.filter(guide_group=guide_group).select_related('guide')
            
            dashboard_data = {
                'guide_group': {
                    'id': guide_group.guide_group_id,
                    'name': guide_group.guide_groupname,
                    'member_count': guide_group.guide_group_number,
                    'is_verified': guide_group.is_verified,
                    'email': guide_group.email,
                    'phone': guide_group.phone_number,
                    'address': guide_group.address or 'Not provided',
                    'description': guide_group.description or 'No description',
                    'created_at': guide_group.created_at,
                },
                'guide_profile': {
                    'name': guide.name,
                    'username': guide.username,
                    'email': guide.email,
                    'phone': guide.phone_number,
                    'experience': guide.experience_years,
                    'languages': guide.languages_spoken,
                    'bio': guide.bio or 'No bio',
                    'rating': float(guide.rating),
                    'total_tours': guide.total_tours,
                },
                'statistics': {
                    'total_tours': total_tours,
                    'total_bookings': total_bookings,
                    'total_revenue': float(total_revenue),
                    'total_expenses': float(total_expenses),
                    'total_profit': float(total_profit),
                    'total_travellers': total_travellers,
                    'upcoming_tours': upcoming_tours,
                    'ongoing_tours': ongoing_tours,
                    'completed_tours': completed_tours,
                },
                'tour_profits': tour_profits,
                'recent_bookings': [
                    {
                        'id': booking.booking_id,
                        'tour_name': booking.tour.tour_name,
                        'tour_id': booking.tour.tour_id,
                        'traveller_name': booking.traveller.get_full_name() or booking.traveller.username,
                        'traveller_email': booking.traveller.email,
                        'traveller_phone': booking.traveller.phone_number,
                        'number_of_travellers': booking.number_of_travellers,
                        'total_amount': float(booking.total_amount),
                        'status': booking.status,
                        'booking_date': booking.booking_date,
                        'payment_method': booking.payment_method,
                        'payment_id': booking.payment_id,
                        'guide_reference': booking.guide_reference,
                        'special_requests': booking.special_requests,
                    }
                    for booking in recent_bookings
                ],
                'group_members': [
                    {
                        'id': member.guide.guide_id,
                        'name': member.guide.name,
                        'username': member.guide.username,
                        'email': member.guide.email,
                        'phone': member.guide.phone_number,
                        'experience': member.guide.experience_years,
                        'languages': member.guide.languages_spoken,
                        'rating': float(member.guide.rating),
                        'total_tours': member.guide.total_tours,
                        'joined_date': member.joined_at,
                    }
                    for member in group_members
                ],
            }
            
            return Response(dashboard_data)
            
        except Guide.DoesNotExist:
            return Response({'error': 'Guide profile not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GuideGroupBookingsView(generics.ListAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request):
        try:
            guide = Guide.objects.get(user=request.user)
            guide_group = guide.guide_group
            
            tours = Tour.objects.filter(guide_group=guide_group)
            bookings = TourBooking.objects.filter(tour__in=tours).order_by('-booking_date')
            
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            start = (page - 1) * page_size
            end = start + page_size
            
            total = bookings.count()
            
            booking_list = []
            for booking in bookings[start:end]:
                booking_list.append({
                    'id': booking.booking_id,
                    'tour_name': booking.tour.tour_name,
                    'tour_id': booking.tour.tour_id,
                    'traveller_name': booking.traveller.get_full_name() or booking.traveller.username,
                    'traveller_email': booking.traveller.email,
                    'traveller_phone': booking.traveller.phone_number,
                    'number_of_travellers': booking.number_of_travellers,
                    'total_amount': float(booking.total_amount),
                    'status': booking.status,
                    'booking_date': booking.booking_date,
                    'payment_method': booking.payment_method,
                    'payment_id': booking.payment_id,
                    'guide_reference': booking.guide_reference,
                    'special_requests': booking.special_requests,
                })
            
            return Response({
                'bookings': booking_list,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size if total > 0 else 1,
            })
            
        except Guide.DoesNotExist:
            return Response({'error': 'Guide profile not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GuideGroupListView(generics.ListAPIView):
    queryset = GuideGroup.objects.filter(is_verified=True)
    serializer_class = GuideGroupSerializer
    permission_classes = (permissions.AllowAny,)


class GuideGroupDetailView(generics.RetrieveAPIView):
    queryset = GuideGroup.objects.all()
    serializer_class = GuideGroupSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = 'guide_group_id'


class PendingGuideGroupsView(generics.ListAPIView):
    serializer_class = GuideGroupSerializer
    permission_classes = (permissions.IsAdminUser,)
    
    def get_queryset(self):
        return GuideGroup.objects.filter(is_verified=False)


class VerifyGuideGroupView(APIView):
    permission_classes = (permissions.IsAdminUser,)
    
    def post(self, request, group_id):
        try:
            guide_group = GuideGroup.objects.get(guide_group_id=group_id)
            guide_group.is_verified = True
            guide_group.save()
            
            # Send acceptance emails to all guides in the group (with password setup link)
            guides = guide_group.guides.all()
            emails_sent = 0
            for guide in guides:
                if send_guide_acceptance_email(guide, guide_group, request):
                    emails_sent += 1
            
            return Response({
                'success': True,
                'message': f'Guide group verified successfully! Password setup emails sent to {emails_sent} guides.',
                'emails_sent': emails_sent
            })
        except GuideGroup.DoesNotExist:
            return Response({'error': 'Guide group not found'}, status=status.HTTP_404_NOT_FOUND)


class RejectGuideGroupView(APIView):
    permission_classes = (permissions.IsAdminUser,)
    
    def delete(self, request, group_id):
        try:
            guide_group = GuideGroup.objects.get(guide_group_id=group_id)
            # Delete all guides
            for guide in guide_group.guides.all():
                if guide.user:
                    guide.user.delete()
                guide.delete()
            guide_group.delete()
            return Response({'message': 'Guide group rejected and deleted'})
        except GuideGroup.DoesNotExist:
            return Response({'error': 'Guide group not found'}, status=status.HTTP_404_NOT_FOUND)