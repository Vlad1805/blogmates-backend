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
    permission_classes = [AllowAny]

    def get(self, request, id):
        if id == "all":
            # Return all accessible blog entries
            if request.user.is_authenticated:
                blog_entries = BlogEntry.objects.filter(
                    models.Q(author=request.user) |
                    models.Q(visibility='public') |
                    models.Q(visibility='friends', author__friendships__follower=request.user)
                ).distinct()
            else:
                # For unauthenticated users, only show public entries
                blog_entries = BlogEntry.objects.filter(visibility='public')

            serializer = BlogEntrySerializer(blog_entries, many=True)
            return Response(serializer.data)

        else:
            # Return a specific blog entry by ID
            try:
                blog_entry = BlogEntry.objects.get(pk=id)

                # Check access for unauthenticated and authenticated users
                if blog_entry.visibility == 'public':
                    # Public entries are accessible to everyone
                    pass
                elif request.user.is_authenticated:
                    # Check additional access for logged-in users
                    if blog_entry.author == request.user:
                        pass  # The user is the author
                    elif blog_entry.visibility == 'friends' and Friendship.objects.filter(user=blog_entry.author, follower=request.user).exists():
                        pass  # The user is a friend
                    else:
                        return Response({'detail': 'You do not have access to this blog entry.'}, status=status.HTTP_403_FORBIDDEN)
                else:
                    # For unauthenticated users, restrict access to private entries
                    return Response({'detail': 'You do not have access to this blog entry.'}, status=status.HTTP_403_FORBIDDEN)

                serializer = BlogEntrySerializer(blog_entry)
                return Response(serializer.data)

            except BlogEntry.DoesNotExist:
                return Response({'detail': 'Blog entry not found.'}, status=status.HTTP_404_NOT_FOUND)