from rest_framework import serializers


class ChatbotMessageSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True)
    confirmed_action = serializers.DictField(required=False, allow_null=True)
    def validate(self, attrs):
        message = attrs.get('message', '').strip()
        confirmed_action = attrs.get('confirmed_action')

        if not message and not confirmed_action:
            raise serializers.ValidationError(
                'Either message or confirmed_action is required.'
            )

        return attrs