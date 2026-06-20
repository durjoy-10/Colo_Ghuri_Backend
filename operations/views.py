from django.db.models import Sum, Q
from rest_framework import permissions, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response

from users.models import User
from destinations.models import Destination
from tours.models import Tour, TourBooking
from trips.models import Trip, Expense
from guides.models import Guide

from .models import ActivityLog, GuideAvailability, ContactMessage
from .serializers import (
    ActivityLogSerializer,
    GuideAvailabilitySerializer,
    ContactMessageSerializer,
    ContactMessageAdminUpdateSerializer,
)
from .utils import (
    generate_booking_ticket_pdf,
    log_activity,
    create_in_app_notification,
    send_colo_email,
)


def is_admin_user(user):
    return (
        user
        and user.is_authenticated
        and (
            user.is_staff
            or user.is_superuser
            or getattr(user, 'role', None) == 'admin'
        )
    )


class IsAdminUserCustom(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_admin_user(request.user)


class TravellerDashboardView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        if request.user.role != 'traveller':
            return Response(
                {'error': 'Only travellers can access traveller dashboard.'},
                status=status.HTTP_403_FORBIDDEN
            )

        user = request.user

        bookings = TourBooking.objects.filter(traveller=user).select_related('tour', 'tour__guide_group')
        trips = Trip.objects.filter(traveller=user)

        total_booking_amount = bookings.aggregate(total=Sum('total_amount'))['total'] or 0
        total_trip_budget = trips.aggregate(total=Sum('total_budget'))['total'] or 0
        total_trip_expense = Expense.objects.filter(trip__traveller=user).aggregate(total=Sum('amount'))['total'] or 0

        upcoming_bookings = bookings.filter(status__in=['pending', 'confirmed']).order_by('-booking_date')[:5]
        recent_bookings = bookings.order_by('-booking_date')[:5]
        active_trips = trips.filter(status__in=['planning', 'upcoming', 'ongoing']).order_by('-created_at')[:5]

        try:
            from engagement.models import WishlistItem
            wishlist_count = WishlistItem.objects.filter(user=user).count()
            saved_tours = WishlistItem.objects.filter(user=user, item_type='tour').count()
            saved_destinations = WishlistItem.objects.filter(user=user, item_type='destination').count()
        except Exception:
            wishlist_count = 0
            saved_tours = 0
            saved_destinations = 0

        try:
            from engagement.models import Notification
            unread_notifications = Notification.objects.filter(user=user, is_read=False).count()
        except Exception:
            unread_notifications = 0

        return Response({
            'summary': {
                'total_bookings': bookings.count(),
                'pending_bookings': bookings.filter(status='pending').count(),
                'confirmed_bookings': bookings.filter(status='confirmed').count(),
                'completed_bookings': bookings.filter(status='completed').count(),
                'cancelled_bookings': bookings.filter(status='cancelled').count(),
                'total_booking_amount': total_booking_amount,
                'total_trips': trips.count(),
                'active_trips': trips.filter(status__in=['planning', 'upcoming', 'ongoing']).count(),
                'total_trip_budget': total_trip_budget,
                'total_trip_expense': total_trip_expense,
                'remaining_trip_budget': total_trip_budget - total_trip_expense,
                'wishlist_count': wishlist_count,
                'saved_tours': saved_tours,
                'saved_destinations': saved_destinations,
                'unread_notifications': unread_notifications,
            },
            'upcoming_bookings': [
                {
                    'booking_id': b.booking_id,
                    'tour_id': b.tour.tour_id,
                    'tour_name': b.tour.tour_name,
                    'guide_group': b.tour.guide_group.guide_groupname,
                    'status': b.status,
                    'number_of_travellers': b.number_of_travellers,
                    'total_amount': b.total_amount,
                    'booking_date': b.booking_date,
                }
                for b in upcoming_bookings
            ],
            'recent_bookings': [
                {
                    'booking_id': b.booking_id,
                    'tour_id': b.tour.tour_id,
                    'tour_name': b.tour.tour_name,
                    'guide_group': b.tour.guide_group.guide_groupname,
                    'status': b.status,
                    'number_of_travellers': b.number_of_travellers,
                    'total_amount': b.total_amount,
                    'booking_date': b.booking_date,
                }
                for b in recent_bookings
            ],
            'active_trips': [
                {
                    'trip_id': t.trip_id,
                    'trip_name': t.trip_name,
                    'start_date': t.start_date,
                    'end_date': t.end_date,
                    'total_budget': t.total_budget,
                    'status': t.status,
                }
                for t in active_trips
            ]
        })


class ActivityLogListView(generics.ListAPIView):
    serializer_class = ActivityLogSerializer
    permission_classes = (IsAdminUserCustom,)

    def get_queryset(self):
        queryset = ActivityLog.objects.select_related('actor').all()

        action_type = self.request.query_params.get('action_type')
        search = self.request.query_params.get('search')

        if action_type:
            queryset = queryset.filter(action_type=action_type)

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(actor__username__icontains=search)
                | Q(target_model__icontains=search)
            )

        return queryset[:200]


class BookingTicketPDFView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, booking_id):
        try:
            booking = TourBooking.objects.select_related(
                'traveller',
                'tour',
                'tour__guide_group'
            ).get(booking_id=booking_id)
        except TourBooking.DoesNotExist:
            return Response({'error': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        allowed = False

        if request.user == booking.traveller:
            allowed = True

        if is_admin_user(request.user):
            allowed = True

        if request.user.role == 'guide':
            try:
                guide = Guide.objects.get(user=request.user)
                if guide.guide_group == booking.tour.guide_group:
                    allowed = True
            except Guide.DoesNotExist:
                pass

        if not allowed:
            return Response({'error': 'You do not have permission to download this ticket.'}, status=status.HTTP_403_FORBIDDEN)

        log_activity(
            actor=request.user,
            action_type='system',
            title='Booking ticket downloaded',
            description=f'Booking ticket #{booking.booking_id} was downloaded.',
            target_model='TourBooking',
            target_id=booking.booking_id,
            request=request
        )

        return generate_booking_ticket_pdf(booking)


class GuideAvailabilityListCreateView(generics.ListCreateAPIView):
    serializer_class = GuideAvailabilitySerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        queryset = GuideAvailability.objects.select_related('guide_group', 'created_by')

        guide_group_id = self.request.query_params.get('guide_group')
        status_filter = self.request.query_params.get('status')

        if is_admin_user(user):
            if guide_group_id:
                queryset = queryset.filter(guide_group_id=guide_group_id)
        elif user.role == 'guide':
            try:
                guide = Guide.objects.get(user=user)
                queryset = queryset.filter(guide_group=guide.guide_group)
            except Guide.DoesNotExist:
                queryset = GuideAvailability.objects.none()
        else:
            queryset = GuideAvailability.objects.filter(status='available')

            if guide_group_id:
                queryset = queryset.filter(guide_group_id=guide_group_id)

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user

        if user.role == 'guide':
            guide = Guide.objects.get(user=user)
            guide_group = guide.guide_group
        elif is_admin_user(user):
            guide_group = serializer.validated_data.get('guide_group')
        else:
            raise PermissionError('Only guide or admin can create availability.')

        start_date = serializer.validated_data['start_date']
        end_date = serializer.validated_data['end_date']

        overlap = GuideAvailability.objects.filter(
            guide_group=guide_group,
            start_date__lte=end_date,
            end_date__gte=start_date
        ).exists()

        if overlap:
            raise ValueError('An availability slot already exists for this date range.')

        availability = serializer.save(
            guide_group=guide_group,
            created_by=user
        )

        log_activity(
            actor=user,
            action_type='create',
            title='Guide availability added',
            description=f'{guide_group.guide_groupname}: {availability.start_date} to {availability.end_date} ({availability.status})',
            target_model='GuideAvailability',
            target_id=availability.id,
            request=self.request
        )

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Guide.DoesNotExist:
            return Response({'error': 'Guide profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GuideAvailabilityDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = GuideAvailabilitySerializer
    permission_classes = (permissions.IsAuthenticated,)
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user

        if is_admin_user(user):
            return GuideAvailability.objects.all()

        if user.role == 'guide':
            try:
                guide = Guide.objects.get(user=user)
                return GuideAvailability.objects.filter(guide_group=guide.guide_group)
            except Guide.DoesNotExist:
                return GuideAvailability.objects.none()

        return GuideAvailability.objects.none()

    def perform_update(self, serializer):
        availability = serializer.save()

        log_activity(
            actor=self.request.user,
            action_type='update',
            title='Guide availability updated',
            description=f'{availability.guide_group.guide_groupname}: {availability.start_date} to {availability.end_date} ({availability.status})',
            target_model='GuideAvailability',
            target_id=availability.id,
            request=self.request
        )

    def perform_destroy(self, instance):
        log_activity(
            actor=self.request.user,
            action_type='delete',
            title='Guide availability deleted',
            description=f'{instance.guide_group.guide_groupname}: {instance.start_date} to {instance.end_date}',
            target_model='GuideAvailability',
            target_id=instance.id,
            request=self.request
        )

        instance.delete()


class GuideAvailabilityCheckView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        guide_group_id = request.query_params.get('guide_group')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not guide_group_id or not start_date or not end_date:
            return Response(
                {'error': 'guide_group, start_date, and end_date are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        unavailable_slots = GuideAvailability.objects.filter(
            guide_group_id=guide_group_id,
            status__in=['unavailable', 'booked'],
            start_date__lte=end_date,
            end_date__gte=start_date
        )

        return Response({
            'available': not unavailable_slots.exists(),
            'conflicts': GuideAvailabilitySerializer(unavailable_slots, many=True).data
        })


class DestinationMapDataView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        destinations = Destination.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)

        return Response([
            {
                'destination_id': d.destination_id,
                'name': d.name,
                'location': d.location,
                'destination_type': d.destination_type,
                'latitude': d.latitude,
                'longitude': d.longitude,
                'average_rating': d.average_rating,
                'url': f'/destinations/{d.destination_id}',
            }
            for d in destinations
        ])


class TourRouteMapDataView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, tour_id):
        try:
            tour = Tour.objects.get(tour_id=tour_id)
        except Tour.DoesNotExist:
            return Response({'error': 'Tour not found.'}, status=status.HTTP_404_NOT_FOUND)

        points = []

        for td in tour.destinations.select_related('destination').order_by('order'):
            d = td.destination

            if d.latitude and d.longitude:
                points.append({
                    'order': td.order,
                    'destination_id': d.destination_id,
                    'name': d.name,
                    'location': d.location,
                    'latitude': d.latitude,
                    'longitude': d.longitude,
                    'arrival_date': td.arrival_date,
                    'departure_date': td.departure_date,
                    'arrival_time': td.arrival_time,
                    'departure_time': td.departure_time,
                })

        return Response({
            'tour_id': tour.tour_id,
            'tour_name': tour.tour_name,
            'points': points
        })


class ContactMessageListCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Only admin can view contact messages.'},
                status=status.HTTP_403_FORBIDDEN
            )

        queryset = ContactMessage.objects.select_related('user').all()

        status_filter = request.query_params.get('status')
        search = request.query_params.get('search')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(subject__icontains=search)
                | Q(message__icontains=search)
                | Q(user__username__icontains=search)
            )

        serializer = ContactMessageSerializer(
            queryset[:200],
            many=True,
            context={'request': request}
        )

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        user = request.user

        if getattr(user, 'role', None) == 'admin' or user.is_staff or user.is_superuser:
            return Response(
                {'error': 'Admin users do not need to send contact messages.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if getattr(user, 'role', None) not in ['traveller', 'guide']:
            return Response(
                {'error': 'Only traveller and guide users can send contact messages.'},
                status=status.HTTP_403_FORBIDDEN
            )

        subject = request.data.get('subject', '').strip()
        message = request.data.get('message', '').strip()

        if not subject:
            return Response(
                {'error': 'Subject is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not message:
            return Response(
                {'error': 'Message is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_name = user.get_full_name() or user.username
        user_email = user.email or ''

        if not user_email:
            return Response(
                {'error': 'Your account does not have an email address.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        contact_message = ContactMessage.objects.create(
            user=user,
            user_role=user.role,
            name=user_name,
            email=user_email,
            subject=subject,
            message=message,
            status='new'
        )

        try:
            log_activity(
                actor=user,
                action_type='create',
                title='New contact message received',
                description=f'{user_name} sent a contact message: {subject}',
                target_model='ContactMessage',
                target_id=contact_message.id,
                request=request
            )
        except Exception as e:
            print(f'Contact activity log failed: {str(e)}')

        try:
            admins = User.objects.filter(
                Q(role='admin') | Q(is_staff=True) | Q(is_superuser=True)
            ).distinct()

            for admin in admins:
                try:
                    create_in_app_notification(
                        admin,
                        'New contact message',
                        f'{user_name} sent: {subject}',
                        'admin',
                        '/admin/contact-messages'
                    )
                except Exception as e:
                    print(f'Admin contact notification failed for {admin.id}: {str(e)}')

                try:
                    if admin.email:
                        send_colo_email(
                            admin.email,
                            'New Contact Message - Colo Ghuri',
                            f"""
A new contact message has been submitted.

Name: {user_name}
Email: {user_email}
Role: {user.role}
Subject: {subject}

Message:
{message}

Please check the admin panel.
"""
                        )
                except Exception as e:
                    print(f'Admin contact email failed for {admin.id}: {str(e)}')

        except Exception as e:
            print(f'Admin notification loop failed: {str(e)}')

        return Response(
            {
                'message': 'Your message has been sent successfully.',
                'data': ContactMessageSerializer(
                    contact_message,
                    context={'request': request}
                ).data,
            },
            status=status.HTTP_201_CREATED
        )


class ContactMessageDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def patch(self, request, message_id):
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Only admin can update contact messages.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            contact_message = ContactMessage.objects.get(id=message_id)
        except ContactMessage.DoesNotExist:
            return Response(
                {'error': 'Contact message not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ContactMessageAdminUpdateSerializer(
            contact_message,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            updated_message = serializer.save()

            try:
                log_activity(
                    actor=request.user,
                    action_type='update',
                    title='Contact message updated',
                    description=f'Contact message #{updated_message.id} was updated.',
                    target_model='ContactMessage',
                    target_id=updated_message.id,
                    request=request
                )
            except Exception as e:
                print(f'Contact update activity log failed: {str(e)}')

            return Response(
                ContactMessageSerializer(
                    updated_message,
                    context={'request': request}
                ).data,
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, message_id):
        if not is_admin_user(request.user):
            return Response(
                {'error': 'Only admin can delete contact messages.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            contact_message = ContactMessage.objects.get(id=message_id)
        except ContactMessage.DoesNotExist:
            return Response(
                {'error': 'Contact message not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            log_activity(
                actor=request.user,
                action_type='delete',
                title='Contact message deleted',
                description=f'Contact message from {contact_message.name} was deleted.',
                target_model='ContactMessage',
                target_id=contact_message.id,
                request=request
            )
        except Exception as e:
            print(f'Contact delete activity log failed: {str(e)}')

        contact_message.delete()

        return Response(
            {'message': 'Contact message deleted successfully.'},
            status=status.HTTP_200_OK
        )