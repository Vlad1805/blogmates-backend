from django.db import models
from django.contrib.auth.models import User

class BlogEntry(models.Model):
    VISIBILITY_CHOICES = [
        ('public', 'Public'),    # Everyone can see this
        ('friends', 'Friends'), # Only friends of the author can see this
        ('journal', 'Journal'), # Only the author can see this
    ]

    title = models.CharField(max_length=200, unique=True)  # Title of the blog post
    content = models.TextField()  # Large text for the blog content
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # Link to the user who is the author
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public')  # Visibility level
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for creation
    updated_at = models.DateTimeField(auto_now=True)  # Timestamp for updates

    class Meta:
        ordering = ['-created_at']  # Order by newest first

    def __str__(self):
        return self.title

class Friendship(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships')
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friends')
    created_at = models.DateTimeField(auto_now_add=True)  # When the friendship was created

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.follower.username} is following {self.user.username}"

class FriendRequest(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests')
    is_accepted = models.BooleanField(default=False)  # Indicates if the request has been accepted
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')  # Prevent duplicate requests

    def __str__(self):
        return f"Friend request from {self.sender.username} to {self.receiver.username}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.BinaryField(blank=True, null=True)
    profile_picture_content_type = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.user.username

# Add `following` property to get all the user's friends
User.add_to_class(
    'followers', 
    property(lambda u: Friendship.objects.filter(user=u))
)

# Add `followers` property to get all the users who consider the user as a friend
User.add_to_class(
    'following', 
    property(lambda u: Friendship.objects.filter(follower=u))
)

# Add `sent_friend_requests` property to track outgoing requests
User.add_to_class(
    'sent_friend_requests',
    property(lambda u: FriendRequest.objects.filter(sender=u, is_accepted=False))
)

# Add `received_friend_requests` property to track incoming requests
User.add_to_class(
    'received_friend_requests',
    property(lambda u: FriendRequest.objects.filter(receiver=u, is_accepted=False))
)