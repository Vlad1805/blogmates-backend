from rest_framework import serializers
from django.contrib.auth.models import User
from .models import BlogEntry, UserProfile

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
class UserProfileSerializer(serializers.ModelSerializer):
    # Include fields from the User model
    id = serializers.IntegerField(source='user.id')
    username = serializers.CharField(source='user.username')
    email = serializers.EmailField(source='user.email')
    
    # Follower and Following counts (using properties you added to the User model)
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'profile_picture', 'follower_count', 'following_count']

    def get_follower_count(self, obj):
        # Use the 'followers' property added to the User model to get the count
        return obj.user.followers.count()

    def get_following_count(self, obj):
        # Use the 'following' property added to the User model to get the count
        return obj.user.following.count()

