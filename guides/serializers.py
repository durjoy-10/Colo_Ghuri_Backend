from rest_framework import serializers
from .models import Guide, GuideGroup, GuideGroupMember
from users.models import User


class PublicGuideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guide
        fields = (
            'guide_id', 'name', 'username', 'email', 'phone_number', 'gender',
            'experience_years', 'languages_spoken', 'bio', 'rating',
            'total_tours', 'is_active', 'has_set_password'
        )
        read_only_fields = fields


class GuideGroupSerializer(serializers.ModelSerializer):
    guides = serializers.SerializerMethodField()

    class Meta:
        model = GuideGroup
        fields = (
            'guide_group_id', 'guide_groupname', 'guide_group_picture',
            'guide_group_number', 'is_verified', 'created_at', 'email',
            'phone_number', 'address', 'description', 'guides'
        )
        read_only_fields = ('guide_group_id', 'created_at', 'is_verified', 'guides')

    def get_guides(self, obj):
        guides = obj.guides.all().order_by('guide_id')
        return PublicGuideSerializer(guides, many=True, context=self.context).data


class GuideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guide
        fields = '__all__'
        read_only_fields = ('guide_id', 'joined_date', 'rating', 'total_tours', 'has_set_password')


class GuideGroupMemberSerializer(serializers.ModelSerializer):
    guide_details = GuideSerializer(source='guide', read_only=True)

    class Meta:
        model = GuideGroupMember
        fields = '__all__'


class GuideGroupRegistrationSerializer(serializers.Serializer):
    guide_groupname = serializers.CharField(max_length=100)
    group_email = serializers.EmailField()
    group_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    group_address = serializers.CharField(required=False, allow_blank=True)
    group_description = serializers.CharField(required=False, allow_blank=True)
    guide_group_number = serializers.IntegerField(min_value=1, max_value=8)

    guides = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=8,
    )

    def validate(self, data):
        expected_number = data.get('guide_group_number', len(data.get('guides', [])))
        actual_number = len(data.get('guides', []))

        if actual_number != expected_number:
            raise serializers.ValidationError(
                f"Number of guides ({actual_number}) doesn't match group size ({expected_number})"
            )

        usernames = [g.get('username') for g in data.get('guides', [])]
        emails = [g.get('email') for g in data.get('guides', [])]
        national_ids = [g.get('national_id') for g in data.get('guides', [])]

        if len(usernames) != len(set(usernames)):
            raise serializers.ValidationError('Duplicate usernames in guide group')

        if len(emails) != len(set(emails)):
            raise serializers.ValidationError('Duplicate emails in guide group')

        if len(national_ids) != len(set(national_ids)):
            raise serializers.ValidationError('Duplicate national IDs in guide group')

        for idx, guide in enumerate(data.get('guides', [])):
            if not guide.get('username'):
                raise serializers.ValidationError(f'Guide {idx + 1}: Username is required')
            if not guide.get('email'):
                raise serializers.ValidationError(f'Guide {idx + 1}: Email is required')
            if not guide.get('national_id'):
                raise serializers.ValidationError(f'Guide {idx + 1}: National ID is required')

        for guide in data.get('guides', []):
            if User.objects.filter(username=guide.get('username')).exists():
                raise serializers.ValidationError(f"Username '{guide.get('username')}' already exists")
            if User.objects.filter(email=guide.get('email')).exists():
                raise serializers.ValidationError(f"Email '{guide.get('email')}' already exists")
            if Guide.objects.filter(username=guide.get('username')).exists():
                raise serializers.ValidationError(f"Guide username '{guide.get('username')}' already exists")
            if Guide.objects.filter(email=guide.get('email')).exists():
                raise serializers.ValidationError(f"Guide email '{guide.get('email')}' already exists")
            if Guide.objects.filter(national_id=guide.get('national_id')).exists():
                raise serializers.ValidationError(f"National ID '{guide.get('national_id')}' already exists")

        return data

    def create(self, validated_data):
        guide_group = GuideGroup.objects.create(
            guide_groupname=validated_data['guide_groupname'],
            email=validated_data['group_email'],
            phone_number=validated_data.get('group_phone', ''),
            address=validated_data.get('group_address', ''),
            description=validated_data.get('group_description', ''),
            guide_group_number=validated_data['guide_group_number'],
            is_verified=False,
        )

        created_guides = []

        for idx, guide_data in enumerate(validated_data['guides']):
            gender_value = guide_data.get('gender', 'M')
            if gender_value == 'male':
                gender_value = 'M'
            elif gender_value == 'female':
                gender_value = 'F'
            elif gender_value not in ['M', 'F']:
                gender_value = 'M'

            guide = Guide.objects.create(
                guide_group=guide_group,
                name=f"{guide_data.get('first_name', '')} {guide_data.get('last_name', '')}".strip() or guide_data['username'],
                username=guide_data['username'],
                email=guide_data['email'],
                national_id=guide_data.get('national_id', ''),
                phone_number=guide_data.get('phone_number', ''),
                gender=gender_value,
                experience_years=guide_data.get('experience_years', 0),
                languages_spoken=guide_data.get('languages_spoken', 'Bengali, English'),
                bio=guide_data.get('bio', ''),
                user=None,
                is_active=False,
            )

            GuideGroupMember.objects.create(
                guide_group=guide_group,
                guide=guide,
                index=idx + 1,
            )

            created_guides.append(guide)

        return {
            'guide_group': guide_group,
            'guides': created_guides,
        }