import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

# First URL segment used by the site itself; a user named like this would
# collide with the ``/<username>/<project>/`` routes.
RESERVED_USERNAMES = {
    "admin", "api", "static", "media", "login", "logout", "signup", "dashboard",
    "new", "docs", "settings", "about", "help", "sdk", "users", "i18n", "blog", "healthz",
}
USERNAME_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")


class SignupForm(UserCreationForm):
    email = forms.EmailField(label=_("Email"))

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")
        labels = {"username": _("Username")}
        help_texts = {"username": _("Letters, numbers and hyphens. It will be part of your project URLs.")}

    def clean_username(self):
        username = self.cleaned_data["username"]
        if not USERNAME_RE.match(username):
            raise forms.ValidationError(_("Use only letters, numbers and hyphens (not at the start or end)."))
        if username.lower() in RESERVED_USERNAMES:
            raise forms.ValidationError(_("That username is reserved."))
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(_("That username is already taken."))
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("An account with that email already exists."))
        return email
