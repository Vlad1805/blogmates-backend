from rest_framework import serializers
from django.contrib.auth.models import User
from .models import BlogEntry

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        validated_data.pop('password2')  # Remove the extra password field
        user = User.objects.create_user(**validated_data)
        return user

class BlogEntrySerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)  # Fetch the username of the author

    class Meta:
        model = BlogEntry
        fields = ['id', 'title', 'content', 'visibility', 'author', 'author_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'author', 'author_name', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Assign the logged-in user as the author
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)