from rest_framework import serializers
from .models import Destination, DestinationImage, DestinationMap


def _build_absolute_url(request, url):
    if not url:
        return None
    return request.build_absolute_uri(url) if request else url


def _prefetched_images(obj):
    """Return images without creating a new query when views used Prefetch(to_attr)."""
    images = getattr(obj, 'prefetched_images', None)

    if images is None:
        cache = getattr(obj, '_prefetched_objects_cache', {})
        images = cache.get('images')

    if images is None:
        images = obj.images.all()

    return sorted(list(images), key=lambda image: image.order or 0)


def _primary_image(obj):
    images = _prefetched_images(obj)
    primary = next((image for image in images if image.is_primary), None)
    return primary or (images[0] if images else None)


class DestinationImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = DestinationImage
        fields = '__all__'

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image:
            return _build_absolute_url(request, obj.image.url)
        return None


class DestinationMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = DestinationMap
        fields = '__all__'


class DestinationSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
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

    def get_images(self, obj):
        return DestinationImageSerializer(
            _prefetched_images(obj),
            many=True,
            context=self.context,
        ).data

    def get_primary_image(self, obj):
        request = self.context.get('request')
        primary = _primary_image(obj)

        if primary and primary.image:
            return _build_absolute_url(request, primary.image.url)

        return None

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
            item_type='destination',
            destination=obj
        ).exists()

    def get_user_review(self, obj):
        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return None

        prefetched_review = getattr(obj, 'user_review_value', None)
        review = prefetched_review

        if review is None:
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
        primary = _primary_image(obj)

        if primary and primary.image:
            return _build_absolute_url(request, primary.image.url)

        return None

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
            item_type='destination',
            destination=obj
        ).exists()