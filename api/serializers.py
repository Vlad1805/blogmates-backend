from rest_framework import serializers
from django.contrib.auth.models import User
from .models import BlogEntry, UserProfile, Friendship, FriendRequest
import base64

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
        
        # Create a UserProfile for the new user
        UserProfile.objects.create(user=user)
        
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
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    
    # Follower and Following counts (using properties you added to the User model)
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    friendship_status = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile_picture', 'profile_picture_content_type', 'follower_count', 'following_count', 'friendship_status', 'biography']

    def get_follower_count(self, obj):
        # Use the 'followers' property added to the User model to get the count
        return obj.user.followers.count()

    def get_following_count(self, obj):
        # Use the 'following' property added to the User model to get the count
        return obj.user.following.count()

    def get_friendship_status(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        current_user = request.user
        target_user = obj.user

        # Check if they are friends
        if Friendship.objects.filter(user=target_user, follower=current_user).exists():
            return 'following'
        
        # Check if there's a pending friend request
        if FriendRequest.objects.filter(sender=current_user, receiver=target_user, is_accepted=False).exists():
            return 'request_sent'
        
        return None

    def to_representation(self, instance):
        """Convert the binary image data to base64 for JSON serialization."""
        ret = super().to_representation(instance)
        if instance.profile_picture:
            ret['profile_picture'] = base64.b64encode(instance.profile_picture).decode('utf-8')
        return ret

    def to_internal_value(self, data):
        """Convert image data to binary for storage."""
        ret = super().to_internal_value(data)
        if 'profile_picture' in data:
            profile_picture = data['profile_picture']
            if hasattr(profile_picture, 'read'):  # It's a file upload
                ret['profile_picture'] = profile_picture.read()
            else:  # It's a base64 string
                ret['profile_picture'] = base64.b64decode(profile_picture)
            ret['profile_picture_content_type'] = data.get('profile_picture_content_type', 'image/jpeg')
        return ret

