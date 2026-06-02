from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        login_value = (username or kwargs.get("username") or "").strip()
        if not login_value or not password:
            return None

        if "@" not in login_value:
            return super().authenticate(request, username=login_value, password=password, **kwargs)

        for user in User.objects.filter(email__iexact=login_value):
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
