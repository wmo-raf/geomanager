from allauth.account.forms import ResetPasswordForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils.module_loading import import_string
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenVerifyView
from wagtail.users.models import UserProfile as WagtailUserProfile

from geomanager.serializers import RegisterSerializer, ResetPasswordSerializer
from geomanager.serializers.auth import EmailTokenObtainSerializer


class RegisterView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def perform_create(self, serializer):
        email = serializer.validated_data['username']

        # check if user exists
        if get_user_model().objects.filter(email=email).exists():
            raise ValidationError({"email": "User with this email already exists"})

        user = get_user_model().objects.create(
            username=email,
            email=email
        )
        user.save()
        form = ResetPasswordForm({"email": user.email})
        if form.is_valid():
            form.save(self.request)

        return user


class ResetPasswordView(generics.CreateAPIView):
    queryset = get_user_model().objects.all()
    permission_classes = (AllowAny,)
    serializer_class = ResetPasswordSerializer

    def perform_create(self, serializer):
        email = serializer.validated_data['username']

        try:
            user = get_user_model().objects.get(email=email)
            form = ResetPasswordForm({"email": user.email})
            if form.is_valid():
                form.save(self.request)

            return user
        except ObjectDoesNotExist:
            raise ValidationError({"email": "User with this email does not exist"})


class EmailTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainSerializer


class UserTokenVerifyView(TokenVerifyView):
    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            if request.data.get("refresh"):
                try:
                    serializer_cls = import_string(api_settings.TOKEN_REFRESH_SERIALIZER)
                    serializer = serializer_cls(data=request.data)
                    serializer.is_valid(raise_exception=True)
                except TokenError as e:
                    raise InvalidToken(e.args[0])
            else:
                raise InvalidToken(e.args[0])

        if serializer.validated_data:
            token = AccessToken(serializer.validated_data.get("access"))
        else:
            token = AccessToken(request.data.get("token"))

        user_id = token.get("user_id")
        try:
            user = get_user_model().objects.get(id=user_id)
        except ObjectDoesNotExist:
            return Response({"detail": "user does not exist"}, status=404)

        avatar_url = None
        try:
            wagtail_profile = WagtailUserProfile.get_for_user(user)
            if wagtail_profile.avatar:
                avatar_url = request.build_absolute_uri(wagtail_profile.avatar.url)
        except Exception:
            avatar_url = None

        user_details = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.get_full_name() or None,
            "avatar": avatar_url,
        }

        return Response(user_details)
