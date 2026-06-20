from rest_framework import serializers
from .models import ActivityLog, GuideAvailability, ContactMessage


class ActivityLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    actor_role = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = (
            'id',
            'actor',
            'actor_name',
            'actor_role',
            'action_type',
            'title',
            'description',
            'target_model',
            'target_id',
            'ip_address',
            'created_at',
        )

    def get_actor_name(self, obj):
        if not obj.actor:
            return 'System'
        return obj.actor.get_full_name() or obj.actor.username

    def get_actor_role(self, obj):
        if not obj.actor:
            return 'system'
        return getattr(obj.actor, 'role', 'user')


class GuideAvailabilitySerializer(serializers.ModelSerializer):
    guide_group_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = GuideAvailability
        fields = (
            'id',
            'guide_group',
            'guide_group_name',
            'start_date',
            'end_date',
            'status',
            'reason',
            'created_by',
            'created_by_name',
            'created_at',
        )
        read_only_fields = ('id', 'created_by', 'created_at')

    def get_guide_group_name(self, obj):
        return obj.guide_group.guide_groupname

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return 'System'
        return obj.created_by.get_full_name() or obj.created_by.username

    def validate(self, attrs):
        start_date = attrs.get('start_date') or getattr(self.instance, 'start_date', None)
        end_date = attrs.get('end_date') or getattr(self.instance, 'end_date', None)

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError('End date cannot be before start date.')

        return attrs


class ContactMessageSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ContactMessage
        fields = (
            'id',
            'user',
            'user_name',
            'user_role',
            'name',
            'email',
            'subject',
            'message',
            'status',
            'admin_reply',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'user',
            'user_name',
            'user_role',
            'name',
            'email',
            'status',
            'admin_reply',
            'created_at',
            'updated_at',
        )

    def get_user_name(self, obj):
        if not obj.user:
            return 'Guest'
        return obj.user.get_full_name() or obj.user.username


class ContactMessageAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = (
            'status',
            'admin_reply',
        )