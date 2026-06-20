from django.db.models import Avg
from rest_framework import serializers

from .models import Tour, TourImage, TourDestination, FoodPlan, TourBooking
from destinations.serializers import DestinationSerializer
from guides.serializers import GuideGroupSerializer


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
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class TourSerializer(serializers.ModelSerializer):
    destinations = TourDestinationSerializer(many=True, read_only=True)
    images = TourImageSerializer(many=True, read_only=True)
    guide_group_details = GuideGroupSerializer(source='guide_group', read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    booked_seats = serializers.IntegerField(read_only=True)
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
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

    def get_cover_image_url(self, obj):
        request = self.context.get('request')

        if obj.cover_image:
            return request.build_absolute_uri(obj.cover_image.url) if request else obj.cover_image.url

        first_image = obj.images.filter(is_primary=True).first()
        if not first_image:
            first_image = obj.images.first()

        if first_image and first_image.image:
            return request.build_absolute_uri(first_image.image.url) if request else first_image.image.url

        return None

    def get_rating_average(self, obj):
        from engagement.models import TourReview

        avg = TourReview.objects.filter(tour=obj).aggregate(avg=Avg('rating'))['avg'] or 0
        return round(avg, 2)

    def get_review_count(self, obj):
        from engagement.models import TourReview

        return TourReview.objects.filter(tour=obj).count()

    def get_is_wishlisted(self, obj):
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
    tour_details = TourSerializer(source='tour', read_only=True)
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