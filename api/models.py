from django.db import models
from django.contrib.auth.models import User

class BlogEntry(models.Model):
    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('friends', 'Friends'),
        ('journal', 'Journal'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('title', 'author')

    def __str__(self):
        return self.title
    
class BlogComment(models.Model):
    blog_entry = models.ForeignKey(BlogEntry, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class BlogLike(models.Model):
    blog_entry = models.ForeignKey(BlogEntry, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
class CommentLike(models.Model):
    comment = models.ForeignKey(BlogComment, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class Friendship(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships')
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friends')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.follower.username} is following {self.user.username}"

class FriendRequest(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests')
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"Friend request from {self.sender.username} to {self.receiver.username}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.BinaryField(blank=True, null=True)
    profile_picture_content_type = models.CharField(max_length=100, blank=True, null=True)
    biography = models.TextField(blank=True, null=True, max_length=500)

    def __str__(self):
        return self.user.username

User.add_to_class(
    'followers', 
    property(lambda u: Friendship.objects.filter(user=u))
)

User.add_to_class(
    'following', 
    property(lambda u: Friendship.objects.filter(follower=u))
)

User.add_to_class(
    'sent_friend_requests',
    property(lambda u: FriendRequest.objects.filter(sender=u, is_accepted=False))
)

User.add_to_class(
    'received_friend_requests',
    property(lambda u: FriendRequest.objects.filter(receiver=u, is_accepted=False))
)