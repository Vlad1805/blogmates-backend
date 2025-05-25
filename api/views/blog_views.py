from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..serializers import SignupSerializer
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from ..models import BlogEntry, FriendRequest, Friendship, BlogComment, BlogLike, CommentLike
from ..serializers import BlogEntrySerializer, BlogCommentSerializer, BlogLikeSerializer, CommentLikeSerializer
from django.db import models
from django.contrib.auth.models import User
from django.db.utils import IntegrityError

class BlogEntryAPIView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]  # Ensure only authenticated users can access
    serializer_class = BlogEntrySerializer

    def get_queryset(self):
        # Retrieve blog entries belonging to the logged-in user
        return BlogEntry.objects.filter(author=self.request.user)

    def perform_create(self, serializer):
        # Automatically set the logged-in user as the author
        serializer.save(author=self.request.user)

class BlogEntryQueryAPIView(APIView):
    permission_classes = [AllowAny]  # Allow public access to view public posts

    def post(self, request):
        """
        Get all blog entries for a specific user that the requesting user can see.
        If no user is logged in, returns only public posts.
        
        Request Body:
        {
            "username": "username_to_query"
        }
        """
        username = request.data.get('username')
        if not username:
            return Response(
                {"error": "Username is required in request body"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get the user whose posts we're querying
            target_user = User.objects.get(username=username)
            
            # Base queryset for the target user's posts
            blog_entries = BlogEntry.objects.filter(author=target_user)

            # Filter based on visibility and authentication
            if request.user.is_authenticated:
                # For authenticated users, show:
                # 1. All their own posts
                # 2. Public posts from others
                # 3. Friends-only posts if they are friends
                if request.user == target_user:
                    # User viewing their own posts - show all
                    pass
                else:
                    # User viewing someone else's posts
                    blog_entries = blog_entries.filter(
                        models.Q(visibility='public') |
                        models.Q(visibility='friends', author__friendships__follower=request.user)
                    )
            else:
                # For unauthenticated users, only show public posts
                blog_entries = blog_entries.filter(visibility='public')

            # Order by newest first
            blog_entries = blog_entries.order_by('-created_at')
            
            serializer = BlogEntrySerializer(blog_entries, many=True)
            return Response(serializer.data)

        except User.DoesNotExist:
            return Response(
                {"error": f"User with username '{username}' not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error retrieving blog entries: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VisibleBlogEntriesView(APIView):
    permission_classes = [AllowAny]  # Allow both authenticated and unauthenticated users
    def get(self, request):
        """
        Get all blog entries that the user can see.
        For authenticated users:
        - Their own entries (all visibility levels)
        - Public entries from others
        - Friends-only entries from their friends
        For unauthenticated users:
        - Only public entries
        """
        if request.user.is_authenticated:
            # For authenticated users, show:
            # 1. Their own entries (all visibility levels)
            # 2. Public entries from others
            # 3. Friends-only entries from their friends
            blog_entries = BlogEntry.objects.filter(
                models.Q(author=request.user) |  # User's own entries
                models.Q(visibility='public') |  # Public entries
                models.Q(visibility='friends', author__friendships__follower=request.user)  # Friends' entries
            ).distinct().order_by('-created_at')  # Order by newest first
        else:
            # For unauthenticated users, only show public entries
            blog_entries = BlogEntry.objects.filter(visibility='public').order_by('-created_at')

        serializer = BlogEntrySerializer(blog_entries, many=True)
        return Response(serializer.data)

class CreateBlogEntryView(APIView):
    permission_classes = [IsAuthenticated]  # Only authenticated users can create blog entries

    def post(self, request):
        """
        Create a new blog entry.
        
        Request Body:
        {
            "title": "Blog Title",
            "content": "Blog Content",
            "visibility": "public" | "friends" | "private"
        }
        """
        try:
            serializer = BlogEntrySerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError as e:
            if 'api_blogentry_title_author_id' in str(e):
                return Response(
                    {"error": "You already have a blog post with this title. Please choose a different title."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {"error": "An error occurred while creating the blog post."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
class BlogCommentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, blog_entry_id):
        """
        Create a new comment on a blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to comment on
        
        Request Body:
        {
            "content": "Comment content"
        }
        """
        try:
            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to comment
            if blog_entry.visibility == 'journal':
                return Response(
                    {"error": "Cannot comment on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not Friendship.objects.filter(
                user=blog_entry.author,
                follower=request.user
            ).exists():
                return Response(
                    {"error": "Cannot comment on friends-only entries unless you are friends with the author"},
                    status=status.HTTP_403_FORBIDDEN
                )

            serializer = BlogCommentSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                serializer.save(
                    author=request.user,
                    blog_entry=blog_entry
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except BlogEntry.DoesNotExist:
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, blog_entry_id, comment_id):
        """
        Delete a comment.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry
        - comment_id: ID of the comment to delete
        
        Note: Users can only delete their own comments or comments on their own blog entries
        """
        try:
            comment = BlogComment.objects.get(id=comment_id, blog_entry_id=blog_entry_id)
            
            # Check if user has permission to delete the comment
            # Users can delete their own comments or comments on their own blog entries
            if request.user != comment.author and request.user != comment.blog_entry.author:
                return Response(
                    {"error": "You can only delete your own comments or comments on your own blog entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            comment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except BlogComment.DoesNotExist:
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogCommentsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_entry_id):
        """
        Get all comments for a specific blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to get comments for
        """
        try:
            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view comments
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                return Response(
                    {"error": "Cannot view comments on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                return Response(
                    {"error": "Must be logged in to view comments on friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and request.user != blog_entry.author:
                if not Friendship.objects.filter(
                    user=blog_entry.author,
                    follower=request.user
                ).exists():
                    return Response(
                        {"error": "Cannot view comments on friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            comments = BlogComment.objects.filter(blog_entry=blog_entry).order_by('-created_at')
            serializer = BlogCommentSerializer(comments, many=True)
            return Response(serializer.data)
            
        except BlogEntry.DoesNotExist:
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class BlogLikeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, blog_entry_id):
        """
        Like a blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to like
        """
        try:
            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to like
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                return Response(
                    {"error": "Cannot like private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not Friendship.objects.filter(
                user=blog_entry.author,
                follower=request.user
            ).exists():
                return Response(
                    {"error": "Cannot like friends-only entries unless you are friends with the author"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Check if user already liked this blog
            if BlogLike.objects.filter(blog_entry=blog_entry, user=request.user).exists():
                return Response(
                    {"error": "You have already liked this blog entry"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the like
            like = BlogLike.objects.create(
                blog_entry=blog_entry,
                user=request.user
            )
            
            serializer = BlogLikeSerializer(like)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except BlogEntry.DoesNotExist:
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, blog_entry_id):
        """
        Unlike a blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to unlike
        """
        try:
            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Find and delete the like
            like = BlogLike.objects.filter(blog_entry=blog_entry, user=request.user).first()
            if not like:
                return Response(
                    {"error": "You have not liked this blog entry"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            like.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except BlogEntry.DoesNotExist:
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogLikesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_entry_id):
        """
        Get all likes for a specific blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to get likes for
        """
        try:
            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view likes
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                return Response(
                    {"error": "Cannot view likes on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                return Response(
                    {"error": "Must be logged in to view likes on friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and request.user != blog_entry.author:
                if not Friendship.objects.filter(
                    user=blog_entry.author,
                    follower=request.user
                ).exists():
                    return Response(
                        {"error": "Cannot view likes on friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            likes = BlogLike.objects.filter(blog_entry=blog_entry).order_by('-created_at')
            serializer = BlogLikeSerializer(likes, many=True)
            return Response(serializer.data)
            
        except BlogEntry.DoesNotExist:
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogLikeCountView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_entry_id):
        """
        Get the number of likes for a specific blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to get like count for
        """
        try:
            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view like count
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                return Response(
                    {"error": "Cannot view like count on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                return Response(
                    {"error": "Must be logged in to view like count on friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and request.user != blog_entry.author:
                if not Friendship.objects.filter(
                    user=blog_entry.author,
                    follower=request.user
                ).exists():
                    return Response(
                        {"error": "Cannot view like count on friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            like_count = BlogLike.objects.filter(blog_entry=blog_entry).count()
            return Response({"like_count": like_count})
            
        except BlogEntry.DoesNotExist:
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class CommentLikeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, comment_id):
        """
        Like a comment.
        
        URL Parameters:
        - comment_id: ID of the comment to like
        """
        try:
            comment = BlogComment.objects.get(id=comment_id)
            
            # Check if user has permission to like
            if comment.blog_entry.visibility == 'journal' and request.user != comment.blog_entry.author:
                return Response(
                    {"error": "Cannot like comments on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and not Friendship.objects.filter(
                user=comment.blog_entry.author,
                follower=request.user
            ).exists():
                return Response(
                    {"error": "Cannot like comments on friends-only entries unless you are friends with the author"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Check if user already liked this comment
            if CommentLike.objects.filter(comment=comment, user=request.user).exists():
                return Response(
                    {"error": "You have already liked this comment"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the like
            like = CommentLike.objects.create(
                comment=comment,
                user=request.user
            )
            
            serializer = CommentLikeSerializer(like)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except BlogComment.DoesNotExist:
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, comment_id):
        """
        Unlike a comment.
        
        URL Parameters:
        - comment_id: ID of the comment to unlike
        """
        try:
            comment = BlogComment.objects.get(id=comment_id)
            
            # Find and delete the like
            like = CommentLike.objects.filter(comment=comment, user=request.user).first()
            if not like:
                return Response(
                    {"error": "You have not liked this comment"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            like.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except BlogComment.DoesNotExist:
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetCommentLikesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, comment_id):
        """
        Get all likes for a specific comment.
        
        URL Parameters:
        - comment_id: ID of the comment to get likes for
        """
        try:
            comment = BlogComment.objects.get(id=comment_id)
            
            # Check if user has permission to view likes
            if comment.blog_entry.visibility == 'journal' and request.user != comment.blog_entry.author:
                return Response(
                    {"error": "Cannot view likes on comments in private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                return Response(
                    {"error": "Must be logged in to view likes on comments in friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and request.user != comment.blog_entry.author:
                if not Friendship.objects.filter(
                    user=comment.blog_entry.author,
                    follower=request.user
                ).exists():
                    return Response(
                        {"error": "Cannot view likes on comments in friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            likes = CommentLike.objects.filter(comment=comment).order_by('-created_at')
            serializer = CommentLikeSerializer(likes, many=True)
            return Response(serializer.data)
            
        except BlogComment.DoesNotExist:
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetCommentLikeCountView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, comment_id):
        """
        Get the number of likes for a specific comment.
        
        URL Parameters:
        - comment_id: ID of the comment to get like count for
        """
        try:
            comment = BlogComment.objects.get(id=comment_id)
            
            # Check if user has permission to view like count
            if comment.blog_entry.visibility == 'journal' and request.user != comment.blog_entry.author:
                return Response(
                    {"error": "Cannot view like count on comments in private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                return Response(
                    {"error": "Must be logged in to view like count on comments in friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if comment.blog_entry.visibility == 'friends' and request.user != comment.blog_entry.author:
                if not Friendship.objects.filter(
                    user=comment.blog_entry.author,
                    follower=request.user
                ).exists():
                    return Response(
                        {"error": "Cannot view like count on comments in friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            like_count = CommentLike.objects.filter(comment=comment).count()
            return Response({"like_count": like_count})
            
        except BlogComment.DoesNotExist:
            return Response(
                {"error": "Comment not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogCommentCountView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_entry_id):
        """
        Get the number of comments for a specific blog entry.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to get comment count for
        """
        try:
            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view comment count
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                return Response(
                    {"error": "Cannot view comment count on private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                return Response(
                    {"error": "Must be logged in to view comment count on friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and request.user != blog_entry.author:
                if not Friendship.objects.filter(
                    user=blog_entry.author,
                    follower=request.user
                ).exists():
                    return Response(
                        {"error": "Cannot view comment count on friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            comment_count = BlogComment.objects.filter(blog_entry=blog_entry).count()
            return Response({"comment_count": comment_count})
            
        except BlogEntry.DoesNotExist:
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class GetBlogEntryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, blog_entry_id):
        """
        Get a specific blog entry by ID.
        
        URL Parameters:
        - blog_entry_id: ID of the blog entry to retrieve
        """
        try:
            blog_entry = BlogEntry.objects.get(id=blog_entry_id)
            
            # Check if user has permission to view the blog entry
            if blog_entry.visibility == 'journal' and request.user != blog_entry.author:
                return Response(
                    {"error": "Cannot view private journal entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and not request.user.is_authenticated:
                return Response(
                    {"error": "Must be logged in to view friends-only entries"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if blog_entry.visibility == 'friends' and request.user != blog_entry.author:
                if not Friendship.objects.filter(
                    user=blog_entry.author,
                    follower=request.user
                ).exists():
                    return Response(
                        {"error": "Cannot view friends-only entries unless you are friends with the author"},
                        status=status.HTTP_403_FORBIDDEN
                    )

            serializer = BlogEntrySerializer(blog_entry)
            return Response(serializer.data)
            
        except BlogEntry.DoesNotExist:
            return Response(
                {"error": "Blog entry not found"},
                status=status.HTTP_404_NOT_FOUND
            )