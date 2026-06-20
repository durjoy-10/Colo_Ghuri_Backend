from rest_framework import serializers

from .models import WishlistItem, DestinationReview, TourReview, Notification


class WishlistItemSerializer(serializers.ModelSerializer):
    item_title = serializers.SerializerMethodField()
    item_subtitle = serializers.SerializerMethodField()
    item_image = serializers.SerializerMethodField()
    item_url = serializers.SerializerMethodField()
    item_price = serializers.SerializerMethodField()

    class Meta:
        model = WishlistItem
        fields = (
            'id',
            'item_type',
            'destination',
            'tour',
            'item_title',
            'item_subtitle',
            'item_image',
            'item_url',
            'item_price',
            'created_at',
        )
        read_only_fields = fields

    def get_item_title(self, obj):
        if obj.item_type == 'destination' and obj.destination:
            return obj.destination.name
        if obj.item_type == 'tour' and obj.tour:
            return obj.tour.tour_name
        return 'Unknown item'

    def get_item_subtitle(self, obj):
        if obj.item_type == 'destination' and obj.destination:
            return obj.destination.location
        if obj.item_type == 'tour' and obj.tour:
            return obj.tour.guide_group.guide_groupname
        return ''

    def get_item_image(self, obj):
        request = self.context.get('request')

        image_url = None

        if obj.item_type == 'destination' and obj.destination:
            primary = obj.destination.images.filter(is_primary=True).first()
            if not primary:
                primary = obj.destination.images.first()
            if primary and primary.image:
                image_url = primary.image.url

        if obj.item_type == 'tour' and obj.tour:
            if obj.tour.cover_image:
                image_url = obj.tour.cover_image.url
            else:
                primary = obj.tour.images.filter(is_primary=True).first()
                if not primary:
                    primary = obj.tour.images.first()
                if primary and primary.image:
                    image_url = primary.image.url

        if image_url and request:
            return request.build_absolute_uri(image_url)

        return image_url

    def get_item_url(self, obj):
        if obj.item_type == 'destination' and obj.destination:
            return f'/destinations/{obj.destination.destination_id}'
        if obj.item_type == 'tour' and obj.tour:
            return f'/tours/{obj.tour.tour_id}'
        return '/'

    def get_item_price(self, obj):
        if obj.item_type == 'destination' and obj.destination:
            return obj.destination.entry_fee
        if obj.item_type == 'tour' and obj.tour:
            return obj.tour.final_price
        return None


class DestinationReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_image = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = DestinationReview
        fields = (
            'id',
            'user',
            'user_name',
            'user_image',
            'destination',
            'rating',
            'comment',
            'image',
            'created_at',
            'updated_at',
            'can_delete',
        )
        read_only_fields = ('id', 'user', 'destination', 'created_at', 'updated_at', 'can_delete')

    def get_user_name(self, obj):
        full_name = obj.user.get_full_name()
        return full_name or obj.user.username

    def get_user_image(self, obj):
        request = self.context.get('request')
        if obj.user.profile_picture:
            url = obj.user.profile_picture.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return (
            request.user.id == obj.user.id
            or request.user.is_staff
            or request.user.is_superuser
            or getattr(request.user, 'role', None) == 'admin'
        )


class TourReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_image = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = TourReview
        fields = (
            'id',
            'user',
            'user_name',
            'user_image',
            'tour',
            'rating',
            'comment',
            'image',
            'created_at',
            'updated_at',
            'can_delete',
        )
        read_only_fields = ('id', 'user', 'tour', 'created_at', 'updated_at', 'can_delete')

    def get_user_name(self, obj):
        full_name = obj.user.get_full_name()
        return full_name or obj.user.username

    def get_user_image(self, obj):
        request = self.context.get('request')
        if obj.user.profile_picture:
            url = obj.user.profile_picture.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return (
            request.user.id == obj.user.id
            or request.user.is_staff
            or request.user.is_superuser
            or getattr(request.user, 'role', None) == 'admin'
        )


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            'id',
            'notification_type',
            'title',
            'message',
            'link',
            'is_read',
            'created_at',
        )
        read_only_fields = fields