from django.db.models import Prefetch, Q
from rest_framework import permissions, status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from users.models import User
from destinations.models import Destination, DestinationImage
from tours.models import Tour, TourBooking, TourImage
from guides.models import Guide

from .models import WishlistItem, DestinationReview, TourReview, Notification
from .serializers import (
    WishlistItemSerializer,
    DestinationReviewSerializer,
    TourReviewSerializer,
    NotificationSerializer,
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


def create_notification(user, title, message, notification_type='general', link=''):
    if user and user.is_authenticated:
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )


def notify_admins(title, message, notification_type='admin', link=''):
    admins = User.objects.filter(
        Q(role='admin') | Q(is_staff=True) | Q(is_superuser=True)
    ).distinct()

    notifications = [
        Notification(
            user=admin,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )
        for admin in admins
    ]

    if notifications:
        Notification.objects.bulk_create(notifications)


class WishlistListView(generics.ListAPIView):
    serializer_class = WishlistItemSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        destination_images = DestinationImage.objects.only(
            'id', 'destination_id', 'image', 'caption', 'is_primary', 'order'
        ).order_by('order')
        tour_images = TourImage.objects.only(
            'image_id', 'tour_id', 'image', 'caption', 'is_primary', 'order'
        ).order_by('order')

        return WishlistItem.objects.filter(user=self.request.user).select_related(
            'destination',
            'tour',
            'tour__guide_group',
        ).prefetch_related(
            Prefetch('destination__images', queryset=destination_images, to_attr='prefetched_images'),
            Prefetch('tour__images', queryset=tour_images, to_attr='prefetched_images'),
        ).order_by('-created_at')

    def get_serializer_context(self):
        return {'request': self.request}


class WishlistToggleView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        item_type = request.data.get('item_type')
        object_id = request.data.get('object_id')

        if item_type not in ['destination', 'tour']:
            return Response(
                {'error': 'item_type must be destination or tour.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not object_id:
            return Response(
                {'error': 'object_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if item_type == 'destination':
            try:
                destination = Destination.objects.get(destination_id=object_id)
            except Destination.DoesNotExist:
                return Response({'error': 'Destination not found.'}, status=status.HTTP_404_NOT_FOUND)

            existing = WishlistItem.objects.filter(
                user=request.user,
                item_type='destination',
                destination=destination
            ).first()

            if existing:
                existing.delete()
                return Response({'wishlisted': False, 'message': 'Removed from wishlist.'})

            WishlistItem.objects.create(
                user=request.user,
                item_type='destination',
                destination=destination
            )
            create_notification(
                request.user,
                'Destination saved',
                f'{destination.name} was added to your wishlist.',
                'wishlist',
                f'/destinations/{destination.destination_id}'
            )
            return Response({'wishlisted': True, 'message': 'Added to wishlist.'})

        try:
            tour = Tour.objects.get(tour_id=object_id)
        except Tour.DoesNotExist:
            return Response({'error': 'Tour not found.'}, status=status.HTTP_404_NOT_FOUND)

        existing = WishlistItem.objects.filter(
            user=request.user,
            item_type='tour',
            tour=tour
        ).first()

        if existing:
            existing.delete()
            return Response({'wishlisted': False, 'message': 'Removed from wishlist.'})

        WishlistItem.objects.create(
            user=request.user,
            item_type='tour',
            tour=tour
        )
        create_notification(
            request.user,
            'Tour saved',
            f'{tour.tour_name} was added to your wishlist.',
            'wishlist',
            f'/tours/{tour.tour_id}'
        )
        return Response({'wishlisted': True, 'message': 'Added to wishlist.'})


class WishlistDeleteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self, request, item_id):
        try:
            item = WishlistItem.objects.get(id=item_id, user=request.user)
        except WishlistItem.DoesNotExist:
            return Response({'error': 'Wishlist item not found.'}, status=status.HTTP_404_NOT_FOUND)

        item.delete()
        return Response({'message': 'Wishlist item removed.'}, status=status.HTTP_200_OK)


class DestinationReviewListCreateView(APIView):
    permission_classes = (permissions.AllowAny,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get(self, request, destination_id):
        reviews = DestinationReview.objects.filter(destination_id=destination_id).select_related('user')
        serializer = DestinationReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, destination_id):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required to write a review.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            destination = Destination.objects.get(destination_id=destination_id)
        except Destination.DoesNotExist:
            return Response({'error': 'Destination not found.'}, status=status.HTTP_404_NOT_FOUND)

        existing = DestinationReview.objects.filter(user=request.user, destination=destination).first()

        serializer = DestinationReviewSerializer(
            existing,
            data=request.data,
            partial=True,
            context={'request': request}
        ) if existing else DestinationReviewSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            review = serializer.save(user=request.user, destination=destination)

            notify_admins(
                'New destination review',
                f'{request.user.username} reviewed {destination.name}.',
                'review',
                f'/destinations/{destination.destination_id}'
            )

            return Response(
                DestinationReviewSerializer(review, context={'request': request}).data,
                status=status.HTTP_201_CREATED if not existing else status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TourReviewListCreateView(APIView):
    permission_classes = (permissions.AllowAny,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get(self, request, tour_id):
        reviews = TourReview.objects.filter(tour_id=tour_id).select_related('user')
        serializer = TourReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, tour_id):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required to write a review.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            tour = Tour.objects.select_related('guide_group').get(tour_id=tour_id)
        except Tour.DoesNotExist:
            return Response({'error': 'Tour not found.'}, status=status.HTTP_404_NOT_FOUND)

        if getattr(request.user, 'role', None) != 'traveller':
            return Response({'error': 'Only travellers can review tours.'}, status=status.HTTP_403_FORBIDDEN)

        has_completed_booking = TourBooking.objects.filter(
            tour=tour,
            traveller=request.user,
            status='completed'
        ).exists()

        if not has_completed_booking:
            return Response(
                {'error': 'You can review this tour only after completing a booking.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing = TourReview.objects.filter(user=request.user, tour=tour).first()

        serializer = TourReviewSerializer(
            existing,
            data=request.data,
            partial=True,
            context={'request': request}
        ) if existing else TourReviewSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            review = serializer.save(user=request.user, tour=tour)

            guide_users = []
            try:
                guides = Guide.objects.filter(guide_group=tour.guide_group, user__isnull=False)
                guide_users = [g.user for g in guides if g.user]
            except Exception:
                guide_users = []

            for guide_user in guide_users:
                create_notification(
                    guide_user,
                    'New tour review',
                    f'{request.user.username} reviewed {tour.tour_name}.',
                    'review',
                    f'/tours/{tour.tour_id}'
                )

            notify_admins(
                'New tour review',
                f'{request.user.username} reviewed {tour.tour_name}.',
                'review',
                f'/tours/{tour.tour_id}'
            )

            return Response(
                TourReviewSerializer(review, context={'request': request}).data,
                status=status.HTTP_201_CREATED if not existing else status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReviewDeleteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def delete(self, request, review_type, review_id):
        if review_type == 'destination':
            model = DestinationReview
        elif review_type == 'tour':
            model = TourReview
        else:
            return Response({'error': 'Invalid review type.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            review = model.objects.get(id=review_id)
        except model.DoesNotExist:
            return Response({'error': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)

        if review.user != request.user and not is_admin_user(request.user):
            return Response({'error': 'You do not have permission to delete this review.'}, status=status.HTTP_403_FORBIDDEN)

        review.delete()
        return Response({'message': 'Review deleted successfully.'}, status=status.HTTP_200_OK)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user)

        unread = self.request.query_params.get('unread')
        if unread == 'true':
            queryset = queryset.filter(is_read=False)

        return queryset[:30]


class NotificationUnreadCountView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count})


class NotificationMarkReadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
        except Notification.DoesNotExist:
            return Response({'error': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)

        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'message': 'Notification marked as read.'})


class NotificationMarkAllReadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'message': 'All notifications marked as read.'})