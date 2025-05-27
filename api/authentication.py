from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from rest_framework_simplejwt.tokens import AccessToken
from django.utils.translation import gettext_lazy as _

class CookieJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # Get the JWT token from the cookie
        jwt_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE'])
        
        if not jwt_token:
            # Return None to indicate no authentication was attempted
            # This allows the view to handle unauthenticated access
            return None
            
        try:
            # Validate the token
            validated_token = AccessToken(jwt_token)
            # Get the user ID from the token
            user_id = validated_token.get('user_id')
            if user_id is None:
                return None
            # Get the actual User object
            user = User.objects.get(id=user_id)
            return (user, validated_token)
        except Exception as e:
            return None

    def authenticate_header(self, request):
        return 'Bearer'
