from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..serializers import SignupSerializer
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from ..models import BlogEntry, FriendRequest, Friendship
from ..serializers import BlogEntrySerializer
from django.db import models
from django.contrib.auth.models import User

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
        serializer = BlogEntrySerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)