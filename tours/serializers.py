from decimal import Decimal

from django.db.models import Avg
from rest_framework import serializers

from .models import FoodPlan, Tour, TourBooking, TourDestination, TourImage
from destinations.serializers import DestinationSerializer
from guides.serializers import GuideGroupSerializer


def _build_absolute_url(request, url):
    if not url:
        return None
    return request.build_absolute_uri(url) if request else url


def _prefetched_images(obj):
    images = getattr(obj, 'prefetched_images', None)

    if images is None:
        cache = getattr(obj, '_prefetched_objects_cache', {})
        images = cache.get('images')

    if images is None:
        images = obj.images.all()

    return sorted(list(images), key=lambda image: image.order or 0)


def _primary_tour_image(obj):
    images = _prefetched_images(obj)
    primary = next((image for image in images if image.is_primary), None)
    return primary or (images[0] if images else None)


def _annotated_number(obj, attr_name, fallback):
    value = getattr(obj, attr_name, None)
    if value is not None:
        return value
    return fallback()


class FoodPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodPlan
        fields = '__all__'


class TourDestinationSerializer(serializers.ModelSerializer):
    destination_details = DestinationSerializer(source='destination', read_only=True)
    food_plans = FoodPlanSerializer(many=True, read_only=True)

    class Meta:
        model = TourDestination
        fields = '__all__'


class TourImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = TourImage
        fields = ('image_id', 'image', 'image_url', 'caption', 'is_primary', 'order')

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image:
            return _build_absolute_url(request, obj.image.url)
        return None


class TourListSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    guide_group_name = serializers.CharField(source='guide_group.guide_groupname', read_only=True)
    guide_group_phone = serializers.CharField(source='guide_group.phone_number', read_only=True)
    guide_group_email = serializers.CharField(source='guide_group.email', read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    booked_seats = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()
    rating_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    is_wishlisted = serializers.SerializerMethodField()

    class Meta:
        model = Tour
        fields = (
            'tour_id',
            'tour_name',
            'guide_group',
            'guide_group_name',
            'guide_group_phone',
            'guide_group_email',
            'description',
            'total_seats',
            'available_seats',
            'price_per_person',
            'discount_percentage',
            'final_price',
            'status',
            'created_at',
            'updated_at',
            'cover_image',
            'cover_image_url',
            'images',
            'total_expenses',
            'is_locked',
            'booked_seats',
            'total_revenue',
            'rating_average',
            'review_count',
            'is_wishlisted',
        )
        read_only_fields = fields

    def get_images(self, obj):
        return TourImageSerializer(
            _prefetched_images(obj),
            many=True,
            context=self.context,
        ).data

    def get_cover_image_url(self, obj):
        request = self.context.get('request')

        if obj.cover_image:
            return _build_absolute_url(request, obj.cover_image.url)

        first_image = _primary_tour_image(obj)
        if first_image and first_image.image:
            return _build_absolute_url(request, first_image.image.url)

        return None

    def get_final_price(self, obj):
        return obj.price_per_person * (Decimal('1') - (obj.discount_percentage / Decimal('100')))

    def get_booked_seats(self, obj):
        return int(_annotated_number(obj, 'booked_seats_value', lambda: obj.booked_seats) or 0)

    def get_total_revenue(self, obj):
        return self.get_booked_seats(obj) * self.get_final_price(obj)

    def get_rating_average(self, obj):
        value = getattr(obj, 'rating_average_value', None)
        if value is None:
            from engagement.models import TourReview

            value = TourReview.objects.filter(tour=obj).aggregate(avg=Avg('rating'))['avg'] or 0
        return round(float(value or 0), 2)

    def get_review_count(self, obj):
        value = getattr(obj, 'review_count_value', None)
        if value is None:
            from engagement.models import TourReview

            value = TourReview.objects.filter(tour=obj).count()
        return int(value or 0)

    def get_is_wishlisted(self, obj):
        annotated_value = getattr(obj, 'is_wishlisted_value', None)
        if annotated_value is not None:
            return bool(annotated_value)

        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return False

        from engagement.models import WishlistItem

        return WishlistItem.objects.filter(
            user=request.user,
            item_type='tour',
            tour=obj
        ).exists()


class TourSerializer(serializers.ModelSerializer):
    destinations = TourDestinationSerializer(many=True, read_only=True)
    images = serializers.SerializerMethodField()
    guide_group_details = GuideGroupSerializer(source='guide_group', read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    booked_seats = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()
    rating_average = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    is_wishlisted = serializers.SerializerMethodField()
    user_review = serializers.SerializerMethodField()

    class Meta:
        model = Tour
        fields = '__all__'
        read_only_fields = (
            'tour_id',
            'created_at',
            'updated_at',
            'available_seats',
            'booked_seats',
            'total_revenue',
        )

    def get_images(self, obj):
        return TourImageSerializer(
            _prefetched_images(obj),
            many=True,
            context=self.context,
        ).data

    def get_cover_image_url(self, obj):
        request = self.context.get('request')

        if obj.cover_image:
            return _build_absolute_url(request, obj.cover_image.url)

        first_image = _primary_tour_image(obj)
        if first_image and first_image.image:
            return _build_absolute_url(request, first_image.image.url)

        return None

    def get_final_price(self, obj):
        return obj.price_per_person * (Decimal('1') - (obj.discount_percentage / Decimal('100')))

    def get_booked_seats(self, obj):
        return int(_annotated_number(obj, 'booked_seats_value', lambda: obj.booked_seats) or 0)

    def get_total_revenue(self, obj):
        return self.get_booked_seats(obj) * self.get_final_price(obj)

    def get_rating_average(self, obj):
        value = getattr(obj, 'rating_average_value', None)
        if value is None:
            from engagement.models import TourReview

            value = TourReview.objects.filter(tour=obj).aggregate(avg=Avg('rating'))['avg'] or 0
        return round(float(value or 0), 2)

    def get_review_count(self, obj):
        value = getattr(obj, 'review_count_value', None)
        if value is None:
            from engagement.models import TourReview

            value = TourReview.objects.filter(tour=obj).count()
        return int(value or 0)

    def get_is_wishlisted(self, obj):
        annotated_value = getattr(obj, 'is_wishlisted_value', None)
        if annotated_value is not None:
            return bool(annotated_value)

        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return False

        from engagement.models import WishlistItem

        return WishlistItem.objects.filter(
            user=request.user,
            item_type='tour',
            tour=obj
        ).exists()

    def get_user_review(self, obj):
        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return None

        from engagement.models import TourReview

        review = TourReview.objects.filter(
            user=request.user,
            tour=obj
        ).first()

        if not review:
            return None

        return {
            'id': review.id,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at,
        }


class TourCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tour
        fields = (
            'tour_name',
            'guide_group',
            'description',
            'total_seats',
            'price_per_person',
            'discount_percentage',
            'status',
            'cover_image',
        )


class TourBookingSerializer(serializers.ModelSerializer):
    tour_details = TourListSerializer(source='tour', read_only=True)
    traveller_details = serializers.SerializerMethodField()

    class Meta:
        model = TourBooking
        fields = '__all__'
        read_only_fields = ('booking_id', 'booking_date')
        extra_kwargs = {
            'payment_id': {'required': False, 'allow_blank': True},
            'guide_reference': {'required': False, 'allow_blank': True},
        }

    def get_traveller_details(self, obj):
        from users.serializers import UserSerializer
        return UserSerializer(obj.traveller).data