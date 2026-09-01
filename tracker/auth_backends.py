from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveModelBackend(ModelBackend):
    """Authenticate with a case-insensitive username match, so "Alice" and
    "alice" log into the same account.

    Registration forbids usernames that differ only by case (see
    RegisterForm.clean_username), so this lookup is normally unambiguous. If a
    legacy case-variant pair ever exists we fall back to an exact match rather
    than raising.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = UserModel._default_manager.get(username__iexact=username)
        except UserModel.DoesNotExist:
            # Run the hasher once anyway to blunt username-enumeration timing,
            # mirroring Django's default ModelBackend.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            # Legacy duplicates that differ only by case — prefer an exact match.
            try:
                user = UserModel._default_manager.get(username=username)
            except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
                return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
