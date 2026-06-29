from rest_framework import generics, permissions, filters, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import BasePermission
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Avg, Count, Exists, FloatField, IntegerField, OuterRef, Prefetch, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from .models import Tour, TourImage, TourBooking, TourDestination, FoodPlan
from destinations.models import DestinationImage
from .serializers import (
    TourSerializer,
    TourListSerializer,
    TourCreateUpdateSerializer,
    TourImageSerializer,
    TourBookingSerializer,
    TourDestinationSerializer,
    FoodPlanSerializer,
)
from decimal import Decimal
from operations.utils import (
    log_activity,
    send_booking_created_email,
    send_booking_status_email,
    send_tour_completed_email,
)
from operations.models import GuideAvailability


def _tour_image_queryset():
    return TourImage.objects.only(
        'image_id',
        'tour_id',
        'image',
        'caption',
        'is_primary',
        'order',
    ).order_by('order')


def _optimized_tour_queryset(request=None):
    """Shared queryset for fast tour cards and nested booking tour details."""
    from engagement.models import TourReview, WishlistItem

    booked_subquery = TourBooking.objects.filter(
        tour_id=OuterRef('pk'),
        status__in=['confirmed', 'completed'],
    ).values('tour_id').annotate(
        total=Sum('number_of_travellers')
    ).values('total')[:1]

    review_count_subquery = TourReview.objects.filter(
        tour_id=OuterRef('pk')
    ).values('tour_id').annotate(
        total=Count('pk')
    ).values('total')[:1]

    rating_average_subquery = TourReview.objects.filter(
        tour_id=OuterRef('pk')
    ).values('tour_id').annotate(
        avg=Avg('rating')
    ).values('avg')[:1]

    queryset = Tour.objects.select_related('guide_group').prefetch_related(
        Prefetch('images', queryset=_tour_image_queryset(), to_attr='prefetched_images')
    ).annotate(
        booked_seats_value=Coalesce(
            Subquery(booked_subquery, output_field=IntegerField()),
            Value(0),
        ),
        review_count_value=Coalesce(
            Subquery(review_count_subquery, output_field=IntegerField()),
            Value(0),
        ),
        rating_average_value=Coalesce(
            Subquery(rating_average_subquery, output_field=FloatField()),
            Value(0.0),
        ),
    )

    if request is not None and request.user.is_authenticated:
        wishlist_subquery = WishlistItem.objects.filter(
            user=request.user,
            item_type='tour',
            tour_id=OuterRef('pk'),
        )
        queryset = queryset.annotate(is_wishlisted_value=Exists(wishlist_subquery))

    return queryset


def _optimized_tour_detail_queryset(request=None):
    from guides.models import Guide

    destination_queryset = TourDestination.objects.select_related('destination').prefetch_related(
        'food_plans',
        Prefetch('destination__images', queryset=DestinationImage.objects.only(
            'id',
            'destination_id',
            'image',
            'caption',
            'is_primary',
            'order',
        ).order_by('order'), to_attr='prefetched_images'),
    ).order_by('order')

    return _optimized_tour_queryset(request).prefetch_related(
        Prefetch('destinations', queryset=destination_queryset),
        Prefetch('guide_group__guides', queryset=Guide.objects.all().order_by('guide_id'), to_attr='prefetched_guides'),
    )


class IsGuideOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['guide', 'admin']


class IsGuideVerified(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == 'admin' or 
            (request.user.role == 'guide' and request.user.is_verified)
        )


class TourListView(generics.ListAPIView):
    serializer_class = TourListSerializer
    permission_classes = (permissions.AllowAny,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'tour_name',
        'description',
        'guide_group__guide_groupname',
        'destinations__destination__name',
        'destinations__destination__location',
    ]
    ordering_fields = ['price_per_person', 'created_at', 'total_seats', 'available_seats']

    def get_queryset(self):
        queryset = _optimized_tour_queryset(self.request)

        if not self.request.user.is_authenticated:
            queryset = queryset.filter(status='upcoming')
        elif self.request.user.role == 'guide':
            from guides.models import Guide
            try:
                guide = Guide.objects.get(user=self.request.user)
                queryset = queryset.filter(guide_group=guide.guide_group)
            except Guide.DoesNotExist:
                return Tour.objects.none()
        elif self.request.user.role == 'admin':
            queryset = queryset.all()
        else:
            queryset = queryset.filter(status='upcoming')

        status_filter = self.request.query_params.get('status')
        guide_group = self.request.query_params.get('guide_group')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        available_only = self.request.query_params.get('available_only')
        min_seats = self.request.query_params.get('min_seats')
        has_discount = self.request.query_params.get('has_discount')
        destination_type = self.request.query_params.get('destination_type')
        location = self.request.query_params.get('location')
        ordering = self.request.query_params.get('ordering')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if guide_group:
            queryset = queryset.filter(guide_group_id=guide_group)

        if min_price:
            queryset = queryset.filter(price_per_person__gte=min_price)

        if max_price:
            queryset = queryset.filter(price_per_person__lte=max_price)

        if available_only in ['true', 'True', '1']:
            queryset = queryset.filter(available_seats__gt=0)

        if min_seats:
            queryset = queryset.filter(available_seats__gte=min_seats)

        if has_discount in ['true', 'True', '1']:
            queryset = queryset.filter(discount_percentage__gt=0)

        if destination_type:
            queryset = queryset.filter(destinations__destination__destination_type=destination_type)

        if location:
            queryset = queryset.filter(destinations__destination__location__icontains=location)

        ordering_map = {
            'price_asc': 'price_per_person',
            'price_desc': '-price_per_person',
            'newest': '-created_at',
            'oldest': 'created_at',
            'seats_desc': '-available_seats',
            'seats_asc': 'available_seats',
        }

        if ordering in ordering_map:
            queryset = queryset.order_by(ordering_map[ordering])
        else:
            queryset = queryset.order_by('-created_at')

        return queryset.distinct()


class TourDetailView(generics.RetrieveAPIView):
    serializer_class = TourSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = 'tour_id'

    def get_queryset(self):
        return _optimized_tour_detail_queryset(self.request)


class TourCreateView(generics.CreateAPIView):
    queryset = Tour.objects.all()
    serializer_class = TourCreateUpdateSerializer
    permission_classes = (IsGuideVerified,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    
    def post(self, request, *args, **kwargs):
        print("=" * 50)
        print("CREATE TOUR REQUEST")
        print(f"User: {request.user.username}, Role: {request.user.role}")
        
        if request.user.role == 'guide':
            from guides.models import Guide
            try:
                guide = Guide.objects.get(user=request.user)
                guide_group_id = guide.guide_group.guide_group_id
            except Guide.DoesNotExist:
                return Response(
                    {'error': 'Guide profile not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            guide_group_id = request.data.get('guide_group')
            if not guide_group_id:
                return Response(
                    {'error': 'guide_group is required for admin'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Extract data
        if hasattr(request.data, 'get'):
            tour_name = request.data.get('tour_name')
            description = request.data.get('description')
            total_seats = request.data.get('total_seats')
            price_per_person = request.data.get('price_per_person')
            discount_percentage = request.data.get('discount_percentage', 0)
            status_val = request.data.get('status', 'upcoming')
        else:
            tour_name = request.data.get('tour_name')
            description = request.data.get('description')
            total_seats = request.data.get('total_seats')
            price_per_person = request.data.get('price_per_person')
            discount_percentage = request.data.get('discount_percentage', 0)
            status_val = request.data.get('status', 'upcoming')
        
        # Validate
        errors = {}
        if not tour_name:
            errors['tour_name'] = 'This field is required'
        if not description:
            errors['description'] = 'This field is required'
        if not total_seats:
            errors['total_seats'] = 'This field is required'
        if not price_per_person:
            errors['price_per_person'] = 'This field is required'
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        from guides.models import GuideGroup
        try:
            guide_group = GuideGroup.objects.get(guide_group_id=guide_group_id)
        except GuideGroup.DoesNotExist:
            return Response(
                {'error': f'Guide group not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            with transaction.atomic():
                tour = Tour.objects.create(
                    tour_name=tour_name,
                    description=description,
                    guide_group=guide_group,
                    total_seats=int(total_seats),
                    available_seats=int(total_seats),
                    price_per_person=float(price_per_person),
                    discount_percentage=float(discount_percentage),
                    status=status_val,
                    total_expenses=0,
                    is_locked=False
                )
                
                if 'cover_image' in request.FILES:
                    tour.cover_image = request.FILES['cover_image']
                    tour.save()
                
                serializer = TourSerializer(tour)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to create tour: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class TourUpdateView(generics.UpdateAPIView):
    queryset = Tour.objects.all()
    serializer_class = TourCreateUpdateSerializer
    permission_classes = (IsGuideVerified,)
    lookup_field = 'tour_id'
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    
    def update(self, request, *args, **kwargs):
        tour = self.get_object()
        print(f"Updating tour {tour.tour_id}")
        
        if tour.is_locked:
            return Response(
                {'error': 'This tour is completed and locked. Cannot edit.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.user.role == 'guide':
            from guides.models import Guide
            try:
                guide = Guide.objects.get(user=request.user)
                if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                    return Response(
                        {'error': 'You do not have permission to update this tour'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Guide.DoesNotExist:
                return Response(
                    {'error': 'Guide profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Update fields
        if 'tour_name' in request.data:
            tour.tour_name = request.data['tour_name']
        if 'description' in request.data:
            tour.description = request.data['description']
        if 'total_seats' in request.data:
            new_total = int(request.data['total_seats'])
            if new_total < (tour.total_seats - tour.available_seats):
                return Response(
                    {'error': f'Cannot reduce total seats below booked seats ({tour.total_seats - tour.available_seats})'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            tour.total_seats = new_total
        if 'price_per_person' in request.data:
            tour.price_per_person = float(request.data['price_per_person'])
        if 'discount_percentage' in request.data:
            tour.discount_percentage = float(request.data['discount_percentage'])
        if 'status' in request.data:
            old_status = tour.status
            new_status = request.data['status']
            tour.status = new_status
            
            # If tour is being marked as completed, mark all confirmed bookings as completed
            if new_status == 'completed' and old_status != 'completed':
                TourBooking.objects.filter(tour=tour, status='confirmed').update(status='completed')
        
        if 'cover_image' in request.FILES:
            tour.cover_image = request.FILES['cover_image']
        
        tour.save()
        
        serializer = TourSerializer(tour)
        return Response(serializer.data)


class TourDeleteView(generics.DestroyAPIView):
    queryset = Tour.objects.all()
    permission_classes = (IsGuideVerified,)
    lookup_field = 'tour_id'
    
    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        tour = self.get_object()
        print(f"Deleting tour {tour.tour_id}")
        
        if tour.is_locked:
            return Response(
                {'error': 'Completed tours cannot be deleted.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.user.role == 'guide':
            from guides.models import Guide
            try:
                guide = Guide.objects.get(user=request.user)
                if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                    return Response(
                        {'error': 'You do not have permission to delete this tour'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Guide.DoesNotExist:
                return Response(
                    {'error': 'Guide profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        try:
            # Delete all related data in correct order
            # 1. Delete FoodPlans
            FoodPlan.objects.filter(tour_destination__tour=tour).delete()
            # 2. Delete TourDestinations
            TourDestination.objects.filter(tour=tour).delete()
            # 3. Delete TourImages
            TourImage.objects.filter(tour=tour).delete()
            # 4. Delete TourBookings
            TourBooking.objects.filter(tour=tour).delete()
            # 5. Finally delete the tour
            tour.delete()
            
            return Response({'message': 'Tour and all related data deleted successfully'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to delete tour: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


class TourCompleteView(APIView):
    permission_classes = (IsGuideVerified,)

    def post(self, request, tour_id):
        try:
            tour = Tour.objects.get(tour_id=tour_id)

            if request.user.role == 'guide':
                from guides.models import Guide

                try:
                    guide = Guide.objects.get(user=request.user)

                    if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                        return Response(
                            {'error': 'You do not have permission to complete this tour'},
                            status=status.HTTP_403_FORBIDDEN
                        )

                except Guide.DoesNotExist:
                    return Response(
                        {'error': 'Guide profile not found'},
                        status=status.HTTP_403_FORBIDDEN
                    )

            expenses = request.data.get('total_expenses', 0)

            tour.status = 'completed'
            tour.total_expenses = Decimal(str(expenses))
            tour.is_locked = True
            tour.save()

            completed_bookings = TourBooking.objects.filter(tour=tour, status='confirmed')

            for booking in completed_bookings:
                booking.status = 'completed'
                booking.save(update_fields=['status'])
                send_tour_completed_email(booking)

            log_activity(
                actor=request.user,
                action_type='update',
                title='Tour marked as completed',
                description=f'{tour.tour_name} was completed and locked.',
                target_model='Tour',
                target_id=tour.tour_id,
                request=request
            )

            return Response({
                'message': 'Tour marked as completed',
                'total_revenue': float(tour.total_revenue),
                'total_expenses': float(tour.total_expenses),
                'net_profit': float(tour.net_profit)
            })

        except Tour.DoesNotExist:
            return Response({'error': 'Tour not found'}, status=status.HTTP_404_NOT_FOUND)

class UpdateBookingStatusView(APIView):
    permission_classes = (IsGuideVerified,)

    def patch(self, request, booking_id):
        try:
            booking = TourBooking.objects.get(booking_id=booking_id)
            tour = booking.tour

            if request.user.role == 'guide':
                from guides.models import Guide

                try:
                    guide = Guide.objects.get(user=request.user)

                    if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                        return Response(
                            {'error': 'You do not have permission to update this booking'},
                            status=status.HTTP_403_FORBIDDEN
                        )

                except Guide.DoesNotExist:
                    return Response(
                        {'error': 'Guide profile not found'},
                        status=status.HTTP_403_FORBIDDEN
                    )

            new_status = request.data.get('status')

            if new_status not in ['pending', 'confirmed', 'cancelled', 'completed']:
                return Response(
                    {'error': 'Invalid status'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if tour.is_locked and new_status != 'completed':
                return Response(
                    {'error': 'Cannot change booking status for completed tours'},
                    status=status.HTTP_403_FORBIDDEN
                )

            old_status = booking.status

            if new_status == 'cancelled' and old_status != 'cancelled':
                booking.cancel()
                message = f'Booking cancelled. {booking.number_of_travellers} seat(s) released.'
            else:
                booking.status = new_status
                booking.save()
                message = f'Booking status updated from {old_status} to {new_status}'

            log_activity(
                actor=request.user,
                action_type='update',
                title='Booking status updated',
                description=f'Booking #{booking.booking_id}: {old_status} to {new_status}',
                target_model='TourBooking',
                target_id=booking.booking_id,
                request=request
            )

            if old_status != new_status:
                send_booking_status_email(booking, old_status, new_status)

            return Response({
                'message': message,
                'booking': {
                    'id': booking.booking_id,
                    'status': booking.status,
                    'tour_name': booking.tour.tour_name,
                    'traveller_name': booking.traveller.get_full_name() or booking.traveller.username,
                    'total_amount': float(booking.total_amount),
                    'available_seats': tour.available_seats
                }
            })

        except TourBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

class TourImageUploadView(generics.CreateAPIView):
    serializer_class = TourImageSerializer
    permission_classes = (IsGuideVerified,)
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request, *args, **kwargs):
        tour_id = request.POST.get('tour') or request.data.get('tour')
        
        if not tour_id:
            return Response({'error': 'tour ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            tour = Tour.objects.get(tour_id=tour_id)
        except Tour.DoesNotExist:
            return Response({'error': 'Tour not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if tour.is_locked:
            return Response(
                {'error': 'Completed tours cannot be modified'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.user.role == 'guide':
            from guides.models import Guide
            try:
                guide = Guide.objects.get(user=request.user)
                if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                    return Response(
                        {'error': 'You do not have permission to add images'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Guide.DoesNotExist:
                return Response(
                    {'error': 'Guide profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        if 'image' not in request.FILES:
            return Response({'error': 'No image file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        image_file = request.FILES['image']
        
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'image/gif', 'image/webp']
        if image_file.content_type not in allowed_types:
            return Response({'error': 'Invalid file type'}, status=status.HTTP_400_BAD_REQUEST)
        
        if image_file.size > 5 * 1024 * 1024:
            return Response({'error': 'File too large (max 5MB)'}, status=status.HTTP_400_BAD_REQUEST)
        
        is_primary = request.POST.get('is_primary', 'false').lower() == 'true'
        
        if is_primary:
            TourImage.objects.filter(tour=tour).update(is_primary=False)
        
        image = TourImage.objects.create(
            tour=tour,
            image=image_file,
            caption=request.POST.get('caption', ''),
            is_primary=is_primary,
            order=TourImage.objects.filter(tour=tour).count() + 1
        )
        
        serializer = TourImageSerializer(image)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TourImageDeleteView(generics.DestroyAPIView):
    queryset = TourImage.objects.all()
    permission_classes = (IsGuideVerified,)
    lookup_field = 'image_id'
    
    def delete(self, request, *args, **kwargs):
        image = self.get_object()
        tour = image.tour
        
        if tour.is_locked:
            return Response(
                {'error': 'Completed tours cannot be modified'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.user.role == 'guide':
            from guides.models import Guide
            try:
                guide = Guide.objects.get(user=request.user)
                if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                    return Response(
                        {'error': 'You do not have permission to delete this image'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Guide.DoesNotExist:
                return Response(
                    {'error': 'Guide profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        image.delete()
        return Response({'message': 'Image deleted successfully'}, status=status.HTTP_200_OK)


class TourImageSetPrimaryView(APIView):
    permission_classes = (IsGuideVerified,)
    
    def patch(self, request, image_id):
        try:
            image = TourImage.objects.get(image_id=image_id)
            tour = image.tour
            
            if tour.is_locked:
                return Response(
                    {'error': 'Completed tours cannot be modified'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if request.user.role == 'guide':
                from guides.models import Guide
                try:
                    guide = Guide.objects.get(user=request.user)
                    if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                        return Response(
                            {'error': 'You do not have permission'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except Guide.DoesNotExist:
                    return Response(
                        {'error': 'Guide profile not found'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            TourImage.objects.filter(tour=tour).update(is_primary=False)
            image.is_primary = True
            image.save()
            
            return Response({'message': 'Primary image updated'})
        except TourImage.DoesNotExist:
            return Response({'error': 'Image not found'}, status=status.HTTP_404_NOT_FOUND)


class BookingCreateView(generics.CreateAPIView):
    queryset = TourBooking.objects.all()
    serializer_class = TourBookingSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        if request.user.role != 'traveller':
            return Response(
                {'error': 'Only travellers can book tours'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data.copy()
        data['traveller'] = request.user.id

        payment_method = data.get('payment_method')

        if payment_method in ['bkash', 'nagad', 'rocket']:
            payment_id = data.get('payment_id')

            if not payment_id:
                return Response(
                    {'error': f'{payment_method.upper()} transaction ID is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if len(payment_id) < 6:
                return Response(
                    {'error': 'Invalid transaction ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if payment_method == 'cash':
            guide_reference = data.get('guide_reference')

            if not guide_reference:
                return Response(
                    {'error': 'Guide reference is required for cash payment'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        tour = serializer.validated_data['tour']
        number_of_travellers = serializer.validated_data['number_of_travellers']

        if tour.available_seats < number_of_travellers:
            return Response(
                {'error': f'Only {tour.available_seats} seats available'},
                status=status.HTTP_400_BAD_REQUEST
            )

        tour.available_seats -= number_of_travellers
        tour.save()

        booking = serializer.save()

        log_activity(
            actor=request.user,
            action_type='booking',
            title='New booking created',
            description=f'{request.user.username} booked {tour.tour_name} for {number_of_travellers} traveller(s).',
            target_model='TourBooking',
            target_id=booking.booking_id,
            request=request
        )

        send_booking_created_email(booking)

        headers = self.get_success_headers(serializer.data)

        return Response(
            TourBookingSerializer(booking, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

class MyBookingsView(generics.ListAPIView):
    serializer_class = TourBookingSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        tour_prefetch = Prefetch('tour', queryset=_optimized_tour_queryset(self.request))
        base_queryset = TourBooking.objects.select_related('traveller').prefetch_related(tour_prefetch).order_by('-booking_date')

        if user.role == 'traveller':
            return base_queryset.filter(traveller=user)

        if user.role == 'guide':
            from guides.models import Guide
            try:
                guide = Guide.objects.get(user=user)
                return base_queryset.filter(tour__guide_group=guide.guide_group)
            except Guide.DoesNotExist:
                return TourBooking.objects.none()

        return TourBooking.objects.none()


# ==================== TOUR DESTINATION AND FOOD PLAN VIEWS ====================

class TourDestinationListView(generics.ListAPIView):
    serializer_class = TourDestinationSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_queryset(self):
        tour_id = self.kwargs.get('tour_id')
        return TourDestination.objects.filter(tour_id=tour_id).select_related('destination').prefetch_related('food_plans')


class TourDestinationCreateView(generics.CreateAPIView):
    serializer_class = TourDestinationSerializer
    permission_classes = (IsGuideVerified,)
    
    def create(self, request, *args, **kwargs):
        tour_id = self.kwargs.get('tour_id')
        try:
            tour = Tour.objects.get(tour_id=tour_id)
            
            if tour.is_locked:
                return Response(
                    {'error': 'Completed tours cannot be modified'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if request.user.role == 'guide':
                from guides.models import Guide
                try:
                    guide = Guide.objects.get(user=request.user)
                    if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                        return Response(
                            {'error': 'You do not have permission'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except Guide.DoesNotExist:
                    return Response(
                        {'error': 'Guide profile not found'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            data = request.data.copy()
            data['tour'] = tour_id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Tour.DoesNotExist:
            return Response({'error': 'Tour not found'}, status=status.HTTP_404_NOT_FOUND)


class TourDestinationDeleteView(generics.DestroyAPIView):
    queryset = TourDestination.objects.all()
    permission_classes = (IsGuideVerified,)
    lookup_field = 'id'
    
    def delete(self, request, *args, **kwargs):
        destination = self.get_object()
        tour = destination.tour
        
        if tour.is_locked:
            return Response(
                {'error': 'Completed tours cannot be modified'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.user.role == 'guide':
            from guides.models import Guide
            try:
                guide = Guide.objects.get(user=request.user)
                if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                    return Response(
                        {'error': 'You do not have permission'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Guide.DoesNotExist:
                return Response(
                    {'error': 'Guide profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        destination.delete()
        return Response({'message': 'Destination removed from tour'}, status=status.HTTP_200_OK)


class FoodPlanCreateView(generics.CreateAPIView):
    serializer_class = FoodPlanSerializer
    permission_classes = (IsGuideVerified,)
    
    def create(self, request, *args, **kwargs):
        tour_destination_id = self.kwargs.get('tour_destination_id')
        try:
            tour_destination = TourDestination.objects.get(id=tour_destination_id)
            tour = tour_destination.tour
            
            if tour.is_locked:
                return Response(
                    {'error': 'Completed tours cannot be modified'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if request.user.role == 'guide':
                from guides.models import Guide
                try:
                    guide = Guide.objects.get(user=request.user)
                    if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                        return Response(
                            {'error': 'You do not have permission'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except Guide.DoesNotExist:
                    return Response(
                        {'error': 'Guide profile not found'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            data = request.data.copy()
            data['tour_destination'] = tour_destination_id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except TourDestination.DoesNotExist:
            return Response({'error': 'Tour destination not found'}, status=status.HTTP_404_NOT_FOUND)


class FoodPlanDeleteView(generics.DestroyAPIView):
    queryset = FoodPlan.objects.all()
    permission_classes = (IsGuideVerified,)
    lookup_field = 'id'
    
    def delete(self, request, *args, **kwargs):
        food_plan = self.get_object()
        tour = food_plan.tour_destination.tour
        
        if tour.is_locked:
            return Response(
                {'error': 'Completed tours cannot be modified'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.user.role == 'guide':
            from guides.models import Guide
            try:
                guide = Guide.objects.get(user=request.user)
                if tour.guide_group.guide_group_id != guide.guide_group.guide_group_id:
                    return Response(
                        {'error': 'You do not have permission'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Guide.DoesNotExist:
                return Response(
                    {'error': 'Guide profile not found'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        food_plan.delete()
        return Response({'message': 'Food plan deleted'}, status=status.HTTP_200_OK)