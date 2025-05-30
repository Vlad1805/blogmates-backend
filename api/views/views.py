from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..serializers import SignupSerializer
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from ..models import BlogEntry, FriendRequest, Friendship, UserProfile, User
from ..serializers import BlogEntrySerializer, UserProfileSerializer
from django.db import models
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from ..authentication import CookieJWTAuthentication

# Create your views here.
def sanity(request):
    return HttpResponse("Server is up and running")

class CookieTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    authentication_classes = []
    """Custom login view that sets JWT tokens in HTTP-only cookies."""
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            data = response.data
            response.set_cookie(
                settings.SIMPLE_JWT["AUTH_COOKIE"],
                data["access"],
                max_age=3600,
                httponly=True,
                secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
                samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
            )
            response.set_cookie(
                settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"],
                data["refresh"],
                max_age=7 * 24 * 3600,
                httponly=True,
                secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
                samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
            )
            del response.data["access"]
            del response.data["refresh"]
        return response

class CookieTokenRefreshView(TokenRefreshView):
    """Refreshes the access token using the refresh token from the cookie."""
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])
        if not refresh_token:
            return Response({"error": "No refresh token"}, status=401)

        request.data["refresh"] = refresh_token  # Use cookie token
        response = super().post(request, *args, **kwargs)

        if "access" in response.data:
            response.set_cookie(
                settings.SIMPLE_JWT["AUTH_COOKIE"],
                response.data["access"],
                max_age=3600,
                httponly=True,
                secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
                samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
            )
            del response.data["access"]

        return response

class LogoutView(APIView):
    """Clears authentication cookies on logout."""
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request):
        response = Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
        response.delete_cookie(settings.SIMPLE_JWT["AUTH_COOKIE"])
        response.delete_cookie(settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])
        return response

class SignupAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()  # Create the user
            return Response({'message': 'User created successfully!'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        user = request.user
        user_profile = get_object_or_404(UserProfile, user__id=user.id)
        return Response(UserProfileSerializer(user_profile).data)
    
class UserProfileView(APIView):
    permission_classes = [AllowAny]  # Allow public access to view profiles
    
    def get(self, request, *args, **kwargs):
        """
        Handle GET request to retrieve the user profile by ID.
        This is accessible by everyone (public access).
        
        Args:
            request: The HTTP request
            user_id: The ID of the user whose profile to retrieve
            
        Returns:
            Response: Serialized user profile data or error message
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response(
                {"error": "User ID is required as a query parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Retrieve the UserProfile for the given user ID
            user_profile = get_object_or_404(UserProfile, user__id=user_id)
            
            # Serialize the profile data with request context
            serializer = UserProfileSerializer(user_profile, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Error retrieving user profile: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to retrieve the user profile by username.
        This is accessible by everyone (public access).
        
        Args:
            request: The HTTP request containing the username in the request body
            
        Returns:
            Response: Serialized user profile data or error message
        """
        username = request.data.get('username')
        if not username:
            return Response(
                {"error": "Username is required in request body"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Retrieve the UserProfile for the given username
            user_profile = get_object_or_404(UserProfile, user__username=username)
            
            # Serialize the profile data with request context
            serializer = UserProfileSerializer(user_profile, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Error retrieving user profile: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, *args, **kwargs):
        """
        Handle PATCH request to update the user profile.
        This is only for the logged-in user (authenticated access).
        Only allows updating username, first_name, last_name, and profile_picture.
        """
        # Retrieve the logged-in user's profile
        try:
            user_profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)

        # Filter the request data to only include allowed fields
        allowed_fields = ['username', 'first_name', 'last_name', 'profile_picture', 'profile_picture_content_type', 'biography']
        filtered_data = {k: v for k, v in request.data.items() if k in allowed_fields}

        # Update user fields
        user = request.user
        if 'username' in filtered_data:
            new_username = filtered_data['username']
            # Check if username is already taken by another user
            if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                return Response(
                    {"username": "A user with this username already exists."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.username = new_username
            filtered_data.pop('username')
        if 'first_name' in filtered_data:
            user.first_name = filtered_data.pop('first_name')
        if 'last_name' in filtered_data:
            user.last_name = filtered_data.pop('last_name')
        user.save()

        # Update profile fields
        serializer = UserProfileSerializer(user_profile, data=filtered_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)