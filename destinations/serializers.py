from rest_framework import serializers
from .models import Destination, DestinationImage, DestinationMap


class DestinationImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = DestinationImage
        fields = '__all__'

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image:
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class DestinationMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = DestinationMap
        fields = '__all__'


class DestinationSerializer(serializers.ModelSerializer):
    images = DestinationImageSerializer(many=True, read_only=True)
    map_details = DestinationMapSerializer(source='map', read_only=True)
    primary_image = serializers.SerializerMethodField()
    is_wishlisted = serializers.SerializerMethodField()
    user_review = serializers.SerializerMethodField()

    class Meta:
        model = Destination
        fields = '__all__'
        read_only_fields = (
            'destination_id',
            'created_at',
            'updated_at',
            'average_rating',
            'total_reviews',
        )

    def get_primary_image(self, obj):
        request = self.context.get('request')
        primary = obj.images.filter(is_primary=True).first()
        if not primary:
            primary = obj.images.first()

        if primary and primary.image:
            return request.build_absolute_uri(primary.image.url) if request else primary.image.url

        return None

    def get_is_wishlisted(self, obj):
        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return False

        from engagement.models import WishlistItem

        return WishlistItem.objects.filter(
            user=request.user,
            item_type='destination',
            destination=obj
        ).exists()

    def get_user_review(self, obj):
        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return None

        from engagement.models import DestinationReview

        review = DestinationReview.objects.filter(
            user=request.user,
            destination=obj
        ).first()

        if not review:
            return None

        return {
            'id': review.id,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at,
        }


class DestinationListSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    is_wishlisted = serializers.SerializerMethodField()

    class Meta:
        model = Destination
        fields = (
            'destination_id',
            'name',
            'description',
            'location',
            'destination_type',
            'entry_fee',
            'average_rating',
            'total_reviews',
            'best_time_to_visit',
            'opening_hours',
            'is_popular',
            'primary_image',
            'is_wishlisted',
        )

    def get_primary_image(self, obj):
        request = self.context.get('request')
        primary = obj.images.filter(is_primary=True).first()
        if not primary:
            primary = obj.images.first()

        if primary and primary.image:
            return request.build_absolute_uri(primary.image.url) if request else primary.image.url

        return None

    def get_is_wishlisted(self, obj):
        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return False

        from engagement.models import WishlistItem

        return WishlistItem.objects.filter(
            user=request.user,
            item_type='destination',
            destination=obj
        ).exists()