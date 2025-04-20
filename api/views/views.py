from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..serializers import SignupSerializer
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from ..models import BlogEntry, FriendRequest, Friendship, UserProfile
from ..serializers import BlogEntrySerializer, UserProfileSerializer
from django.db import models
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

# Create your views here.
def sanity(request):
    return HttpResponse("Server is up and running")

class CookieTokenObtainPairView(TokenObtainPairView):
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


class LoginView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)

        if user is not None:
            refresh = RefreshToken.for_user(user)
            response = Response({"message": "Login successful"}, status=status.HTTP_200_OK)

            # Set cookies with HttpOnly flag
            response.set_cookie(
                key="access_token",
                value=str(refresh.access_token),
                httponly=True,  # Prevent JavaScript access
                secure=False,  # Set to True in production (requires HTTPS)
                samesite="Lax",
            )
            response.set_cookie(
                key="refresh_token",
                value=str(refresh),
                httponly=True,
                secure=False,
                samesite="Lax",
            )
            return response
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(APIView):
    """Clears authentication cookies on logout."""

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

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "followers_count": user.followers.count(),
            "following_count": user.following.count(),
        })
    
class UserProfileView(APIView):
    
    def get(self, request, user_id, *args, **kwargs):
        """
        Handle GET request to retrieve the user profile by user_id.
        This is accessible by everyone (public access).
        """
        # Retrieve the UserProfile for the given user_id
        print(f"Fetching profile for user_id: {user_id}")
        user_profile = get_object_or_404(UserProfile, user__id=user_id)
        
        # Serialize the profile data
        serializer = UserProfileSerializer(user_profile)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        """
        Handle PATCH request to update the user profile.
        This is only for the logged-in user (authenticated access).
        """
        # Retrieve the logged-in user's profile
        try:
            user_profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return Response({"detail": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)

        # Partially update the profile
        serializer = UserProfileSerializer(user_profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)