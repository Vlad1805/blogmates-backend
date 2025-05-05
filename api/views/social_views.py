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

class SendFriendRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        receiver_id = request.data.get('receiver_id')
        if not receiver_id:
            return Response({'error': 'Receiver ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if receiver_id == request.user.id:
            return Response({'error': 'You cannot send a friend request to yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            receiver = User.objects.get(id=receiver_id)

            # Check if the sender is already following the receiver
            if Friendship.objects.filter(user=receiver, follower=request.user).exists():
                return Response({'error': 'You are already friends with this user.'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if there is an existing pending friend request
            if FriendRequest.objects.filter(sender=request.user, receiver=receiver, is_accepted=False).exists():
                return Response({'error': 'Friend request already sent.'}, status=status.HTTP_400_BAD_REQUEST)

            # Create a new friend request
            FriendRequest.objects.create(sender=request.user, receiver=receiver)
            return Response({'message': 'Friend request sent successfully.'}, status=status.HTTP_201_CREATED)

        except User.DoesNotExist:
            return Response({'error': 'Receiver not found.'}, status=status.HTTP_404_NOT_FOUND)

class PendingFriendRequestsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pending_requests = request.user.received_friend_requests
        data = [
            {
                'id': req.id,
                'sender_id': req.sender.id,
                'sender_name': req.sender.username,
                'created_at': req.created_at
            }
            for req in pending_requests
        ]
        return Response(data, status=status.HTTP_200_OK)
    
class PendingSentFriendRequestsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pending_requests = request.user.sent_friend_requests
        data = [
            {
                'id': req.id,
                'receiver_id': req.receiver.id,
                'receiver_name': req.receiver.username,
                'created_at': req.created_at
            }
            for req in pending_requests
        ]
        return Response(data, status=status.HTTP_200_OK)

class AcceptFriendRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        try:
            friend_request = FriendRequest.objects.get(id=request_id, receiver=request.user, is_accepted=False)
            
            # Create an entry in the Friendship table
            Friendship.objects.create(user=request.user, follower=friend_request.sender)
            
            # Delete the friend request after it has been processed
            friend_request.delete()

            return Response({'message': 'Friend request accepted successfully.'}, status=status.HTTP_200_OK)
        except FriendRequest.DoesNotExist:
            return Response({'error': 'Friend request not found or already accepted.'}, status=status.HTTP_404_NOT_FOUND)


class RemoveFriendRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, request_id):
        try:
            # Combine conditions using Q objects
            friend_request = FriendRequest.objects.get(
                models.Q(id=request_id) & (models.Q(sender=request.user) | models.Q(receiver=request.user))
            )
            friend_request.delete()
            return Response({'message': 'Friend request removed successfully.'}, status=status.HTTP_200_OK)
        except FriendRequest.DoesNotExist:
            return Response({'error': 'Friend request not found.'}, status=status.HTTP_404_NOT_FOUND)

class GetFollowersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        followers = request.user.followers  # Uses the `followers` property from the User model
        data = [{'id': f.follower.id, 'username': f.follower.username} for f in followers]
        return Response(data, status=status.HTTP_200_OK)

class GetFollowingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        following = request.user.following  # Uses the `following` property from the User model
        data = [{'id': f.user.id, 'username': f.user.username} for f in following]
        return Response(data, status=status.HTTP_200_OK)

class UnfollowUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, user_id):
        try:
            # Check if the user is being followed
            followed = User.objects.get(id=user_id)
            print(followed)
            friendship = Friendship.objects.get(user=followed, follower=request.user)
            friendship.delete()
            return Response({'message': 'You have unfollowed the user.'}, status=status.HTTP_200_OK)
        except Friendship.DoesNotExist:
            return Response({'error': 'You are not following this user.'}, status=status.HTTP_404_NOT_FOUND)

class RemoveFollowerAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, user_id):
        try:
            # Check if the user is a follower
            follower = User.objects.get(id=user_id)
            friendship = Friendship.objects.get(user=request.user, follower=follower)
            friendship.delete()
            return Response({'message': 'Follower removed successfully.'}, status=status.HTTP_200_OK)
        except Friendship.DoesNotExist:
            return Response({'error': 'This user is not following you.'}, status=status.HTTP_404_NOT_FOUND)

