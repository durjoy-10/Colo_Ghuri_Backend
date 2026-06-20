from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 
                  'phone_number', 'national_id', 'profile_picture', 'address', 
                  'is_verified', 'date_joined', 'gender', 'date_of_birth', 
                  'preferred_language', 'email_verified')
        read_only_fields = ('id', 'date_joined', 'is_verified', 'email_verified')

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name', 
                  'phone_number', 'address', 'gender', 'date_of_birth', 'preferred_language')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        validated_data['role'] = 'traveller'
        validated_data['is_verified'] = True
        validated_data['email_verified'] = False  # Set to False, requires email verification
        user = User.objects.create_user(**validated_data)
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 
                  'phone_number', 'national_id', 'profile_picture', 'address', 
                  'is_verified', 'date_joined', 'last_login', 'gender', 'date_of_birth', 
                  'preferred_language', 'email_verified')
        read_only_fields = ('id', 'date_joined', 'last_login', 'is_verified', 'role', 'email_verified')