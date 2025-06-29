from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from rest_framework_simplejwt.tokens import AccessToken
from django.utils.translation import gettext_lazy as _

class CookieJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # Extract JWT token from cookies
        jwt_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE'])
        
        if not jwt_token:
            # Allow unauthenticated user access
            return None
            
        try:
            # If token exists, return the user and the token
            validated_token = AccessToken(jwt_token)
            user_id = validated_token.get('user_id')
            if user_id is None:
                return None
            user = User.objects.get(id=user_id)
            return (user, validated_token)
        except Exception as e:
            return None

    def authenticate_header(self, request):
        return 'Bearer'
