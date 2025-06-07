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
import logging

logger = logging.getLogger('api')

# Create your views here.
def sanity(request):
    return HttpResponse("Server is up and running")

class CookieTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    authentication_classes = []
    """Custom login view that sets JWT tokens in HTTP-only cookies."""
    
    def post(self, request, *args, **kwargs):
        logger.info('Login attempt', extra={
            'username': request.data.get('username'),
            'ip': request.META.get('REMOTE_ADDR')
        })
        
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
            logger.info('Login successful', extra={
                'username': request.data.get('username'),
                'ip': request.META.get('REMOTE_ADDR')
            })
        else:
            logger.warning('Login failed', extra={
                'username': request.data.get('username'),
                'ip': request.META.get('REMOTE_ADDR'),
                'status_code': response.status_code
            })
        return response

class CookieTokenRefreshView(TokenRefreshView):
    """Refreshes the access token using the refresh token from the cookie."""
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request, *args, **kwargs):
        logger.info('Token refresh attempt', extra={
            'ip': request.META.get('REMOTE_ADDR')
        })
        
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])
        if not refresh_token:
            logger.warning('Token refresh failed - no refresh token', extra={
                'ip': request.META.get('REMOTE_ADDR')
            })
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
            logger.info('Token refresh successful', extra={
                'ip': request.META.get('REMOTE_ADDR')
            })
        else:
            logger.warning('Token refresh failed', extra={
                'ip': request.META.get('REMOTE_ADDR'),
                'status_code': response.status_code
            })

        return response

class LogoutView(APIView):
    """Clears authentication cookies on logout."""
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request):
        logger.info('Logout attempt', extra={
            'user_id': request.user.id if request.user.is_authenticated else None,
            'ip': request.META.get('REMOTE_ADDR')
        })
        
        response = Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
        response.delete_cookie(settings.SIMPLE_JWT["AUTH_COOKIE"])
        response.delete_cookie(settings.SIMPLE_JWT["AUTH_COOKIE_REFRESH"])
        
        logger.info('Logout successful', extra={
            'user_id': request.user.id if request.user.is_authenticated else None,
            'ip': request.META.get('REMOTE_ADDR')
        })
        return response

class SignupAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        logger.info('Signup attempt', extra={
            'username': request.data.get('username'),
            'email': request.data.get('email'),
            'ip': request.META.get('REMOTE_ADDR')
        })
        
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()  # Create the user
            logger.info('Signup successful', extra={
                'user_id': user.id,
                'username': user.username,
                'ip': request.META.get('REMOTE_ADDR')
            })
            return Response({'message': 'User created successfully!'}, status=status.HTTP_201_CREATED)
        
        logger.warning('Signup failed - validation error', extra={
            'username': request.data.get('username'),
            'email': request.data.get('email'),
            'errors': serializer.errors,
            'ip': request.META.get('REMOTE_ADDR')
        })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        logger.info('Current user profile retrieval', extra={
            'user_id': request.user.id,
            'ip': request.META.get('REMOTE_ADDR')
        })
        
        try:
            user_profile = get_object_or_404(UserProfile, user__id=request.user.id)
            logger.info('Current user profile retrieved successfully', extra={
                'user_id': request.user.id,
                'username': request.user.username
            })
            return Response(UserProfileSerializer(user_profile).data)
        except Exception as e:
            logger.error('Current user profile retrieval failed', extra={
                'user_id': request.user.id,
                'error': str(e),
                'error_type': type(e).__name__
            }, exc_info=True)
            return Response(
                {"error": "Error retrieving user profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
class UserProfileView(APIView):
    permission_classes = [AllowAny]  # Allow public access to view profiles
    
    def get(self, request, *args, **kwargs):
        """
        Handle GET request to retrieve the user profile by ID.
        This is accessible by everyone (public access).
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            logger.warning('User profile retrieval failed - no user_id provided', extra={
                'ip': request.META.get('REMOTE_ADDR')
            })
            return Response(
                {"error": "User ID is required as a query parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info('User profile retrieval by ID', extra={
            'requested_user_id': user_id,
            'requesting_user_id': request.user.id if request.user.is_authenticated else None,
            'ip': request.META.get('REMOTE_ADDR')
        })

        try:
            user_profile = get_object_or_404(UserProfile, user__id=user_id)
            serializer = UserProfileSerializer(user_profile, context={'request': request})
            logger.info('User profile retrieved successfully', extra={
                'requested_user_id': user_id,
                'requesting_user_id': request.user.id if request.user.is_authenticated else None
            })
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error('User profile retrieval failed', extra={
                'requested_user_id': user_id,
                'requesting_user_id': request.user.id if request.user.is_authenticated else None,
                'error': str(e),
                'error_type': type(e).__name__
            }, exc_info=True)
            return Response(
                {"error": f"Error retrieving user profile: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to retrieve the user profile by username.
        This is accessible by everyone (public access).
        """
        username = request.data.get('username')
        if not username:
            logger.warning('User profile retrieval failed - no username provided', extra={
                'ip': request.META.get('REMOTE_ADDR')
            })
            return Response(
                {"error": "Username is required in request body"},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info('User profile retrieval by username', extra={
            'requested_username': username,
            'requesting_user_id': request.user.id if request.user.is_authenticated else None,
            'ip': request.META.get('REMOTE_ADDR')
        })

        try:
            user_profile = get_object_or_404(UserProfile, user__username=username)
            serializer = UserProfileSerializer(user_profile, context={'request': request})
            logger.info('User profile retrieved successfully', extra={
                'requested_username': username,
                'requesting_user_id': request.user.id if request.user.is_authenticated else None
            })
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error('User profile retrieval failed', extra={
                'requested_username': username,
                'requesting_user_id': request.user.id if request.user.is_authenticated else None,
                'error': str(e),
                'error_type': type(e).__name__
            }, exc_info=True)
            return Response(
                {"error": f"Error retrieving user profile: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, *args, **kwargs):
        """
        Handle PATCH request to update the user profile.
        This is only for the logged-in user (authenticated access).
        """
        logger.info('User profile update attempt', extra={
            'user_id': request.user.id,
            'ip': request.META.get('REMOTE_ADDR')
        })

        try:
            user_profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            logger.warning('User profile update failed - profile not found', extra={
                'user_id': request.user.id
            })
            return Response({"detail": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)

        # Filter the request data to only include allowed fields
        allowed_fields = ['username', 'first_name', 'last_name', 'profile_picture', 'profile_picture_content_type', 'biography']
        filtered_data = {k: v for k, v in request.data.items() if k in allowed_fields}

        # Update user fields
        user = request.user
        if 'username' in filtered_data:
            new_username = filtered_data['username']
            if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                logger.warning('User profile update failed - username already taken', extra={
                    'user_id': request.user.id,
                    'requested_username': new_username
                })
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
            logger.info('User profile updated successfully', extra={
                'user_id': request.user.id,
                'updated_fields': list(filtered_data.keys())
            })
            return Response(serializer.data)
        
        logger.warning('User profile update failed - validation error', extra={
            'user_id': request.user.id,
            'errors': serializer.errors
        })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)